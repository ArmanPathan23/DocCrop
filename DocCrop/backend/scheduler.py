from datetime import date, timedelta
from typing import List, Dict


SCHEDULES: Dict[str, List[Dict]] = {
    'Wheat': [
        {"days_after_sowing": 10, "pesticide": "Herbicide A", "note": "Weed control"},
        {"days_after_sowing": 25, "pesticide": "Fungicide B", "note": "Rust prevention"},
        {"days_after_sowing": 40, "pesticide": "Insecticide C", "note": "Aphid control"},
    ],
    'Rice': [
        {"days_after_sowing": 15, "pesticide": "Herbicide R1", "note": "Weed control"},
        {"days_after_sowing": 30, "pesticide": "Fungicide R2", "note": "Blast prevention"},
    ],
}


def get_pesticide_schedule(crop: str) -> List[Dict]:
    crop = (crop or 'Wheat').strip()
    return SCHEDULES.get(crop, SCHEDULES['Wheat'])


def next_pesticide_recommendation(crop: str, from_date: date) -> Dict:
    # Simple demo: assume sowing happened 7 days before from_date
    crop = (crop or 'Wheat').strip()
    schedule = get_pesticide_schedule(crop)
    sowing_date = from_date - timedelta(days=7)
    for item in schedule:
        due_date = sowing_date + timedelta(days=item['days_after_sowing'])
        if due_date >= from_date:
            return {"due_date": due_date.isoformat(), **item}
    return {"message": "No upcoming tasks in schedule"}


