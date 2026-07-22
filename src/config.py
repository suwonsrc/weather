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
    name_en_short: str = ""
    location_en_short: str = ""

COURSES: List[Course] = [
    Course("seoho-park", "서호공원", "Seoho Park", 37.280325, 126.990396, "수원시 권선구 서둔동", "Seodun-dong, Suwon", "Seoho Park", "Seodun"),
    Course("youth-center", "청소년문화센터", "Youth Culture Center", 37.274248, 127.034519, "수원시 팔달구 인계동", "Ingye-dong, Suwon", "Youth Center", "Ingye"),
    Course("gwanggyo-lake-park", "광교호수공원", "Gwanggyo Lake Park", 37.283439, 127.065989, "수원시 영통구 하동", "Ha-dong, Suwon", "Gwanggyo Lake", "Hadong"),
    Course("skku", "성균관대학교", "Sungkyunkwan Univ. (Suwon)", 37.293788, 126.974365, "수원시 장안구 율전동", "Yuljeon-dong, Suwon", "SKKU (Suwon)", "Yuljeon"),
    Course("woncheon-stream-sindong", "원천리천(신동)", "Woncheon Stream (Sindong)", 37.248469, 127.041965, "수원시 영통구 신동", "Sin-dong, Suwon", "Woncheon Stream", "Sindong"),
    Course("paldalsan-hwaseong", "팔달산(수원화성, 행궁동)", "Paldalsan Fortress Area", 37.277614, 127.010650, "수원시 팔달구 행궁동", "Haenggung-dong, Suwon", "Paldalsan Area", "Haenggung"),
    Course("suwon-stream", "수원천", "Suwoncheon Stream", 37.266571, 127.015022, "수원시 팔달구 지동", "Ji-dong, Suwon", "Suwon Stream", "Jidong"),
    Course("gwanggyo-mountain", "광교산", "Gwanggyo Mountain", 37.328633, 127.038172, "수원시 장안구 하광교동", "Hagwanggyo-dong, Suwon", "Mt. Gwanggyo", "Hagwanggyo"),
    Course("suwon-worldcup", "수원월드컵경기장", "Suwon World Cup Stadium", 37.286545, 127.036871, "수원시 팔달구 우만동", "Uman-dong, Suwon", "Suwon World Cup", "Uman"),
    Course("dongtan-yeoul-park", "동탄여울공원", "Dongtan Yeoul Park", 37.198689, 127.086609, "화성시 동탄 오산동", "Osan-dong, Dongtan", "Dongtan Yeoul", "Osan"),
    Course("yeongheung-forest-park", "영흥숲공원", "Yeongheung Forest Park", 37.261067, 127.070470, "수원시 영통구 원천동", "Woncheon-dong, Suwon", "Yeongheung Forest", "Woncheon"),
    Course("majung-park", "마중공원", "Majung Park", 37.236832, 127.020592, "수원시 권선구 세류동", "Seryu-dong, Suwon", "Majung Park", "Seryu"),
]

KMA_ULTRA_NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
KMA_ULTRA_FCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst"
KMA_AIR_QUALITY_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"

DEFAULT_KMA_AIR_SIDO = os.getenv("KMA_AIR_SIDO_NAME", "경기도")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
