"""
Weather Trigger Engine
=======================
Fetches REAL weather data from OpenMeteo (free, no API key needed) for
Indian districts and determines dynamic pest/disease threat triggers.

Uses actual agronomic disease-weather correlations:
- Yellow Rust (wheat): humidity > 80% + temp 10-20°C
- Powdery Mildew: humidity > 70% + temp 20-25°C + low rain
- Late Blight (potato): humidity > 90% + temp 15-22°C + rain
- White Rust (mustard): humidity > 85% + temp 10-20°C
"""

import requests
from typing import Dict, Any, Optional
from datetime import date, timedelta

# District → approximate lat/lon (covering the 10 states in our dataset)
DISTRICT_COORDS = {
    "Bharatpur": (27.22, 77.49),
    "Kanpur Nagar": (26.45, 80.35),
    "Patiala": (30.34, 76.39),
    "Jaipur": (26.92, 75.79),
    "Amravati": (20.93, 77.75),
    "Sirsa": (29.53, 75.02),
    "Ahmedabad": (23.02, 72.57),
    "Meerut": (28.98, 77.71),
    "Ujjain": (23.18, 75.79),
    "Sehore": (23.20, 77.08),
    "Kalaburagi": (17.33, 76.83),
    "Agra": (27.18, 78.02),
    "Akola": (20.71, 77.00),
    "Patna": (25.60, 85.10),
    "Karnal": (29.69, 76.99),
    "Bikaner": (28.02, 73.31),
    "Vijayapura": (16.83, 75.71),
    "Ludhiana": (30.90, 75.86),
    "Rohtak": (28.54, 76.34),
    "Sikar": (27.61, 75.14),
    "Lucknow": (26.85, 80.95),
    "Jalgaon": (21.01, 75.57),
    "Mehsana": (23.59, 72.37),
    "Indore": (22.72, 75.86),
    "Ratlam": (23.33, 75.04),
    "Nadia": (23.47, 88.56),
    "Hisar": (29.15, 75.72),
    "Muzaffarpur": (26.12, 85.39),
    "Varanasi": (25.32, 83.01),
    "Bathinda": (30.21, 74.95),
    "Amritsar": (31.63, 74.87),
    "Bardhaman": (23.23, 87.85),
    "Rajkot": (22.30, 70.80)
}

# Agronomic disease-weather correlation rules
DISEASE_RULES = {
    "wheat": [
        {
            "disease": "Yellow Rust (Puccinia striiformis)",
            "product": "Tilt 250 EC",
            "conditions": lambda w: w["humidity"] > 80
            and 10 <= w["temp_avg"] <= 20
            and w["stage"] == "tillering",
            "severity": "high",
        },
        {
            "disease": "Powdery Mildew (Blumeria graminis)",
            "product": "Score 250 EC",
            "conditions": lambda w: w["humidity"] > 70
            and 20 <= w["temp_avg"] <= 25
            and w["stage"] == "flowering",
            "severity": "medium",
        },
        {
            "disease": "Aphid Infestation",
            "product": "Actara 25 WG",
            "conditions": lambda w: w["temp_avg"] > 22 and w["humidity"] < 60,
            "severity": "medium",
        },
    ],
    "mustard": [
        {
            "disease": "White Rust (Albugo candida)",
            "product": "Score 250 EC",
            "conditions": lambda w: w["humidity"] > 85 and 10 <= w["temp_avg"] <= 20,
            "severity": "high",
        },
        {
            "disease": "Alternaria Blight",
            "product": "Score 250 EC",
            "conditions": lambda w: w["humidity"] > 75 and w["rainfall_mm"] > 2,
            "severity": "medium",
        },
    ],
    "chickpea": [
        {
            "disease": "Fusarium Wilt",
            "product": "Amistar 250 SC",
            "conditions": lambda w: w["temp_avg"] > 25 and w["humidity"] < 50,
            "severity": "high",
        },
        {
            "disease": "Pod Borer (Helicoverpa armigera)",
            "product": "Actara 25 WG",
            "conditions": lambda w: w["temp_avg"] > 20 and w["stage"] == "flowering",
            "severity": "high",
        },
    ],
    "potato": [
        {
            "disease": "Late Blight (Phytophthora infestans)",
            "product": "Kavach 75 WP",
            "conditions": lambda w: w["humidity"] > 90
            and 15 <= w["temp_avg"] <= 22
            and w["rainfall_mm"] > 5,
            "severity": "critical",
        },
        {
            "disease": "Early Blight (Alternaria solani)",
            "product": "Amistar 250 SC",
            "conditions": lambda w: w["humidity"] > 70 and w["temp_avg"] > 24,
            "severity": "medium",
        },
    ],
    "barley": [
        {
            "disease": "Powdery Mildew",
            "product": "Tilt 250 EC",
            "conditions": lambda w: w["humidity"] > 70 and 15 <= w["temp_avg"] <= 25,
            "severity": "medium",
        },
    ],
    "lentil": [
        {
            "disease": "Rust (Uromyces viciae-fabae)",
            "product": "Score 250 EC",
            "conditions": lambda w: w["humidity"] > 80 and 15 <= w["temp_avg"] <= 25,
            "severity": "high",
        },
    ],
}


class WeatherTriggerEngine:
    """Fetches real weather and determines dynamic pest/disease triggers."""

    def __init__(self):
        self._cache = {}

    def get_weather(self, district: str, ref_date: date = None) -> Dict[str, Any]:
        """Fetch real weather data from Open-Meteo for a district."""
        if ref_date is None:
            ref_date = date.today()

        cache_key = f"{district}_{ref_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        coords = DISTRICT_COORDS.get(district)
        if not coords:
            # Fallback: return plausible Rabi-season defaults for North India
            return {
                "district": district,
                "temp_max": 28.0,
                "temp_min": 12.0,
                "temp_avg": 20.0,
                "humidity": 65.0,
                "rainfall_mm": 0.0,
                "source": "default_estimate",
                "date": ref_date.isoformat(),
            }

        lat, lon = coords
        try:
            # Open-Meteo: free, no API key, real data
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&daily=temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean,"
                f"precipitation_sum&timezone=Asia/Kolkata&past_days=7&forecast_days=7"
            )
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()

            daily = data.get("daily", {})
            dates = daily.get("time", [])

            # Find today or closest date
            target = ref_date.isoformat()
            idx = dates.index(target) if target in dates else len(dates) // 2

            temp_max = daily.get("temperature_2m_max", [28])[idx]
            temp_min = daily.get("temperature_2m_min", [12])[idx]
            humidity = daily.get("relative_humidity_2m_mean", [65])[idx]
            rain = daily.get("precipitation_sum", [0])[idx]

            result = {
                "district": district,
                "latitude": lat,
                "longitude": lon,
                "temp_max": round(float(temp_max or 28), 1),
                "temp_min": round(float(temp_min or 12), 1),
                "temp_avg": round(float(((temp_max or 28) + (temp_min or 12)) / 2), 1),
                "humidity": round(float(humidity or 65), 1),
                "rainfall_mm": round(float(rain or 0), 1),
                "source": "open_meteo_live",
                "date": ref_date.isoformat(),
                "forecast_7d": {
                    "dates": dates,
                    "temp_max": [
                        round(float(t or 0), 1)
                        for t in daily.get("temperature_2m_max", [])
                    ],
                    "temp_min": [
                        round(float(t or 0), 1)
                        for t in daily.get("temperature_2m_min", [])
                    ],
                    "rain": [
                        round(float(r or 0), 1)
                        for r in daily.get("precipitation_sum", [])
                    ],
                },
            }
            self._cache[cache_key] = result
            return result

        except Exception as e:
            print(f"[WeatherEngine] API error for {district}: {e}")
            return {
                "district": district,
                "temp_max": 28.0,
                "temp_min": 12.0,
                "temp_avg": 20.0,
                "humidity": 65.0,
                "rainfall_mm": 0.0,
                "source": "fallback_on_error",
                "date": ref_date.isoformat(),
            }

    def evaluate_triggers(
        self, crop: str, stage: str, district: str, ref_date: date = None
    ) -> list:
        """Evaluate which disease/pest triggers are active for given conditions."""
        weather = self.get_weather(district, ref_date)
        weather["stage"] = stage

        rules = DISEASE_RULES.get(crop, [])
        active_triggers = []

        for rule in rules:
            try:
                if rule["conditions"](weather):
                    active_triggers.append(
                        {
                            "disease": rule["disease"],
                            "recommended_product": rule["product"],
                            "severity": rule["severity"],
                            "weather_evidence": {
                                "temp_avg": weather["temp_avg"],
                                "humidity": weather["humidity"],
                                "rainfall_mm": weather["rainfall_mm"],
                            },
                        }
                    )
            except Exception:
                continue

        return active_triggers
