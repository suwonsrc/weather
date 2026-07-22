import math
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional, Dict, Any, List
from urllib.parse import quote_plus
import requests
from requests.exceptions import Timeout, ReadTimeout, RequestException, HTTPError

from src.config import (
    KST,
    Course,
    KMA_ULTRA_NCST_URL,
    KMA_ULTRA_FCST_URL,
    KMA_AIR_QUALITY_URL,
    DEFAULT_KMA_AIR_SIDO,
)

def kst_now() -> datetime:
    return datetime.now(tz=timezone.utc).astimezone(KST)

def kma_base_datetime(now_kst: Optional[datetime] = None) -> Tuple[str, str]:
    now = now_kst or kst_now()
    base_dt = now - timedelta(minutes=40)
    base_dt = base_dt.replace(
        minute=(base_dt.minute // 30) * 30,
        second=0,
        microsecond=0,
    )
    return base_dt.strftime("%Y%m%d"), base_dt.strftime("%H%M")

def latlon_to_kma_xy(lat: float, lon: float) -> Tuple[int, int]:
    RE = 6371.00877
    GRID = 5.0
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
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if not text or text == "강수없음":
        return 0.0
    cleaned = text.replace("mm", "").replace(" ", "").replace("미만", "")
    if cleaned == "":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def parse_pm_value(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None

def build_kma_url(base_url: str, service_key: str) -> str:
    encoded_key = service_key if "%" in service_key else quote_plus(service_key)
    return f"{base_url}?serviceKey={encoded_key}"

def fetch_kma_weather(course: Course, service_key: str) -> Optional[Dict[str, Any]]:
    if not service_key:
        raise ValueError("KMA 서비스 키가 필요합니다.")

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
    except Exception as e:
        print(f"[WARN] KMA obs fetch failed for {course.name_ko}: {e}")
        return None

    obs_map = {item["category"]: item.get("obsrValue") for item in obs_items}

    try:
        temp_c = float(obs_map.get("T1H"))
    except (TypeError, ValueError):
        return None

    wind_ms = float(obs_map.get("WSD", 0.0) or 0.0)
    wind_dir = float(obs_map.get("VEC", 0.0) or 0.0)
    humidity = float(obs_map.get("REH", 60.0) or 60.0)
    precip_mm = parse_precip_value(obs_map.get("RN1"))
    pty_val = str(obs_map.get("PTY", "0"))
    rain_mm = precip_mm if pty_val in ("1", "2", "5", "6") else 0.0

    forecast_rain: Dict[str, float] = {}
    forecast_pty: Dict[str, str] = {}
    forecast_temp: Dict[str, float] = {}
    try:
        fcst_url = build_kma_url(KMA_ULTRA_FCST_URL, service_key)
        fcst_resp = requests.get(fcst_url, params=dict(common_params, numOfRows=200), timeout=10)
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
    except Exception as e:
        print(f"[WARN] KMA fcst fetch failed for {course.name_ko}: {e}")

    hourly_precip = []
    hourly_rain = []
    hourly_temp = []
    sorted_times = sorted(set(forecast_rain.keys()) | set(forecast_pty.keys()) | set(forecast_temp.keys()))

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
            "apparent_temperature": temp_c,
            "relative_humidity_2m": humidity,
            "precipitation": precip_mm,
            "rain": rain_mm,
            "wind_speed_10m": wind_ms * 3.6,
            "wind_direction_10m": wind_dir,
        },
        "hourly": {
            "precipitation": hourly_precip,
            "rain": hourly_rain,
            "temperature_2m": hourly_temp,
        },
    }

def fetch_air_quality_kma(
    course: Course, service_key: str, sido_name: str = DEFAULT_KMA_AIR_SIDO
) -> Optional[Dict[str, Any]]:
    if not service_key:
        return None

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
        items = resp.json().get("response", {}).get("body", {}).get("items") or []
        for item in items:
            pm10 = parse_pm_value(item.get("pm10Value"))
            pm25 = parse_pm_value(item.get("pm25Value"))
            if pm10 is not None or pm25 is not None:
                return {"current": {"time": item.get("dataTime"), "pm10": pm10, "pm2_5": pm25, "station": item.get("stationName")}}
    except Exception as e:
        print(f"[WARN] Air quality fetch error: {e}")
    return None
