from typing import Dict

MOCK_RATES: Dict[str, Dict[str, float]] = {
    'Wheat': {"min": 1800, "max": 2200, "expected": 2050},
    'Rice': {"min": 2000, "max": 2500, "expected": 2300},
    'Corn': {"min": 1500, "max": 1900, "expected": 1750},
    'Soybean': {"min": 2500, "max": 3200, "expected": 2900},
}


def get_market_rates(crop: str) -> Dict[str, float]:
    crop = (crop or '').strip() or 'Wheat'
    return MOCK_RATES.get(crop, MOCK_RATES['Wheat'])


