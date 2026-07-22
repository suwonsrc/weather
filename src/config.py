import os
from dataclasses import dataclass
from typing import List
from datetime import timezone, timedelta

KST = timezone(timedelta(hours=9))

DEFAULT_PROVIDER = "kma"
SUPPORTED_PROVIDERS = ("kma", "open-meteo")

@dataclass
class Course:
    id: str
    name_ko: str
    name_en: str
    lat: float
    lon: float
    location_ko: str
    location_en: str

COURSES: List[Course] = [
    Course("seoho-park", "서호공원", "Seoho Park", 37.280325, 126.990396, "수원시 권선구 서둔동", "Seodun"),
    Course("youth-center", "청소년문화센터", "Youth Center", 37.274248, 127.034519, "수원시 팔달구 인계동", "Ingye"),
    Course("gwanggyo-lake-park", "광교호수공원", "Gwanggyo Lake Park", 37.283439, 127.065989, "수원시 영통구 하동", "Hadong"),
    Course("skku", "성균관대학교", "SKKU (Suwon)", 37.293788, 126.974365, "수원시 장안구 율전동", "Yuljeon"),
    Course("woncheon-stream-sindong", "원천리천(신동)", "Woncheon Stream", 37.248469, 127.041965, "수원시 영통구 신동", "Sindong"),
    Course("paldalsan-hwaseong", "팔달산(수원화성, 행궁동)", "Paldalsan Area", 37.277614, 127.010650, "수원시 팔달구 행궁동", "Haenggung"),
    Course("suwon-stream", "수원천", "Suwon Stream", 37.266571, 127.015022, "수원시 팔달구 지동", "Jidong"),
    Course("gwanggyo-mountain", "광교산", "Mt. Gwanggyo", 37.328633, 127.038172, "수원시 장안구 하광교동", "Hagwanggyo"),
    Course("suwon-worldcup", "수원월드컵경기장", "Suwon World Cup", 37.286545, 127.036871, "수원시 팔달구 우만동", "Uman"),
    Course("dongtan-yeoul-park", "동탄여울공원", "Dongtan Yeoul Park", 37.198689, 127.086609, "화성시 동탄 오산동", "Osan"),
    Course("yeongheung-forest-park", "영흥숲공원", "Yeongheung Forest", 37.261067, 127.070470, "수원시 영통구 원천동", "Woncheon"),
    Course("majung-park", "마중공원", "Majung Park", 37.236832, 127.020592, "수원시 권선구 세류동", "Seryu"),
]

KMA_ULTRA_NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
KMA_ULTRA_FCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst"
KMA_AIR_QUALITY_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"

DEFAULT_KMA_AIR_SIDO = os.getenv("KMA_AIR_SIDO_NAME", "경기도")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
