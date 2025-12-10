import os
import requests


def get_weather(city: str = 'Pune') -> dict:
    api_key = os.environ.get('OPENWEATHER_API_KEY', '')
    if not api_key:
        return {"error": "OPENWEATHER_API_KEY not set", "city": city}
    params = {
        'q': city,
        'appid': api_key,
        'units': 'metric'
    }
    try:
        resp = requests.get('https://api.openweathermap.org/data/2.5/weather', params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "city": data.get('name', city),
            "temp_c": data.get('main', {}).get('temp'),
            "humidity": data.get('main', {}).get('humidity'),
            "condition": data.get('weather', [{}])[0].get('description', ''),
            "wind_mps": data.get('wind', {}).get('speed'),
        }
    except Exception as e:
        return {"error": str(e), "city": city}


