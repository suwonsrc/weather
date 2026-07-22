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

    current_temp = float(current["temperature_2m"])
    humidity = float(current.get("relative_humidity_2m", 60.0) or 60.0)
    current_rain = float(current.get("rain", 0.0))
    current_precip = float(current.get("precipitation", 0.0))
    current_snow = max(current_precip - current_rain, 0.0)
    raw_wind_speed_kmh = float(current["wind_speed_10m"])
    wind_speed = raw_wind_speed_kmh / 3.6
    wind_dir = float(current["wind_direction_10m"])

    apparent = calc_apparent_temperature(current_temp, wind_speed, humidity)

    # 강수 & 잔설 메모리 추정
    recent_rain = float(sum(hourly.get("rain", []) or []))
    recent_precip = float(sum(hourly.get("precipitation", []) or []))
    recent_snow = max(recent_precip - recent_rain, 0.0)

    prev_snow_mm = 0.0
    if prev_state:
        try:
            prev_snow_mm = float(prev_state.get("snow_memory_mm", 0.0) or 0.0)
        except (TypeError, ValueError):
            prev_snow_mm = 0.0

    snow_memory_mm = estimate_snow_memory_mm(prev_snow_mm, 0.5, current_snow, current_temp, current_rain)
    freeze_surface_risk = (snow_memory_mm >= 0.8 or current_snow > 0) and (current_temp <= 0.0)

    # 1) 습도/예보강수/노면 지표 태그 (간결 표준화)
    if freeze_surface_risk:
        surface_score = 10
        hard_caps.append(15)
        wet_badge = {"level": "bad", "text_ko": "결빙", "text_en": "Icy"}
        wet_tag_ko, wet_tag_en = "결빙", "Icy"
    elif snow_memory_mm >= 0.8 or current_snow > 0:
        surface_score = 45
        wet_badge = {"level": "wet", "text_ko": "눈슬러시", "text_en": "Slush"}
        wet_tag_ko, wet_tag_en = "눈슬러시", "Slush"
    elif current_rain >= 8.0 or recent_rain >= 15.0:
        surface_score = 15
        hard_caps.append(20)
        wet_badge = {"level": "bad", "text_ko": "폭우", "text_en": "Heavy Rain"}
        wet_tag_ko, wet_tag_en = "폭우", "Heavy Rain"
    elif current_rain >= 3.0 or recent_rain >= 6.0:
        surface_score = 35
        hard_caps.append(40)
        wet_badge = {"level": "bad", "text_ko": "노면젖음", "text_en": "Wet"}
        wet_tag_ko, wet_tag_en = "노면젖음", "Wet"
    elif current_rain > 0 or recent_rain > 0:
        surface_score = 65
        wet_badge = {"level": "wet", "text_ko": "살짝젖음", "text_en": "Damp"}
        wet_tag_ko, wet_tag_en = "살짝젖음", "Damp"
    else:
        surface_score = 100
        wet_badge = {"level": "good", "text_ko": "건조", "text_en": "Dry"}
        wet_tag_ko, wet_tag_en = "건조", "Dry"

    # 2) 기온 지표 태그 (간결 표준화: 최적, 쾌적, 더움, 찜통, 폭염, 쌀쌀, 혹한)
    if apparent <= -12:
        temp_score = 20
        hard_caps.append(20)
        temp_tag_ko, temp_tag_en = "혹한", "Severe Cold"
    elif apparent >= 33:
        temp_score = 20
        hard_caps.append(20)
        temp_tag_ko, temp_tag_en = "폭염", "Extreme Heat"
    elif apparent >= 28 and humidity >= 85:
        temp_score = 30
        hard_caps.append(50)
        temp_tag_ko, temp_tag_en = "찜통", "Humid Heat"
    elif apparent > 24:
        temp_score = 50
        temp_tag_ko, temp_tag_en = "더움", "Warm"
    elif 5 <= apparent <= 18:
        temp_score = 100
        temp_tag_ko, temp_tag_en = "최적", "Optimal"
    elif 0 <= apparent < 5 or 18 < apparent <= 24:
        temp_score = 80
        temp_tag_ko, temp_tag_en = "쾌적", "Comfortable"
    else:
        temp_score = 40
        temp_tag_ko, temp_tag_en = "쌀쌀", "Chilly"

    # 3) 바람 지표 태그 (간결 표준화: 약한바람, 다소바람, 강풍)
    if wind_speed < 3.0:
        wind_score = 100
        wind_tag_ko, wind_tag_en = "약한바람", "Light Breeze"
    elif wind_speed < 6.0:
        wind_score = 70
        wind_tag_ko, wind_tag_en = "다소바람", "Moderate Wind"
    else:
        wind_score = 40
        wind_tag_ko, wind_tag_en = "강풍", "Strong Wind"

    # 4) 공기질 지표 태그 (간결 표준화: 공기좋음, 공기보통, 공기나쁨, 황사경보)
    pm10 = None
    pm25 = None
    if raw_air and "current" in raw_air:
        air_curr = raw_air["current"]
        pm10 = float(air_curr.get("pm10")) if air_curr.get("pm10") is not None else None
        pm25 = float(air_curr.get("pm2_5")) if air_curr.get("pm2_5") is not None else None

    if (pm10 is not None and pm10 > 150) or (pm25 is not None and pm25 > 75):
        air_score = 15
        hard_caps.append(25)
        air_tag_ko, air_tag_en = "황사경보", "Dust Warning"
    elif (pm10 is not None and pm10 > 80) or (pm25 is not None and pm25 > 35):
        air_score = 40
        hard_caps.append(50)
        air_tag_ko, air_tag_en = "공기나쁨", "Bad Air"
    elif (pm10 is not None and pm10 > 30) or (pm25 is not None and pm25 > 15):
        air_score = 75
        air_tag_ko, air_tag_en = "공기보통", "Moderate Air"
    else:
        air_score = 100
        air_tag_ko, air_tag_en = "공기좋음", "Good Air"

    # 종합점수 산출 & 안전 상한선(hard cap) 적용
    base_score = (temp_score * 0.45 + wind_score * 0.25 + surface_score * 0.30)
    factor_air = 1.0 if air_score >= 80 else (0.75 if air_score >= 40 else 0.4)
    run_score = base_score * factor_air

    if hard_caps:
        run_score = min(run_score, min(hard_caps))

    dt_now = parse_iso_datetime(current.get("time")) or datetime.now(tz=KST)
    is_night = dt_now.hour >= 19 or dt_now.hour < 6

    run_score = int(round(max(0, min(100, run_score))))

    if run_score >= 80:
        run_grade = "A"
    elif run_score >= 65:
        run_grade = "B"
    elif run_score >= 50:
        run_grade = "C"
    elif run_score >= 35:
        run_grade = "D"
    else:
        run_grade = "E"

    outfit_ko, outfit_en = get_outfit_recommendation(
        current_temp, apparent, current_rain, current_snow, wind_speed, surface_score, freeze_surface_risk, is_night=is_night
    )
    pace_tip_ko, pace_tip_en = get_pace_and_running_tip(
        current_temp, apparent, humidity, wind_speed, air_score, surface_score, freeze_surface_risk, current_rain, is_night=is_night
    )

    if freeze_surface_risk:
        advice_short_ko = "🚨 빙판길 결빙 위험 - 야외 러닝 금지 및 실내 운동 권장!"
        advice_short_en = "🚨 Ice hazard! Outdoor running prohibited."
    elif air_score <= 20:
        advice_short_ko = "🚨 황사/미세먼지 매우나쁨 - 야외 러닝 금지 및 실내 운동 권장!"
        advice_short_en = "🚨 Severe dust hazard! Indoor running recommended."
    elif run_score >= 80:
        advice_short_ko = "러닝하기 아주 좋은 컨디션입니다 😄"
        advice_short_en = "Great running condition 😄"
    elif run_score >= 50:
        advice_short_ko = "주의하면서 뛰기 좋은 컨디션입니다 🙂"
        advice_short_en = "Decent running condition 🙂"
    else:
        advice_short_ko = "🚨 기상/공기질 불량 - 야외 러닝을 자제하고 실내 운동을 권장합니다."
        advice_short_en = "🚨 Poor conditions! Reduce intensity or train indoors."

    # 상단 4개 지표(기온, 바람, 습도/강수, 공기질)와 1:1 대응되는 깔끔한 4개 표준화 태그
    tags_ko = [temp_tag_ko, wind_tag_ko, wet_tag_ko, air_tag_ko]
    tags_en = [temp_tag_en, wind_tag_en, wet_tag_en, air_tag_en]

    return {
        "id": course.id,
        "name_ko": course.name_ko,
        "name_en": course.name_en,
        "name": course.name_ko,
        "location_ko": getattr(course, "location_ko", "수원시 코스"),
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
        "freeze_surface_risk": freeze_surface_risk,
        "forecast_rain_3h": recent_rain,
        "forecast_snow_3h": recent_snow,
        "recent_rain_3h": recent_rain,
        "recent_snow_3h": recent_snow,
        "wet_badge": wet_badge,
        "run_score": run_score,
        "run_grade": run_grade,
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
