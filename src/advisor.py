from typing import Tuple, Dict, Any, List
import json
import requests
from requests.exceptions import Timeout, ReadTimeout, RequestException, HTTPError
from src.config import Course, DEFAULT_OPENAI_MODEL, OPENAI_API_URL

def get_outfit_recommendation(
    temp_c: float,
    apparent: float,
    rain_mm: float,
    snow_mm: float,
    wind_ms: float,
    surface_score: int = 100,
    freeze_risk: bool = False,
) -> Tuple[str, str]:
    """기온, 체감온도, 강수량, 결빙 위험에 따른 상하의 복장 및 러닝화 추천 가이드를 반환합니다."""
    t = apparent if apparent is not None else temp_c
    parts_ko = []
    parts_en = []

    # 1) 상하의 복장 추천
    if t >= 27:
        parts_ko.append("👕 싱글렛/민소매 + 초경량 러닝 숏츠 (선크림·모자 필수)")
        parts_en.append("👕 Singlet & ultra-light shorts (Sunscreen & cap required)")
    elif t >= 20:
        parts_ko.append("👕 통풍 좋은 반팔 T셔츠 + 러닝 숏츠")
        parts_en.append("👕 Breathable short-sleeve T-shirt & running shorts")
    elif t >= 13:
        parts_ko.append("👕 반팔 또는 얇은 긴팔 + 러닝 숏츠 (러닝 최적 복장)")
        parts_en.append("👕 Short/thin long sleeves & shorts (Optimal running gear)")
    elif t >= 7:
        parts_ko.append("👕 긴팔 T셔츠 + 러닝 타이츠/팬츠 (얇은 바람막이 지참 권장)")
        parts_en.append("👕 Long sleeves & tights (Light windbreaker recommended)")
    elif t >= 1:
        parts_ko.append("👕 기모 긴팔 + 방풍 자켓 + 롱타이츠 (얇은 장갑/모자)")
        parts_en.append("👕 Thermal long sleeves, windproof jacket, tights, gloves & beanie")
    else:
        parts_ko.append("👕 방한 자켓 + 방풍 타이츠 + 귀마개·장갑·넥워머 필수")
        parts_en.append("👕 Thermal jacket, windproof tights, gloves, beanie & neck warmer")

    # 2) 상황별 러닝화(Shoes) 및 전용 용품 추천
    if freeze_risk:
        parts_ko.append("👟 추천 러닝화: 트레일러닝화(Trail shoes) 또는 아이젠/접지 강화화 (카본 레이싱화 절대 금지 🚨)")
        parts_en.append("👟 Shoes: Trail running shoes or high-traction shoes (AVOID carbon racing shoes 🚨)")
    elif rain_mm >= 4.0 or surface_score <= 30:
        parts_ko.append("👟 추천 러닝화: 방수/고어텍스(GORE-TEX) 러닝화 또는 젖어도 되는 데일리 트레이너 + 챙모자")
        parts_en.append("👟 Shoes: Waterproof GORE-TEX or daily trainers with wet-grip outsoles + cap")
    elif rain_mm > 0.2 or surface_score <= 70:
        parts_ko.append("👟 추천 러닝화: 아웃솔 접지력(Grip) 뛰어난 데일리 러닝화 (미끄러운 우레탄/보도블럭 주의)")
        parts_en.append("👟 Shoes: Daily trainers with high-traction rubber outsole (Caution on wet pavements)")
    elif t <= 2:
        parts_ko.append("👟 추천 러닝화: 방풍/도톰한 어퍼 러닝화 + 도톰한 스포츠 양말")
        parts_en.append("👟 Shoes: Windproof upper trainers + warm running socks")
    else:
        parts_ko.append("👟 추천 러닝화: 일반 데일리 쿠션화, 레이싱화, 카본화 자유 착용")
        parts_en.append("👟 Shoes: Daily cushion trainers, carbon-plated racing shoes, or light trainers")

    return " | ".join(parts_ko), " | ".join(parts_en)


def get_pace_and_running_tip(
    temp_c: float,
    apparent: float,
    humidity: float,
    wind_ms: float,
    air_score: int,
    surface_score: int,
    freeze_risk: bool = False,
    rain_mm: float = 0.0,
) -> Tuple[str, str]:
    """강수량, 빙판 위험, 무더위, 한파 등을 정밀 반영한 페이스 및 안전 가이드를 제공합니다."""
    tips_ko = []
    tips_en = []

    t = apparent if apparent is not None else temp_c

    # 1) 위험 극단 상황 (러닝 자제/금지 안내)
    if freeze_risk:
        tips_ko.append("🚨 [야외 러닝 금지] 영하의 날씨가 지속되어 잔설이 블랙아이스/빙판으로 변했습니다. 낙상 및 인대 손상 위험이 매우 높으니 야외 러닝을 금지하고 실내 트레드밀/휴식을 강력히 권장합니다.")
        tips_en.append("🚨 [Outdoor Run Prohibited] Persistent sub-zero temperatures turned snow into black ice. Extremely high fall risk; indoor treadmill exercise is strongly recommended.")
        return " ".join(tips_ko), " ".join(tips_en)

    if rain_mm >= 8.0 or surface_score <= 20:
        tips_ko.append("🚨 [야외 러닝 자제] 폭우 및 도로 물웅덩이로 인해 수막현상과 슬립 위험이 큽니다. 강도 높은 훈련을 중단하고 실내 운동을 권장합니다.")
        tips_en.append("🚨 [Avoid Outdoor Run] Heavy rain and puddles create high hydroplaning and slip hazards. Indoor workouts recommended.")
        return " ".join(tips_ko), " ".join(tips_en)

    # 2) 일반 기온 및 습도 조건 페이스 팁
    if t >= 28 or (t >= 23 and humidity >= 75):
        tips_ko.append("☀️ [무더위/고습도] 체온 조절이 힘든 고습도 기온입니다. 목표 페이스보다 20~30초 낮추고 15분마다 이온음료 수분을 필수 섭취하세요.")
        tips_en.append("☀️ [High Heat & Humidity] Lower target pace by 20-30s and drink electrolyte fluids every 15 minutes.")
    elif t <= -5:
        tips_ko.append("❄️ [한파 주의] 강한 한기로 심박수가 급상승합니다. 웜업을 15분 이상 충분히 하고 호흡 시 넥워머로 차가운 공기를 가려주세요.")
        tips_en.append("❄️ [Severe Cold] Warm up thoroughly for 15+ minutes and use a neck warmer to shield lungs from freezing air.")
    else:
        tips_ko.append("🏃‍♂️ [쾌적 기온] 체온 유지가 용이한 좋은 러닝 환경입니다. 충분한 워밍업 후 주행 목표 페이스 유지를 시도해보세요.")
        tips_en.append("🏃‍♂️ [Optimal Temp] Great running environment. Maintain your target pace after a proper warmup.")

    # 3) 노면 및 바람 상태
    if surface_score <= 50:
        tips_ko.append("☔ 노면이 젖어있으므로 코너링 시 속도를 줄이고 내리막/만곡 보도블럭 구간에서 발목 착지에 유의하세요.")
        tips_en.append("☔ Wet surface. Slow down on turns and exercise ankle care on slippery downhills.")
    elif wind_ms >= 5.5:
        tips_ko.append("💨 맞바람이 강하므로 시선과 상체를 약간 낮추고, 크루원들과 그룹 주행 시 팩 후미에서 체력을 안배하세요.")
        tips_en.append("💨 Strong headwinds. Lean slightly forward and draft behind your running pack to save energy.")

    if air_score <= 55:
        tips_ko.append("😷 공기질 나쁨 수준입니다. 대량의 호흡이 필요한 인터벌/빌드업 훈련은 자제하는 편이 좋습니다.")
        tips_en.append("😷 Poor air quality. Avoid high-intensity interval workouts causing heavy breathing.")

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
