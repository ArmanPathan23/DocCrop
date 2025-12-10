import os
import sys
import sqlite3
from io import BytesIO
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file
try:
    # Running as package: python -m backend.app
    from .translator import translate_text, synthesize_speech
    from .weather import get_weather
    from .market import get_market_rates
    from .scheduler import get_pesticide_schedule, next_pesticide_recommendation
except Exception:
    # Running as script: python backend/app.py
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from translator import translate_text, synthesize_speech  # type: ignore
    from weather import get_weather  # type: ignore
    from market import get_market_rates  # type: ignore
    from scheduler import get_pesticide_schedule, next_pesticide_recommendation  # type: ignore
from PIL import Image


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'expenses.db')

# --- MongoDB optional ---
MONGODB_URI = os.environ.get('MONGODB_URI', '').strip()
USE_MONGO = False
mongo_client = None
mongo_collection = None  # expenses collection
mongo_notes = None  # notes collection
if MONGODB_URI:
    try:
        from pymongo import MongoClient
        mongo_client = MongoClient(MONGODB_URI)
        mongo_db = mongo_client.get_database(os.environ.get('MONGODB_DB', 'smart_agri_assist'))
        mongo_collection = mongo_db.get_collection(os.environ.get('MONGODB_COLLECTION', 'expenses'))
        mongo_notes = mongo_db.get_collection(os.environ.get('MONGODB_NOTES_COLLECTION', 'notes'))
        USE_MONGO = True
    except Exception:
        USE_MONGO = False


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, 'static'),
        template_folder=os.path.join(os.path.dirname(BASE_DIR), 'templates'),
    )

    # --- DB bootstrap for expenses ---
    def init_db():
        if USE_MONGO:
            # MongoDB is schemaless; ensure index for performance
            try:
                mongo_collection.create_index('date')
                mongo_collection.create_index('type')
                mongo_notes.create_index('created_at')
                mongo_notes.create_index('title')
            except Exception:
                pass
            return
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    type TEXT CHECK(type IN ('expense','income')) NOT NULL,
                    category TEXT NOT NULL,
                    amount REAL NOT NULL,
                    note TEXT
                );
                """
            )
            conn.commit()

    init_db()

    # ---------- Core pages ----------
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/translator')
    def translator_page():
        return render_template('translator.html')

    @app.route('/schemes')
    def schemes_page():
        return render_template('schemes.html')

    @app.route('/weather')
    def weather_page():
        return render_template('weather.html')

    @app.route('/market')
    def market_page():
        return render_template('market.html')

    @app.route('/expenses')
    def expenses_page():
        # Load existing entries for table view
        if USE_MONGO:
            rows = list(mongo_collection.find({}, sort=[('date', -1)]))
            # normalize shapes
            for r in rows:
                r['id'] = str(r.get('_id'))
        else:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute('SELECT * FROM entries ORDER BY date DESC, id DESC').fetchall()
        total_income = sum((r['amount'] if isinstance(r, dict) else r['amount']) for r in rows if (r['type'] if isinstance(r, dict) else r['type']) == 'income')
        total_expense = sum((r['amount'] if isinstance(r, dict) else r['amount']) for r in rows if (r['type'] if isinstance(r, dict) else r['type']) == 'expense')
        profit = total_income - total_expense
        return render_template('expenses.html', rows=rows, total_income=total_income, total_expense=total_expense, profit=profit)

    @app.route('/disease')
    def disease_page():
        return render_template('disease.html')

    @app.route('/scheduler')
    def scheduler_page():
        return render_template('scheduler.html')

    # ---------- Translator APIs ----------
    @app.route('/api/translate', methods=['POST'])
    def api_translate():
        data = request.get_json(force=True)
        text = data.get('text', '')
        src = data.get('src', 'auto')
        dest = data.get('dest', 'en')
        translated = translate_text(text=text, src=src, dest=dest)
        return jsonify({"translated": translated})

    @app.route('/api/tts', methods=['POST'])
    def api_tts():
        data = request.get_json(force=True)
        text = data.get('text', '')
        lang = data.get('lang', 'en')
        audio_bytes = synthesize_speech(text, lang)
        return send_file(BytesIO(audio_bytes), mimetype='audio/mpeg', as_attachment=False, download_name='tts.mp3')

    # ---------- Weather API ----------
    @app.route('/api/weather')
    def api_weather():
        city = request.args.get('city', 'Pune')
        return jsonify(get_weather(city))

    # ---------- Market API ----------
    @app.route('/api/market')
    def api_market():
        crop = request.args.get('crop', 'Wheat')
        return jsonify(get_market_rates(crop))

    # ---------- Scheduler API ----------
    @app.route('/api/schedule')
    def api_schedule():
        crop = request.args.get('crop', 'Wheat')
        schedule = get_pesticide_schedule(crop)
        next_due = next_pesticide_recommendation(crop, from_date=datetime.utcnow().date())
        return jsonify({"crop": crop, "schedule": schedule, "next_due": next_due})

    # ---------- Schemes (from JSON) ----------
    @app.route('/api/schemes')
    def api_schemes():
        state = request.args.get('state', '').lower().strip()
        district = request.args.get('district', '').lower().strip()
        json_path = os.path.join(BASE_DIR, 'schemes.json')
        results = []
        if os.path.exists(json_path):
            import json
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data.get('schemes', []):
                s_ok = (not state) or (item.get('state', '').lower() == state)
                d_ok = (not district) or (item.get('district', '').lower() == district)
                if s_ok and d_ok:
                    results.append(item)
        return jsonify({"schemes": results})

    # ---------- Expenses CRUD ----------
    @app.post('/api/expenses')
    def api_add_entry():
        payload = request.get_json(force=True)
        entry_date = payload.get('date') or datetime.utcnow().strftime('%Y-%m-%d')
        entry_type = payload.get('type', 'expense')
        category = payload.get('category', 'general')
        amount = float(payload.get('amount', 0))
        note = payload.get('note', '')
        if USE_MONGO:
            doc = {"date": entry_date, "type": entry_type, "category": category, "amount": amount, "note": note}
            res = mongo_collection.insert_one(doc)
            return jsonify({"status": "ok", "id": str(res.inserted_id)})
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('INSERT INTO entries (date, type, category, amount, note) VALUES (?,?,?,?,?)', (entry_date, entry_type, category, amount, note))
            conn.commit()
        return jsonify({"status": "ok"})

    @app.get('/api/expenses')
    def api_list_entries():
        if USE_MONGO:
            items = []
            for r in mongo_collection.find({}, sort=[('date', -1)]):
                r['id'] = str(r.get('_id'))
                r.pop('_id', None)
                items.append(r)
            return jsonify({"entries": items})
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM entries ORDER BY date DESC, id DESC').fetchall()
        return jsonify({"entries": [dict(r) for r in rows]})

    @app.delete('/api/expenses/<entry_id>')
    def api_delete_entry(entry_id):
        if USE_MONGO:
            from bson import ObjectId
            try:
                mongo_collection.delete_one({"_id": ObjectId(entry_id)})
                return jsonify({"deleted": entry_id})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        try:
            numeric_id = int(entry_id)
        except Exception:
            return jsonify({"error": "invalid id"}), 400
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('DELETE FROM entries WHERE id = ?', (numeric_id,))
            conn.commit()
        return jsonify({"deleted": numeric_id})

    # ---------- Simple Notes (Mongo-only demo storage) ----------
    @app.post('/api/notes')
    def api_add_note():
        if not USE_MONGO:
            return jsonify({"error": "MongoDB not configured"}), 400
        payload = request.get_json(force=True)
        title = (payload.get('title') or '').strip() or 'Untitled'
        content = (payload.get('content') or '').strip()
        now = datetime.utcnow().isoformat()
        res = mongo_notes.insert_one({"title": title, "content": content, "created_at": now})
        return jsonify({"status": "ok", "id": str(res.inserted_id)})

    @app.get('/api/notes')
    def api_list_notes():
        if not USE_MONGO:
            return jsonify({"error": "MongoDB not configured"}), 400
        items = []
        for doc in mongo_notes.find({}, sort=[('created_at', -1)]):
            doc['id'] = str(doc.get('_id'))
            doc.pop('_id', None)
            items.append(doc)
        return jsonify({"notes": items})

    # ---------- Disease Detection (Mock) ----------
    @app.post('/api/disease')
    def api_disease():
        if 'image' not in request.files:
            return jsonify({"error": "image is required"}), 400
        file = request.files['image']
        try:
            img = Image.open(file.stream).convert('RGB')
            # Simple heuristic: if average green channel is high => Healthy, else Possible disease
            pixels = list(img.resize((64, 64)).getdata())
            avg_r = sum(p[0] for p in pixels) / len(pixels)
            avg_g = sum(p[1] for p in pixels) / len(pixels)
            avg_b = sum(p[2] for p in pixels) / len(pixels)
            health_score = (avg_g - (avg_r + avg_b) / 2)
            if health_score > 10:
                label = 'Healthy Leaf'
                confidence = 0.85
                advice = 'No disease detected. Maintain regular irrigation and nutrient schedule.'
            else:
                label = 'Possible Leaf Disease'
                confidence = 0.7
                advice = 'Inspect for spots or discoloration. Consider broad-spectrum fungicide as per schedule.'
            return jsonify({
                "label": label,
                "confidence": round(confidence, 2),
                "metrics": {"avg_r": avg_r, "avg_g": avg_g, "avg_b": avg_b},
                "advice": advice,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
