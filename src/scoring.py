import math
from datetime import datetime
from typing import Dict, Any, Optional, List
from src.config import Course, KST
from src.advisor import get_outfit_recommendation, get_pace_and_running_tip

def parse_iso_datetime(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KST)
    return dt

def calc_apparent_temperature(temp_c: float, wind_speed_ms: float, humidity: float) -> float:
    wind_kmh = wind_speed_ms * 3.6
    if temp_c <= 10 and wind_kmh > 4.8:
        v16 = math.pow(wind_kmh, 0.16)
        return 13.12 + 0.6215 * temp_c - 11.37 * v16 + 0.3965 * temp_c * v16
    if temp_c >= 27 and humidity >= 40:
        t_f = temp_c * 9 / 5 + 32
        hi_f = (
            -42.379 + 2.04901523 * t_f + 10.14333127 * humidity
            - 0.22475541 * t_f * humidity - 0.00683783 * t_f * t_f
            - 0.05481717 * humidity * humidity + 0.00122874 * t_f * t_f * humidity
            + 0.00085282 * t_f * humidity * humidity - 0.00000199 * t_f * t_f * humidity * humidity
        )
        return (hi_f - 32) * 5 / 9
    if temp_c >= 22 and humidity >= 65:
        return temp_c + ((humidity - 60) * 0.08)
    return temp_c

def estimate_snow_melt_rate_mm_h(temp_c: float, rain_mm_h: float) -> float:
    if temp_c <= 0: base_melt = 0.0
    elif temp_c <= 2: base_melt = 0.3
    elif temp_c <= 5: base_melt = 0.8
    else: base_melt = 1.5
    return base_melt + (max(0.0, rain_mm_h) * 0.2)

def estimate_snow_memory_mm(
    prev_snow_memory_mm: float, dt_h: float, current_snow_mm_h: float, temp_c: float, rain_mm_h: float
) -> float:
    safe_prev = max(0.0, min(30.0, prev_snow_memory_mm))
    safe_dt = max(0.0, min(12.0, dt_h))
    snow_in_mm = max(0.0, current_snow_mm_h) * safe_dt
    melt_mm = estimate_snow_melt_rate_mm_h(temp_c, rain_mm_h) * safe_dt
    return max(0.0, min(30.0, safe_prev + snow_in_mm - melt_mm))

def summarize_course_weather(
    course: Course,
    raw_weather: Dict[str, Any],
    raw_air: Optional[Dict[str, Any]] = None,
    prev_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    current = raw_weather["current"]
    hourly = raw_weather["hourly"]

    risk_flags_ko: List[str] = []
    risk_flags_en: List[str] = []
    hard_caps: List[int] = []
    penalty_factor = 1.0

    current_temp = float(current["temperature_2m"])
    humidity = float(current.get("relative_humidity_2m", 60.0) or 60.0)
    current_rain = float(current.get("rain", 0.0))
    current_precip = float(current.get("precipitation", 0.0))
    current_snow = max(current_precip - current_rain, 0.0)
    raw_wind_speed_kmh = float(current["wind_speed_10m"])
    wind_speed = raw_wind_speed_kmh / 3.6
    wind_dir = float(current["wind_direction_10m"])

    apparent = calc_apparent_temperature(current_temp, wind_speed, humidity)

    # 1) 노면 & 강수
    recent_rain = float(sum(hourly.get("rain", []) or []))
    recent_precip = float(sum(hourly.get("precipitation", []) or []))
    recent_snow = max(recent_precip - recent_rain, 0.0)

    snow_memory_mm = 0.0
    if prev_state:
        try:
            snow_memory_mm = float(prev_state.get("snow_memory_mm", 0.0) or 0.0)
        except (TypeError, ValueError):
            snow_memory_mm = 0.0

    if recent_precip == 0 and current_precip == 0:
        surface_score = 100
        wet_badge = {"level": "good", "text_ko": "노면 건조", "text_en": "Dry surface"}
        wet_tag_ko, wet_tag_en = "노면 건조", "Dry surface"
    else:
        surface_score = 60
        wet_badge = {"level": "wet", "text_ko": "젖은 노면", "text_en": "Wet surface"}
        wet_tag_ko, wet_tag_en = "젖은 노면", "Wet surface"

    # 2) 기온 점수
    if 5 <= apparent <= 18:
        temp_score = 100
        temp_tag_ko, temp_tag_en = "러닝 최적 기온", "Optimal temp"
    elif 0 <= apparent < 5 or 18 < apparent <= 24:
        temp_score = 80
        temp_tag_ko, temp_tag_en = "쾌적함", "Comfortable"
    elif apparent > 24:
        temp_score = 50
        temp_tag_ko, temp_tag_en = "조금 더움", "Warm"
    else:
        temp_score = 40
        temp_tag_ko, temp_tag_en = "쌀쌀함", "Chilly"

    # 3) 바람 점수
    if wind_speed < 3.0:
        wind_score = 100
        wind_tag_ko, wind_tag_en = "약한 바람", "Light breeze"
    elif wind_speed < 6.0:
        wind_score = 70
        wind_tag_ko, wind_tag_en = "다소 바람", "Moderate wind"
    else:
        wind_score = 40
        wind_tag_ko, wind_tag_en = "강한 바람", "Strong wind"

    # 4) 공기질
    pm10 = None
    pm25 = None
    if raw_air and "current" in raw_air:
        air_curr = raw_air["current"]
        pm10 = float(air_curr.get("pm10")) if air_curr.get("pm10") is not None else None
        pm25 = float(air_curr.get("pm2_5")) if air_curr.get("pm2_5") is not None else None

    score_pm10 = 100 if (pm10 is None or pm10 <= 30) else (80 if pm10 <= 80 else 50)
    score_pm25 = 100 if (pm25 is None or pm25 <= 15) else (80 if pm25 <= 35 else 50)
    air_score = min(score_pm10, score_pm25)
    air_tag_ko, air_tag_en = ("공기질 좋음", "Good air") if air_score >= 80 else ("공기질 보통", "Moderate air")

    # 종합점수
    base_score = (temp_score * 0.50 + wind_score * 0.25 + surface_score * 0.25)
    factor_air = 1.0 if air_score >= 80 else (0.9 if air_score >= 60 else 0.7)
    run_score = int(round(max(0, min(100, base_score * factor_air))))

    outfit_ko, outfit_en = get_outfit_recommendation(current_temp, apparent, current_rain, current_snow, wind_speed)
    pace_tip_ko, pace_tip_en = get_pace_and_running_tip(current_temp, apparent, humidity, wind_speed, air_score, surface_score)

    advice_short_ko = "러닝하기 아주 좋은 컨디션입니다 😄" if run_score >= 80 else "주의하면서 뛰기 좋은 컨디션입니다 🙂"
    advice_short_en = "Great running condition 😄" if run_score >= 80 else "Decent running condition 🙂"

    tags_ko = [temp_tag_ko, wind_tag_ko, wet_tag_ko, air_tag_ko]
    tags_en = [temp_tag_en, wind_tag_en, wet_tag_en, air_tag_en]

    return {
        "id": course.id,
        "name_ko": course.name_ko,
        "name_en": course.name_en,
        "name": course.name_ko,
        "location_ko": getattr(course, "location_ko", "수원/경기 코스"),
        "location_en": getattr(course, "location_en", "Suwon Area"),
        "updated_at": current["time"],
        "lat": course.lat,
        "lon": course.lon,
        "temperature": current_temp,
        "apparent_temperature": round(apparent, 1),
        "humidity": round(humidity, 1),
        "wind_speed": wind_speed,
        "wind_direction": wind_dir,
        "rain_now": current_rain,
        "snow_now": current_snow,
        "snow_memory_mm": round(snow_memory_mm, 2),
        "freeze_surface_risk": False,
        "forecast_rain_3h": recent_rain,
        "forecast_snow_3h": recent_snow,
        "recent_rain_3h": recent_rain,
        "recent_snow_3h": recent_snow,
        "wet_badge": wet_badge,
        "run_score": run_score,
        "temp_score": temp_score,
        "wind_score": wind_score,
        "wet_score": surface_score,
        "surface_score": surface_score,
        "air_score": air_score,
        "outfit_ko": outfit_ko,
        "outfit_en": outfit_en,
        "pace_tip_ko": pace_tip_ko,
        "pace_tip_en": pace_tip_en,
        "risk_flags_ko": risk_flags_ko,
        "risk_flags_en": risk_flags_en,
        "tags_ko": tags_ko,
        "tags_en": tags_en,
        "advice_short_ko": advice_short_ko,
        "advice_short_en": advice_short_en,
        "pm10": pm10,
        "pm25": pm25,
    }
