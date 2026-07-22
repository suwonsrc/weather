from typing import Tuple, Dict, Any, List
import json
import requests
from requests.exceptions import Timeout, ReadTimeout, RequestException, HTTPError
from src.config import Course, DEFAULT_OPENAI_MODEL, OPENAI_API_URL

def get_outfit_recommendation(
    temp_c: float, apparent: float, rain_mm: float, snow_mm: float, wind_ms: float
) -> Tuple[str, str]:
    """기온, 체감온도, 강수량에 따른 러너 복장 가이드를 반환합니다."""
    t = apparent if apparent is not None else temp_c
    parts_ko = []
    parts_en = []

    if t >= 27:
        parts_ko.append("싱글렛/민소매 + 초경량 러닝 숏츠 (선크림·모자 필수)")
        parts_en.append("Singlet & ultra-light shorts (Sunscreen & cap required)")
    elif t >= 20:
        parts_ko.append("통풍 좋은 반팔 T셔츠 + 러닝 숏츠")
        parts_en.append("Breathable short-sleeve T-shirt & running shorts")
    elif t >= 13:
        parts_ko.append("반팔 또는 얇은 긴팔 + 러닝 숏츠 (러닝 최적 복장)")
        parts_en.append("Short/thin long sleeves & shorts (Optimal running gear)")
    elif t >= 7:
        parts_ko.append("긴팔 T셔츠 + 러닝 타이츠/팬츠 (얇은 바람막이 지참 권장)")
        parts_en.append("Long sleeves & tights (Light windbreaker recommended)")
    elif t >= 1:
        parts_ko.append("기모 긴팔 + 방풍 자켓 + 롱타이츠 (얇은 장갑/모자)")
        parts_en.append("Thermal long sleeves, windproof jacket, tights, gloves & beanie")
    else:
        parts_ko.append("방한 자켓 + 방풍 타이츠 + 귀마개·장갑·넥워머 필수")
        parts_en.append("Thermal jacket, windproof tights, gloves, beanie & neck warmer")

    if rain_mm > 0.5:
        parts_ko.append("챙모자 / 방수 자켓 착용 추천")
        parts_en.append("Cap / waterproof jacket recommended")
    if snow_mm > 0.2:
        parts_ko.append("접지력 뛰어난 러닝화(트레일화)")
        parts_en.append("Running shoes with high grip (Trail shoes)")

    return " | ".join(parts_ko), " | ".join(parts_en)


def get_pace_and_running_tip(
    temp_c: float,
    apparent: float,
    humidity: float,
    wind_ms: float,
    air_score: int,
    surface_score: int,
) -> Tuple[str, str]:
    """기상 조건에 맞춰 러닝 페이스 및 수분 섭취, 안전 팁을 제공합니다."""
    tips_ko = []
    tips_en = []

    t = apparent if apparent is not None else temp_c

    if t >= 26 or (t >= 22 and humidity >= 70):
        tips_ko.append(
            "습도와 기온이 높아 땀 증발이 느립니다. 기존 목표 페이스보다 15~30초 낮추고 15분마다 수분을 섭취하세요."
        )
        tips_en.append(
            "High heat and humidity slow sweat evaporation. Lower target pace by 15-30s and hydrate every 15m."
        )
    elif t <= 0:
        tips_ko.append(
            "한기로 인해 심박수가 빠르게 상승합니다. 웜업을 충분히(10~15분) 하고 초반 급가속을 피하세요."
        )
        tips_en.append(
            "Cold air elevates heart rate quickly. Warm up thoroughly (10-15m) and avoid sudden sprints."
        )
    else:
        tips_ko.append(
            "체온 조절이 용이한 기온입니다. 충분한 워밍업 후 목표 페이스 유지를 시도해보세요."
        )
        tips_en.append(
            "Great temperature for body temp regulation. Maintain target pace after a good warmup."
        )

    if surface_score <= 60:
        tips_ko.append("노면이 젖어있으므로 코너링 및 보도블럭·만곡 구간에서 슬립에 주의하세요.")
        tips_en.append("Surface is wet. Take extra caution on cornering and wet pavements.")
    elif wind_ms >= 5.0:
        tips_ko.append("강풍 구간에서는 맞바람 시 상체를 약간 낮추고 그룹 러닝 시 팩 후미에서 체력을 아끼세요.")
        tips_en.append("In strong winds, lean forward into headwinds or draft behind a running pack.")

    if air_score <= 55:
        tips_ko.append("공기질 나쁨 수준입니다. 호흡수가 급증하는 고강도 훈련(인터벌)은 자제하는 것이 좋습니다.")
        tips_en.append("Poor air quality. Avoid high-intensity interval workouts causing heavy breathing.")

    return " ".join(tips_ko), " ".join(tips_en)


def call_chatgpt_coach(
    course: Course,
    summary: Dict[str, Any],
    raw_weather: Dict[str, Any],
    raw_air: Any,
    api_key: str,
    model: str = DEFAULT_OPENAI_MODEL,
    timeout: int = 30,
) -> Any:
    """OpenAI API를 통해 러닝 코치 생성"""
    if not api_key:
        return None

    payload = {
        "course": {"id": course.id, "name_ko": course.name_ko, "name_en": course.name_en},
        "summary": summary,
    }
    messages = [
        {"role": "system", "content": "You are a concise running coach fluent in Korean and English."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        resp = requests.post(OPENAI_API_URL, headers=headers, json={"model": model, "messages": messages}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[WARN] Coach call failed: {e}")
        return None
