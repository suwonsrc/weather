import argparse
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import quote_plus

import requests

from requests.exceptions import Timeout, ReadTimeout, RequestException, HTTPError

# === 1. 러닝 코스 정의 ===


@dataclass
class Course:
    id: str
    name_ko: str
    name_en: str
    lat: float
    lon: float


COURSES: List[Course] = [
    Course(
        id="seoho-park",
        name_ko="서호공원",
        name_en="Seoho Park",
        lat=37.280325,
        lon=126.990396,
    ),
    Course(
        id="youth-center",
        name_ko="청소년문화센터",
        name_en="Youth Culture Center",
        lat=37.274248,
        lon=127.034519,
    ),
    Course(
        id="gwanggyo-lake-park",
        name_ko="광교호수공원",
        name_en="Gwanggyo Lake Park",
        lat=37.283439,
        lon=127.065989,
    ),
    Course(
        id="skku",
        name_ko="성균관대학교",
        name_en="Sungkyunkwan Univ. (Suwon)",
        lat=37.293788,
        lon=126.974365,
    ),
    Course(
        id="woncheon-stream-sindong",
        name_ko="원천리천(신동)",
        name_en="Woncheon Stream (Sindong)",
        lat=37.248469,
        lon=127.041965,
    ),
    Course(
        id="paldalsan-hwaseong",
        name_ko="팔달산(수원화성, 행궁동)",
        name_en="Paldalsan Fortress Area",
        lat=37.277614,
        lon=127.010650,
    ),
    Course(
        id="suwon-stream",
        name_ko="수원천",
        name_en="Suwoncheon Stream",
        lat=37.266571,
        lon=127.015022,
    ),
    Course(
        id="gwanggyo-mountain",
        name_ko="광교산",
        name_en="Gwanggyo Mountain",
        lat=37.328633,
        lon=127.038172,
    ),
    Course(
        id="suwon-worldcup",
        name_ko="수원월드컵경기장",
        name_en="Suwon World Cup Stadium",
        lat=37.286545,
        lon=127.036871,
    ),
    Course(
        id="dongtan-yeoul-park",
        name_ko="동탄여울공원",
        name_en="Dongtan Yeoul Park",
        lat=37.198689,
        lon=127.086609,
    ),
    Course(
        id="yeongheung-forest-park",
        name_ko="영흥숲공원",
        name_en="Yeongheung Forest Park",
        lat=37.261067,
        lon=127.070470,
    ),
    Course(
        id="majung-park",
        name_ko="마중공원",
        name_en="Majung Park",
        lat=37.236832,
        lon=127.020592,
    ),
]

# === Provider 정의 & 상수 ===

DEFAULT_PROVIDER = "kma"
SUPPORTED_PROVIDERS = ("kma",)
KST = timezone(timedelta(hours=9))

KMA_ULTRA_NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
KMA_ULTRA_FCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst"
KMA_AIR_QUALITY_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
DEFAULT_KMA_AIR_SIDO = os.getenv("KMA_AIR_SIDO_NAME", "경기도")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")


# === 2. 기상청(KMA) 초단기/초단기예보 호출 ===

def kst_now() -> datetime:
    return datetime.now(tz=timezone.utc).astimezone(KST)


def kma_base_datetime(now_kst: Optional[datetime] = None) -> Tuple[str, str]:
    """
    기상청 초단기 API는 발표시각 이후 약 30~40분 뒤에 최신 값을 제공합니다.
    현재 시각에서 40분을 뺀 뒤, 가까운 30분 단위로 내림하여 base_date/base_time을 계산합니다.
    """
    now = now_kst or kst_now()
    base_dt = now - timedelta(minutes=40)
    base_dt = base_dt.replace(
        minute=(base_dt.minute // 30) * 30,
        second=0,
        microsecond=0,
    )
    return base_dt.strftime("%Y%m%d"), base_dt.strftime("%H%M")


def latlon_to_kma_xy(lat: float, lon: float) -> Tuple[int, int]:
    """
    위/경도를 기상청 격자(nx, ny)로 변환합니다.
    표준 기상청 격자 변환(DFS) 공식 사용.
    """
    RE = 6371.00877  # 지구 반경(km)
    GRID = 5.0       # 격자 간격(km)
    SLAT1 = 30.0
    SLAT2 = 60.0
    OLON = 126.0
    OLAT = 38.0
    XO = 43
    YO = 136

    DEGRAD = math.pi / 180.0

    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)
    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    x = int(ra * math.sin(theta) + XO + 1.5)
    y = int(ro - ra * math.cos(theta) + YO + 1.5)
    return x, y


def parse_precip_value(raw: Any) -> float:
    """
    기상청 RN1/PCP 값은 숫자 또는 '강수없음', '1mm 미만' 형태가 올 수 있으므로 보정합니다.
    """
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip()
    if not text or text == "강수없음":
        return 0.0

    cleaned = text.replace("mm", "").replace(" ", "")
    cleaned = cleaned.replace("미만", "")
    if cleaned == "":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_pm_value(raw: Any) -> Optional[float]:
    """PM10/PM2.5 값 문자열에서 숫자만 추출해 float로 변환합니다."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def calc_apparent_temperature(temp_c: float, wind_speed_ms: float, humidity: float) -> float:
    """
    기상청 실황(체감온도 제공 안 함) 값을 이용해 체감온도를 계산합니다.
    - 추울 때: 캐나다 윈드칠 공식
    - 더울 때: NOAA Heat Index 및 고습도 체감 보정
    """
    wind_kmh = wind_speed_ms * 3.6

    if temp_c <= 10 and wind_kmh > 4.8:
        v16 = math.pow(wind_kmh, 0.16)
        return 13.12 + 0.6215 * temp_c - 11.37 * v16 + 0.3965 * temp_c * v16

    if temp_c >= 27 and humidity >= 40:
        t_f = temp_c * 9 / 5 + 32
        hi_f = (
            -42.379
            + 2.04901523 * t_f
            + 10.14333127 * humidity
            - 0.22475541 * t_f * humidity
            - 0.00683783 * t_f * t_f
            - 0.05481717 * humidity * humidity
            + 0.00122874 * t_f * t_f * humidity
            + 0.00085282 * t_f * humidity * humidity
            - 0.00000199 * t_f * t_f * humidity * humidity
        )
        return (hi_f - 32) * 5 / 9

    # 22도 이상이면서 습도가 높은 한국 여름철 날씨 보정
    if temp_c >= 22 and humidity >= 65:
        return temp_c + ((humidity - 60) * 0.08)

    return temp_c


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


def build_kma_url(base_url: str, service_key: str) -> str:
    """
    serviceKey는 이미 URL-encoded된 문자열을 그대로 써야 하므로,
    인코딩 여부를 감지해 중복 인코딩을 방지합니다.
    """
    if "%" in service_key:
        encoded_key = service_key
    else:
        encoded_key = quote_plus(service_key)
    return f"{base_url}?serviceKey={encoded_key}"


def parse_iso_datetime(raw: Any) -> Optional[datetime]:
    """ISO datetime 문자열을 datetime으로 파싱합니다."""
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


def estimate_snow_melt_rate_mm_h(temp_c: float, rain_mm_h: float) -> float:
    """
    기온/강수량을 기반으로 시간당 눈 융해량(mm/h)을 단순 추정합니다.
    - 영하에서는 거의 녹지 않는다고 가정
    - 영상으로 갈수록 융해율 증가
    - 비가 오면 융해를 가속
    """
    if temp_c <= 0:
        base_melt = 0.0
    elif temp_c <= 2:
        base_melt = 0.3
    elif temp_c <= 5:
        base_melt = 0.8
    else:
        base_melt = 1.5
    return base_melt + (max(0.0, rain_mm_h) * 0.2)


def estimate_snow_memory_mm(
    prev_snow_memory_mm: float,
    dt_h: float,
    current_snow_mm_h: float,
    temp_c: float,
    rain_mm_h: float,
) -> float:
    """
    잔설 추정치(mm) = 이전 잔설 + (현재 눈 유입) - (융해량)
    """
    safe_prev = max(0.0, min(30.0, prev_snow_memory_mm))
    safe_dt = max(0.0, min(12.0, dt_h))
    snow_in_mm = max(0.0, current_snow_mm_h) * safe_dt
    melt_mm = estimate_snow_melt_rate_mm_h(temp_c, rain_mm_h) * safe_dt
    return max(0.0, min(30.0, safe_prev + snow_in_mm - melt_mm))


def fetch_kma_weather(course: Course, service_key: str) -> Optional[Dict[str, Any]]:
    """
    기상청 초단기실황 + 초단기예보를 조회해 summarize_course_weather가 기대하는
    형태(current/hourly)로 정규화합니다.
    """
    if not service_key:
        raise ValueError("KMA 서비스 키가 필요합니다. --kma-service-key 또는 KMA_SERVICE_KEY를 설정하세요.")

    base_date, base_time = kma_base_datetime()
    nx, ny = latlon_to_kma_xy(course.lat, course.lon)

    common_params = {
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
        "pageNo": 1,
        "numOfRows": 1000,
    }

    try:
        obs_url = build_kma_url(KMA_ULTRA_NCST_URL, service_key)
        obs_resp = requests.get(obs_url, params=common_params, timeout=10)
        obs_resp.raise_for_status()
        obs_items = obs_resp.json()["response"]["body"]["items"]["item"]
    except (Timeout, ReadTimeout) as e:
        print(f"[WARN] KMA timeout for {course.name_ko} ({course.lat}, {course.lon}): {e}")
        return None
    except HTTPError as e:
        print(f"[WARN] KMA request error for {course.name_ko} ({course.lat}, {course.lon}): {e}")
        if e.response is not None:
            print(f"[WARN] KMA response body: {e.response.text}")
        return None
    except RequestException as e:
        print(f"[WARN] KMA request error for {course.name_ko} ({course.lat}, {course.lon}): {e}")
        return None
    except Exception as e:
        print(f"[WARN] KMA response parsing error for {course.name_ko}: {e}")
        return None

    obs_map: Dict[str, Any] = {item["category"]: item.get("obsrValue") for item in obs_items}

    try:
        temp_c = float(obs_map.get("T1H"))
    except (TypeError, ValueError):
        temp_c = None

    if temp_c is None:
        print(f"[WARN] KMA response missing temperature for {course.name_ko}, skipping.")
        return None

    wind_ms = float(obs_map.get("WSD", 0.0) or 0.0)
    wind_dir = float(obs_map.get("VEC", 0.0) or 0.0)
    humidity = float(obs_map.get("REH", 60.0) or 60.0)
    precip_mm = parse_precip_value(obs_map.get("RN1"))
    pty_val = str(obs_map.get("PTY", "0"))

    rain_mm = precip_mm if pty_val in ("1", "2", "5", "6") else 0.0
    apparent = calc_apparent_temperature(temp_c or 0.0, wind_ms, humidity)

    # 초단기예보로 앞으로 3시간 강수/기온 예측값을 가져와 노면 판단 보조값으로 사용
    forecast_params = dict(common_params)
    forecast_params["numOfRows"] = 200

    forecast_rain: Dict[str, float] = {}
    forecast_pty: Dict[str, str] = {}
    forecast_temp: Dict[str, float] = {}
    try:
        fcst_url = build_kma_url(KMA_ULTRA_FCST_URL, service_key)
        fcst_resp = requests.get(fcst_url, params=forecast_params, timeout=10)
        fcst_resp.raise_for_status()
        fcst_items = fcst_resp.json()["response"]["body"]["items"]["item"]
        for item in fcst_items:
            time_key = f"{item['fcstDate']}{item['fcstTime']}"
            if item["category"] == "RN1":
                forecast_rain[time_key] = parse_precip_value(item["fcstValue"])
            elif item["category"] == "PTY":
                forecast_pty[time_key] = str(item["fcstValue"])
            elif item["category"] == "T1H":
                try:
                    forecast_temp[time_key] = float(item["fcstValue"])
                except (TypeError, ValueError):
                    pass
    except (Timeout, ReadTimeout) as e:
        print(f"[WARN] KMA forecast timeout for {course.name_ko} ({course.lat}, {course.lon}): {e}")
    except HTTPError as e:
        print(f"[WARN] KMA forecast request error for {course.name_ko} ({course.lat}, {course.lon}): {e}")
        if e.response is not None:
            print(f"[WARN] KMA forecast response body: {e.response.text}")
    except RequestException as e:
        print(f"[WARN] KMA forecast request error for {course.name_ko} ({course.lat}, {course.lon}): {e}")
    except Exception as e:
        print(f"[WARN] KMA forecast parsing error for {course.name_ko}: {e}")

    hourly_precip: List[float] = []
    hourly_rain: List[float] = []
    hourly_temp: List[float] = []
    sorted_times = sorted(
        set(forecast_rain.keys()) |
        set(forecast_pty.keys()) |
        set(forecast_temp.keys())
    )

    for time_key in sorted_times[:3]:
        rn1 = forecast_rain.get(time_key, 0.0)
        pty = forecast_pty.get(time_key, "0")
        t1h = forecast_temp.get(time_key)
        hourly_precip.append(rn1)
        hourly_rain.append(rn1 if pty in ("1", "2", "5", "6") else 0.0)
        if t1h is not None:
            hourly_temp.append(t1h)

    current_time = kst_now().replace(microsecond=0).isoformat()
    return {
        "current": {
            "time": current_time,
            "temperature_2m": temp_c,
            "apparent_temperature": apparent if temp_c is not None else temp_c,
            "precipitation": precip_mm,
            "rain": rain_mm,
            "wind_speed_10m": wind_ms * 3.6,  # summarize 함수가 m/s로 변환하므로 km/h 단위로 제공
            "wind_direction_10m": wind_dir,
        },
        "hourly": {
            "precipitation": hourly_precip,
            "rain": hourly_rain,
            "temperature_2m": hourly_temp,
        },
    }


def fetch_air_quality_kma(
    course: Course,
    service_key: str,
    sido_name: str = DEFAULT_KMA_AIR_SIDO,
) -> Optional[Dict[str, Any]]:
    """
    환경부(에어코리아) 실시간 시도별 대기오염 정보에서 PM10/PM2.5를 조회합니다.
    - lat/lon별 가장 근처 측정소를 구하는 추가 API가 있으나, 간단히 시도 단위로 조회해
      유효한 첫 측정값을 사용합니다.
    """
    if not service_key:
        raise ValueError("KMA 서비스 키가 필요합니다. --kma-service-key 또는 KMA_SERVICE_KEY를 설정하세요.")

    params = {
        "sidoName": sido_name,
        "returnType": "json",
        "pageNo": 1,
        "numOfRows": 100,
        "ver": "1.3",
    }

    url = build_kma_url(KMA_AIR_QUALITY_URL, service_key)
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except HTTPError as e:
        print(f"[WARN] KMA air quality HTTP error: {e}")
        if e.response is not None:
            print(f"[WARN] KMA air quality body: {e.response.text}")
        return None
    except RequestException as e:
        print(f"[WARN] KMA air quality request error: {e}")
        return None

    body = resp.json().get("response", {}).get("body", {})
    items = body.get("items") or []

    chosen = None
    for item in items:
        pm10 = parse_pm_value(item.get("pm10Value"))
        pm25 = parse_pm_value(item.get("pm25Value"))
        if pm10 is not None or pm25 is not None:
            chosen = {
                "time": item.get("dataTime"),
                "pm10": pm10,
                "pm2_5": pm25,
                "station": item.get("stationName"),
            }
            break

    if chosen is None:
        return None

    return {"current": chosen}


# === CLI 옵션 ===


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch running weather data from KMA (only).")
    parser.add_argument(
        "--provider",
        choices=list(SUPPORTED_PROVIDERS),
        default=DEFAULT_PROVIDER,
        help="날씨 데이터 소스 (kma 고정).",
    )
    parser.add_argument(
        "--kma-service-key",
        dest="kma_service_key",
        default=os.getenv("KMA_SERVICE_KEY"),
        help="기상청(data.go.kr) 서비스 키. provider=kma일 때 필수. 환경변수 KMA_SERVICE_KEY로도 지정 가능.",
    )
    parser.add_argument(
        "--air-provider",
        choices=("kma",),
        default="kma",
        help="대기질 데이터 소스 (kma 고정).",
    )
    parser.add_argument(
        "--kma-air-sido-name",
        dest="kma_air_sido_name",
        default=DEFAULT_KMA_AIR_SIDO,
        help=f"기상청(에어코리아) 대기질 조회 시 사용할 시도 이름. 기본값: {DEFAULT_KMA_AIR_SIDO}",
    )
    parser.add_argument(
        "--with-coach",
        action="store_true",
        help="ChatGPT 러닝 코치 메시지를 생성합니다. OPENAI_API_KEY가 필요합니다.",
    )
    parser.add_argument(
        "--openai-api-key",
        dest="openai_api_key",
        default=os.getenv("OPENAI_API_KEY"),
        help="OpenAI API 키. 환경변수 OPENAI_API_KEY로도 지정 가능.",
    )
    parser.add_argument(
        "--openai-model",
        dest="openai_model",
        default=DEFAULT_OPENAI_MODEL,
        help=f"러닝 코치 응답에 사용할 OpenAI 모델. 기본값: {DEFAULT_OPENAI_MODEL}",
    )
    return parser


# === 4. 러닝용으로 요약 + 한/영 텍스트 생성 ===


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
    current_time_dt = parse_iso_datetime(current.get("time")) or kst_now()

    prev_snow_memory_mm = 0.0
    prev_time_dt: Optional[datetime] = None
    if prev_state:
        try:
            prev_snow_memory_mm = float(prev_state.get("snow_memory_mm", 0.0) or 0.0)
        except (TypeError, ValueError):
            prev_snow_memory_mm = 0.0
        prev_snow_memory_mm = max(0.0, min(30.0, prev_snow_memory_mm))
        prev_time_dt = parse_iso_datetime(prev_state.get("updated_at"))

    delta_hours = 0.5  # 워크플로우 기본 주기(30분) 기준
    if prev_time_dt and current_time_dt > prev_time_dt:
        delta_hours = (current_time_dt - prev_time_dt).total_seconds() / 3600.0
    delta_hours = max(0.25, min(12.0, delta_hours))

    # -----------------------------
    # 1) 강수/노면 상태 (비 + 눈)
    # -----------------------------
    current_rain = float(current.get("rain", 0.0))              # mm/h
    current_precip = float(current.get("precipitation", 0.0))   # mm/h (비+눈)
    current_snow = max(current_precip - current_rain, 0.0)      # 눈/진눈깨비 추정

    recent_rain_list = hourly.get("rain", []) or []
    recent_precip_list = hourly.get("precipitation", []) or []
    recent_rain = float(sum(recent_rain_list))                  # 최근 3시간 비
    recent_precip = float(sum(recent_precip_list))              # 최근 3시간 비+눈
    recent_snow = max(recent_precip - recent_rain, 0.0)         # 최근 3시간 눈

    snow_memory_mm = estimate_snow_memory_mm(
        prev_snow_memory_mm=prev_snow_memory_mm,
        dt_h=delta_hours,
        current_snow_mm_h=current_snow,
        temp_c=current_temp,
        rain_mm_h=current_rain,
    )
    hourly_temp_list = hourly.get("temperature_2m", []) or []
    temp_window: List[float] = [current_temp]
    for v in hourly_temp_list[:3]:
        try:
            temp_window.append(float(v))
        except (TypeError, ValueError):
            continue
    subzero_persistent = all(t <= 0.0 for t in temp_window) if temp_window else (current_temp <= 0.0)
    freeze_surface_risk = snow_memory_mm >= 1.0 and subzero_persistent

    if current_precip >= 4.0 or recent_precip >= 8.0:
        hard_caps.append(30)  # 짧은 시간 강수량이 많으면 러닝 강도 제한
        risk_flags_ko.append("강한 비/눈 주의")
        risk_flags_en.append("Heavy precipitation caution")

    # surface_score: 0~100
    # wet_badge: { level: good/wet/bad, text_ko/text_en }
    # wet_tag_*: 태그용, wet_comment_*: 설명문용
    if recent_precip == 0 and current_precip == 0:
        surface_score = 100
        wet_badge = {
            "level": "good",
            "text_ko": "노면 건조",
            "text_en": "Dry surface",
        }
        wet_tag_ko = "노면 건조"
        wet_tag_en = "Dry surface"
        wet_comment_ko = "노면이 건조해서 미끄럼 위험이 적습니다."
        wet_comment_en = "Surface is dry with low risk of slipping."
    else:
        # 눈 많은 날 / 조금 쌓인 날 / 비 위주인 날 구분
        heavy_snow = (recent_snow >= 6.0) or (current_snow >= 4.0)
        light_snow = (recent_snow >= 1.0) or (current_snow >= 0.5)

        if heavy_snow:
            surface_score = 0
            wet_badge = {
                "level": "bad",
                "text_ko": "눈 많이 쌓임",
                "text_en": "Heavy snow/ice",
            }
            wet_tag_ko = "눈 많이 쌓임"
            wet_tag_en = "Heavy snow"
            wet_comment_ko = (
                "눈이 많이 쌓이거나 얼음 구간이 많아 매우 미끄럽습니다. "
                "실외 러닝보다는 실내 러닝이나 휴식을 권장합니다."
            )
            wet_comment_en = (
                "There is heavy snow or many icy sections, making it very slippery. "
                "Indoor running or rest is recommended instead of outdoor running."
            )
        elif light_snow:
            surface_score = 40
            wet_badge = {
                "level": "bad",
                "text_ko": "눈 조금 쌓임",
                "text_en": "Some snow on surface",
            }
            wet_tag_ko = "눈 조금 쌓임"
            wet_tag_en = "Some snow"
            wet_comment_ko = (
                "노면에 눈이 조금 쌓이거나 녹은 물이 있어 미끄러울 수 있습니다. "
                "가능하면 트레일 러닝화나 접지 좋은 러닝화를 착용해 주세요."
            )
            wet_comment_en = (
                "Some snow or meltwater on the surface may cause slipperiness. "
                "Trail running shoes or shoes with good grip are recommended."
            )
        else:
            # 비 위주로 판단
            if recent_precip < 2.0 and current_precip < 1.0:
                surface_score = 80
                wet_badge = {
                    "level": "wet",
                    "text_ko": "살짝 젖음",
                    "text_en": "Slightly wet",
                }
                wet_tag_ko = "살짝 젖음"
                wet_tag_en = "Slightly wet"
                wet_comment_ko = (
                    "노면이 살짝 젖어 있습니다. 코너링이나 브레이킹 시에만 "
                    "미끄럼에 주의하면 러닝에 큰 지장은 없습니다."
                )
                wet_comment_en = (
                    "The surface is slightly wet. As long as you are careful "
                    "when cornering or braking, running should be fine."
                )
            elif recent_rain < 10.0 or current_rain < 4.0:
                surface_score = 50
                wet_badge = {
                    "level": "wet",
                    "text_ko": "젖은 노면",
                    "text_en": "Wet surface",
                }
                wet_tag_ko = "젖은 노면"
                wet_tag_en = "Wet surface"
                wet_comment_ko = (
                    "노면이 젖어 있어 미끄러운 구간이 있을 수 있습니다. "
                    "페이스를 약간 낮추고, 특히 내리막·코너 구간에서 발 조심해 주세요."
                )
                wet_comment_en = (
                    "The surface is wet, and some sections may be slippery. "
                    "Slightly lower your pace and take extra care on downhills and corners."
                )
            elif recent_rain < 20.0 or current_rain < 8.0:
                surface_score = 20
                wet_badge = {
                    "level": "bad",
                    "text_ko": "많이 젖음",
                    "text_en": "Very wet",
                }
                wet_tag_ko = "많이 젖음"
                wet_tag_en = "Very wet"
                wet_comment_ko = (
                    "비가 많이 내려 노면이 꽤 젖어 있고 물웅덩이가 많을 수 있습니다. "
                    "발이 쉽게 젖고 미끄러울 수 있으니 강도 높은 훈련은 피하는 것이 좋습니다."
                )
                wet_comment_en = (
                    "It has rained a lot, so the surface is very wet with many puddles. "
                    "Your feet may get soaked and it can be slippery, so avoid high-intensity workouts."
                )
            else:
                surface_score = 0
                wet_badge = {
                    "level": "bad",
                    "text_ko": "매우 젖음",
                    "text_en": "Extremely wet",
                }
                wet_tag_ko = "매우 젖음"
                wet_tag_en = "Extremely wet"
                wet_comment_ko = (
                    "폭우 수준의 비가 내리고 있어 노면 상태가 매우 좋지 않습니다. "
                    "실외 러닝보다는 실내 러닝이나 휴식을 권장합니다."
                )
                wet_comment_en = (
                    "Rain is at a heavy or torrential level, making the surface very poor. "
                    "Indoor running or rest is recommended instead of outdoor running."
                )

    if freeze_surface_risk:
        if snow_memory_mm >= 3.0:
            surface_score = min(surface_score, 20)
            wet_badge = {
                "level": "bad",
                "text_ko": "잔설/결빙 우려",
                "text_en": "Persistent snow/ice risk",
            }
            wet_tag_ko = "잔설/결빙 우려"
            wet_tag_en = "Snow/ice risk"
            penalty_factor *= 0.8
            hard_caps.append(25)
        else:
            surface_score = min(surface_score, 45)
            wet_badge = {
                "level": "wet",
                "text_ko": "잔설 가능",
                "text_en": "Possible residual snow",
            }
            wet_tag_ko = "잔설 가능"
            wet_tag_en = "Residual snow"
            penalty_factor *= 0.9
            hard_caps.append(35)

        freeze_comment_ko = (
            "영하가 이어져 내린 눈이 잘 녹지 않아 그늘·코너·내리막 구간에서 "
            "잔설 또는 얇은 결빙이 남아 있을 수 있습니다."
        )
        freeze_comment_en = (
            "Sub-zero temperatures may keep snow from melting, so residual snow or thin ice can remain "
            "on shaded, cornering, or downhill sections."
        )
        wet_comment_ko = f"{wet_comment_ko} {freeze_comment_ko}".strip()
        wet_comment_en = f"{wet_comment_en} {freeze_comment_en}".strip()
        if "잔설/결빙 주의" not in risk_flags_ko:
            risk_flags_ko.append("잔설/결빙 주의")
        if "Residual snow/ice caution" not in risk_flags_en:
            risk_flags_en.append("Residual snow/ice caution")

    # -----------------------------
    # 2) 온도 점수 (체감온도, 한국 기준)
    # -----------------------------
    apparent = float(current["apparent_temperature"])

    if apparent <= -15:
        temp_score = 5
        temp_tag_ko = "위험한 추움"
        temp_tag_en = "Very cold"
        temp_comment_ko = (
            "매우 춥습니다. 노출 부위를 최소화하고 두꺼운 장갑, 모자, 넥워머 등 "
            "충분한 방한 장비가 필요합니다."
        )
        temp_comment_en = (
            "It is extremely cold. Minimize exposed skin and wear warm gear such as gloves, hat, and neck warmer."
        )
    elif apparent < -10:
        temp_score = 15
        temp_tag_ko = "매우 추움"
        temp_tag_en = "Very cold"
        temp_comment_ko = (
            "상당히 강한 한기입니다. 장시간 야외 러닝은 추천하지 않으며, "
            "짧고 가벼운 러닝 위주로 가져가는 편이 안전합니다."
        )
        temp_comment_en = (
            "Very cold. Long outdoor runs are not recommended; stick to shorter, lighter runs if you go out."
        )
    elif apparent < -5:
        temp_score = 30
        temp_tag_ko = "추움"
        temp_tag_en = "Cold"
        temp_comment_ko = (
            "꽤 춥습니다. 긴팔+긴바지에 방풍 자켓을 더해 주는 것이 좋습니다."
        )
        temp_comment_en = (
            "It is quite cold. Long sleeves, tights, and a windproof jacket are recommended."
        )
    elif apparent < 0:
        temp_score = 45
        temp_tag_ko = "쌀쌀함"
        temp_tag_en = "Chilly"
        temp_comment_ko = (
            "쌀쌀한 편입니다. 긴팔, 긴바지 또는 얇은 레이어링을 추천합니다."
        )
        temp_comment_en = (
            "Chilly conditions. Long sleeves and tights or light layering are recommended."
        )
    elif apparent < 5:
        temp_score = 60
        temp_tag_ko = "조금 쌀쌀함"
        temp_tag_en = "A bit chilly"
        temp_comment_ko = (
            "조금 쌀쌀하지만 러닝하기 좋은 편입니다. 가벼운 레이어링이 잘 어울립니다."
        )
        temp_comment_en = (
            "A bit chilly but good for running. Light layering works well."
        )
    elif apparent < 12:
        temp_score = 100
        temp_tag_ko = "러닝 최적"
        temp_tag_en = "Optimal"
        temp_comment_ko = (
            "러닝하기 최적의 온도입니다. 평소보다 페이스를 조금 올려도 부담이 적습니다."
        )
        temp_comment_en = (
            "Perfect temperature for running. You can slightly increase your usual pace."
        )
    elif apparent < 18:
        temp_score = 90
        temp_tag_ko = "적당함"
        temp_tag_en = "Comfortable"
        temp_comment_ko = (
            "적당한 온도입니다. 평소 복장으로 무리 없이 러닝하기 좋습니다."
        )
        temp_comment_en = (
            "Comfortable temperature. Your usual outfit should be fine for running."
        )
    elif apparent < 22:
        temp_score = 75
        temp_tag_ko = "다소 따뜻함"
        temp_tag_en = "Warm"
        temp_comment_ko = (
            "다소 따뜻한 편입니다. 통풍 잘 되는 옷과 충분한 수분 섭취를 추천합니다."
        )
        temp_comment_en = (
            "Slightly warm. Wear breathable clothes and make sure to hydrate."
        )
    elif apparent < 26:
        temp_score = 55
        temp_tag_ko = "조금 더움"
        temp_tag_en = "Very warm"
        temp_comment_ko = (
            "조금 더운 편입니다. 강도 높은 훈련보다는 적당한 강도의 러닝이 좋습니다."
        )
        temp_comment_en = (
            "Slightly hot. Moderate intensity runs are better than hard workouts."
        )
    elif apparent < 29:
        temp_score = 40
        temp_tag_ko = "더움"
        temp_tag_en = "Hot"
        temp_comment_ko = (
            "더운 편입니다. 강도를 낮추고 자주 수분을 섭취하는 것이 좋습니다."
        )
        temp_comment_en = (
            "Warm conditions. Lower your intensity and hydrate frequently."
        )
    elif apparent < 31:
        temp_score = 25
        temp_tag_ko = "꽤 더움"
        temp_tag_en = "Quite hot"
        temp_comment_ko = (
            "상당히 덥습니다. 장거리나 고강도 러닝은 피하고, 그늘 위주 코스를 추천합니다."
        )
        temp_comment_en = (
            "It is quite hot. Avoid long or high-intensity runs and seek shaded routes."
        )
    elif apparent < 33:
        temp_score = 10
        temp_tag_ko = "매우 더움"
        temp_tag_en = "Very hot"
        temp_comment_ko = (
            "매우 덥습니다. 짧고 가벼운 러닝이 아니면 실외 러닝을 피하는 편이 안전합니다."
        )
        temp_comment_en = (
            "Very hot. Unless it is a short and easy run, it is safer to avoid outdoor running."
        )
    else:
        temp_score = 0
        temp_tag_ko = "위험한 더움"
        temp_tag_en = "Extremely hot"
        temp_comment_ko = (
            "위험할 정도로 덥습니다. 실외 러닝은 권장하지 않으며, 실내 운동이나 휴식을 추천합니다."
        )
        temp_comment_en = (
            "Dangerously hot. Outdoor running is not recommended; consider indoor exercise or rest."
        )

    # 극단적인 추위/더위에서는 추가 패널티와 상한을 적용
    if apparent < -8:
        penalty_factor *= max(0.35, 1.0 - (abs(apparent + 8) * 0.06))
        risk_flags_ko.append("혹한 주의")
        risk_flags_en.append("Extreme cold")
    elif apparent > 26:
        penalty_factor *= max(0.35, 1.0 - ((apparent - 26) * 0.07))
        risk_flags_ko.append("고온 주의")
        risk_flags_en.append("Extreme heat")

    if apparent <= -15 or apparent >= 33 or surface_score == 0:
        hard_caps.append(20)
    elif apparent <= -12 or apparent >= 30:
        hard_caps.append(25)

    # -----------------------------
    # 3) 바람 점수 (m/s 기준)
    # -----------------------------
    raw_wind_speed_kmh = float(current["wind_speed_10m"])
    wind_speed = raw_wind_speed_kmh / 3.6  # km/h → m/s
    wind_dir = float(current["wind_direction_10m"])

    if wind_speed < 2.0:
        wind_score = 100
        wind_tag_ko = "바람 거의 없음"
        wind_tag_en = "Calm"
        wind_comment_ko = "바람이 거의 없어 페이스 유지에 유리합니다."
        wind_comment_en = "Almost no wind, good for maintaining your pace."
    elif wind_speed < 4.0:
        wind_score = 80
        wind_tag_ko = "약한 바람"
        wind_tag_en = "Light breeze"
        wind_comment_ko = "약한 바람으로 러닝에 큰 지장은 없습니다."
        wind_comment_en = "Light breeze with little impact on running."
    elif wind_speed < 6.0:
        wind_score = 60
        wind_tag_ko = "다소 강한 바람"
        wind_tag_en = "Moderate wind"
        wind_comment_ko = (
            "바람이 다소 있어 체감온도가 조금 낮게 느껴질 수 있습니다."
        )
        wind_comment_en = (
            "Moderate wind. It may feel a bit cooler than the actual temperature."
        )
    elif wind_speed < 8.0:
        wind_score = 40
        wind_tag_ko = "강한 바람"
        wind_tag_en = "Strong wind"
        wind_comment_ko = (
            "바람이 강한 편입니다. 맞바람 구간에서는 페이스를 낮추는 것이 좋습니다."
        )
        wind_comment_en = (
            "Strong wind. Lower your pace in headwind sections."
        )
    else:
        wind_score = 25
        wind_tag_ko = "매우 강한 바람"
        wind_tag_en = "Very strong wind"
        wind_comment_ko = (
            "바람이 매우 강합니다. 체감온도가 크게 내려가고 피로가 빨리 쌓일 수 있습니다."
        )
        wind_comment_en = (
            "Very strong wind. It feels much colder and fatigue may build up faster."
        )

    if apparent <= -5:
        if wind_speed >= 8.0:
            penalty_factor *= 0.8
            risk_flags_ko.append("강풍 한기")
            risk_flags_en.append("Wind chill risk")
        elif wind_speed >= 6.0:
            penalty_factor *= 0.9
            risk_flags_ko.append("바람 추위")
            risk_flags_en.append("Breezy cold")

    # -----------------------------
    # 4) 공기질 (PM10 / PM2.5) + 패널티 팩터
    # -----------------------------
    pm10 = None
    pm25 = None
    air_score = 90  # 기본값: "거의 문제 없음" 정도
    air_tag_ko = None
    air_tag_en = None
    air_comment_ko = ""
    air_comment_en = ""

    if raw_air is not None and "current" in raw_air:
        current_air = raw_air["current"]
        if current_air.get("pm10") is not None:
            pm10 = float(current_air["pm10"])
        if current_air.get("pm2_5") is not None:
            pm25 = float(current_air["pm2_5"])

    # PM10과 PM2.5 각각 점수 계산 후 최솟값(더 보수적인 점수) 적용
    score_pm10 = 100
    score_pm25 = 100
    if pm10 is not None:
        if pm10 <= 30:
            score_pm10 = 100
        elif pm10 <= 80:
            score_pm10 = 80
        elif pm10 <= 150:
            score_pm10 = 55
        else:
            score_pm10 = 30

    if pm25 is not None:
        if pm25 <= 15:
            score_pm25 = 100
        elif pm25 <= 35:
            score_pm25 = 80
        elif pm25 <= 75:
            score_pm25 = 55
        else:
            score_pm25 = 30

    if pm10 is not None or pm25 is not None:
        air_score = min(score_pm10, score_pm25)
        if air_score >= 90:
            air_tag_ko, air_tag_en = "공기질 좋음", "Good air"
            air_comment_ko = "공기질이 깨끗하여 야외 러닝에 적합합니다."
            air_comment_en = "Air quality is clean and great for outdoor running."
        elif air_score >= 70:
            air_tag_ko, air_tag_en = "공기질 보통", "Moderate air"
            air_comment_ko = "공기질이 보통 수준입니다. 민감군은 조심하세요."
            air_comment_en = "Air quality is moderate."
        elif air_score >= 50:
            air_tag_ko, air_tag_en = "공기질 나쁨", "Bad air"
            air_comment_ko = "공기질이 안 좋습니다. 고강도 훈련은 자제하세요."
            air_comment_en = "Air quality is poor. Avoid intense workouts."
        else:
            air_tag_ko, air_tag_en = "공기질 매우 나쁨", "Very bad air"
            air_comment_ko = "공기질이 매우 나쁩니다. 실내 러닝을 권장합니다."
            air_comment_en = "Air quality is very poor. Indoor running recommended."

    # 공기질 수준에 따른 패널티 팩터
    if air_score >= 90:
        factor_air = 1.0     # 좋음: 영향 없음
    elif air_score >= 70:
        factor_air = 0.95    # 보통: 소폭 감소
    elif air_score >= 50:
        factor_air = 0.7     # 나쁨: 더 보수적으로 감소
        risk_flags_ko.append("공기질 주의")
        risk_flags_en.append("Air quality caution")
    else:
        factor_air = 0.45    # 매우 나쁨: 강하게 감소
        risk_flags_ko.append("공기질 매우 나쁨")
        risk_flags_en.append("Very poor air")

    # 야간(22~6시) 처리: 여름철(체감 20도 이상)에는 무더위 피하는 밤러닝 이점이 있으므로 점수 감점 없이 안전 주의 태그만 부여
    night_penalty = 1.0
    try:
        current_dt = datetime.fromisoformat(current["time"])
        if current_dt.hour >= 22 or current_dt.hour < 6:
            risk_flags_ko.append("야간 주의")
            risk_flags_en.append("Night caution")
            if apparent < 20:
                night_penalty = 0.95
    except Exception:
        current_dt = None
    penalty_factor *= night_penalty

    # -----------------------------
    # 5) 종합 러닝 인덱스
    #    기본: 온도 60% + 바람 20% + 노면 20%
    #    공기질은 패널티(factor_air)로만 반영
    # -----------------------------
    base_score = (
        temp_score * 0.60 +
        wind_score * 0.20 +
        surface_score * 0.20
    )

    run_score = base_score * factor_air * penalty_factor

    # 안전 상한 적용
    if hard_caps:
        run_score = min(run_score, min(hard_caps))

    run_score = int(round(max(0, min(100, run_score))))

    humidity = float(current.get("relative_humidity_2m", 60.0) or 60.0)
    outfit_ko, outfit_en = get_outfit_recommendation(
        current_temp, apparent, current_rain, current_snow, wind_speed
    )
    pace_tip_ko, pace_tip_en = get_pace_and_running_tip(
        current_temp, apparent, humidity, wind_speed, air_score, surface_score
    )

    # -----------------------------
    # 6) 종합 코멘트 및 태그 구성
    # -----------------------------
    if run_score >= 80:
        advice_short_ko = "러닝하기 아주 좋은 컨디션입니다 😄"
        advice_short_en = "Great conditions for running 😄"
    elif run_score >= 60:
        advice_short_ko = "러닝하기 무난한 컨디션입니다 🙂"
        advice_short_en = "Decent conditions for running 🙂"
    elif run_score >= 40:
        advice_short_ko = "주의하면서 뛰면 괜찮은 컨디션입니다 ⚠️"
        advice_short_en = "Okay to run with some caution ⚠️"
    else:
        advice_short_ko = "러닝 강도/시간을 줄이거나 실외 러닝을 피하는 것이 좋습니다 🚨"
        advice_short_en = "Consider reducing intensity/duration or avoiding outdoor running 🚨"

    detail_parts_ko = [temp_comment_ko, wind_comment_ko, wet_comment_ko]
    detail_parts_en = [temp_comment_en, wind_comment_en, wet_comment_en]

    if air_comment_ko:
        detail_parts_ko.append(air_comment_ko)
    if air_comment_en:
        detail_parts_en.append(air_comment_en)

    if risk_flags_ko:
        detail_parts_ko.append(f"추가 주의 요인: {', '.join(risk_flags_ko)}.")
    if risk_flags_en:
        detail_parts_en.append(f"Extra cautions: {', '.join(risk_flags_en)}.")

    advice_detail_ko = " ".join(detail_parts_ko)
    advice_detail_en = " ".join(detail_parts_en)

    # 태그: 온도/바람/노면 + (공기질 있으면) 공기질
    tags_ko = [temp_tag_ko, wind_tag_ko, wet_tag_ko]
    tags_en = [temp_tag_en, wind_tag_en, wet_tag_en]
    if air_tag_ko and air_tag_en:
        tags_ko.append(air_tag_ko)
        tags_en.append(air_tag_en)
    tags_ko.extend(risk_flags_ko)
    tags_en.extend(risk_flags_en)

    # -----------------------------
    # 7) 최종 Dict 리턴 (JSON으로 직렬화될 내용)
    # -----------------------------
    return {
        "id": course.id,
        "name_ko": course.name_ko,
        "name_en": course.name_en,
        "name": course.name_ko,
        "updated_at": current["time"],
        "lat": course.lat,
        "lon": course.lon,
        "temperature": float(current["temperature_2m"]),
        "apparent_temperature": round(apparent, 1),
        "humidity": round(humidity, 1),
        "wind_speed": wind_speed,          # m/s
        "wind_direction": wind_dir,
        "rain_now": current_rain,
        "snow_now": current_snow,
        "snow_memory_mm": round(snow_memory_mm, 2),
        "freeze_surface_risk": freeze_surface_risk,
        "forecast_rain_3h": recent_rain,
        "forecast_snow_3h": recent_snow,
        "recent_rain_3h": recent_rain,     # 하위 호환용
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
        "advice_detail_ko": advice_detail_ko,
        "advice_detail_en": advice_detail_en,
        "pm10": pm10,
        "pm25": pm25,
    }


# === 5. ChatGPT 러닝 코치 ===


def build_coach_messages(
    course: Course,
    summary: Dict[str, Any],
    raw_weather: Dict[str, Any],
    raw_air: Optional[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """
    ChatGPT에게 전달할 메시지 페이로드를 구성합니다.
    한국어 → 영어 순서로 짧게 러닝 코칭을 요청합니다.
    """
    payload = {
        "course": {
            "id": course.id,
            "name_ko": course.name_ko,
            "name_en": course.name_en,
            "lat": course.lat,
            "lon": course.lon,
        },
        "summary_for_running": summary,
        "raw_weather": raw_weather,
        "raw_air": raw_air,
    }

    system_prompt = (
        "You are a concise running coach who is fluent in Korean and English. "
        "Given structured weather/air data for a running course, produce short, "
        "actionable advice (Korean first, English second). "
        "Cover recommended intensity/time, hydration/gear, and key cautions. "
        "Keep it under 6 sentences total."
    )

    user_prompt = (
        "Here is the course + weather data as JSON. "
        "Respond with Korean first, then English:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def call_chatgpt_coach(
    course: Course,
    summary: Dict[str, Any],
    raw_weather: Dict[str, Any],
    raw_air: Optional[Dict[str, Any]],
    api_key: str,
    model: str = DEFAULT_OPENAI_MODEL,
    timeout: int = 30,
) -> Optional[str]:
    """
    OpenAI Chat Completions API를 호출해 러닝 코치 코멘트를 생성합니다.
    실패 시 None을 반환하며 전체 스크립트를 중단하지 않습니다.
    """
    if not api_key:
        raise ValueError("OpenAI API 키가 필요합니다. --openai-api-key 또는 OPENAI_API_KEY를 설정하세요.")

    messages = build_coach_messages(course, summary, raw_weather, raw_air)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": 400,
    }

    try:
        resp = requests.post(
            OPENAI_API_URL,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (Timeout, ReadTimeout) as e:
        print(f"[WARN] ChatGPT timeout for {course.name_ko}: {e}")
    except HTTPError as e:
        print(f"[WARN] ChatGPT HTTP error for {course.name_ko}: {e}")
        if e.response is not None:
            print(f"[WARN] ChatGPT response body: {e.response.text}")
    except RequestException as e:
        print(f"[WARN] ChatGPT request error for {course.name_ko}: {e}")
    except Exception as e:
        print(f"[WARN] ChatGPT unexpected error for {course.name_ko}: {e}")
    return None


# === 6. JSON 파일로 저장 ===


def load_previous_course_states(path: Path) -> Dict[str, Dict[str, Any]]:
    """
    이전 src_weather.json에서 코스별 상태를 읽어 id 기준으로 매핑합니다.
    """
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] Failed to read previous weather json: {e}")
        return {}

    courses = payload.get("courses")
    if not isinstance(courses, list):
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for item in courses:
        if not isinstance(item, dict):
            continue
        cid = item.get("id")
        if not cid:
            continue
        out[str(cid)] = item
    return out


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    kma_service_key = args.kma_service_key
    air_provider = args.air_provider
    kma_air_sido_name = args.kma_air_sido_name
    enable_coach = args.with_coach
    openai_api_key = args.openai_api_key
    openai_model = args.openai_model

    if not kma_service_key:
        print("[ERROR] --kma-service-key 또는 KMA_SERVICE_KEY가 필요합니다.")
        return
    if enable_coach and not openai_api_key:
        print("[WARN] --with-coach가 설정되었지만 OpenAI API 키가 없습니다. 코치 생성은 건너뜁니다.")
        enable_coach = False

    out_path = Path("data") / "src_weather.json"
    previous_states = load_previous_course_states(out_path)
    results: List[Dict[str, Any]] = []

    for course in COURSES:
        print(
            f"[INFO] Fetching weather (KMA) for {course.name_ko} "
            f"({course.lat}, {course.lon})"
        )

        raw_weather = fetch_kma_weather(course, kma_service_key)

        if raw_weather is None:
            # 이 코스는 이번 run에서 실패 → 전체 스크립트는 계속 진행
            print(f"[WARN] Weather fetch failed for {course.name_ko}, skipping this course.")
            continue

        raw_air: Optional[Dict[str, Any]] = None
        try:
            if air_provider == "kma":
                print("    - Fetching air quality (KMA/AirKorea)...")
                raw_air = fetch_air_quality_kma(course, kma_service_key, kma_air_sido_name)
        except Exception as e:
            print(f"[WARN] Failed to fetch air quality for {course.name_ko}: {e}")
            raw_air = None

        summary = summarize_course_weather(
            course,
            raw_weather,
            raw_air,
            prev_state=previous_states.get(course.id),
        )
        if enable_coach:
            coach = call_chatgpt_coach(
                course=course,
                summary=summary,
                raw_weather=raw_weather,
                raw_air=raw_air,
                api_key=openai_api_key,
                model=openai_model,
            )
            if coach:
                summary["coach_advice"] = coach
                summary["coach_model"] = openai_model
        results.append(summary)
        time.sleep(5)

    output = {
        "generated_at": kst_now().isoformat(),
        "courses": results,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[INFO] Saved {out_path} ({len(results)} courses)")


if __name__ == "__main__":
    main()
