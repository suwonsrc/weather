import os
from dataclasses import dataclass
from typing import List, Tuple
from datetime import timezone, timedelta

KST = timezone(timedelta(hours=9))

@dataclass
class Course:
    id: str
    name_ko: str
    name_en: str
    lat: float
    lon: float

COURSES: List[Course] = [
    Course("seoho-park", "서호공원", "Seoho Park", 37.280325, 126.990396),
    Course("youth-center", "청소년문화센터", "Youth Culture Center", 37.274248, 127.034519),
    Course("gwanggyo-lake-park", "광교호수공원", "Gwanggyo Lake Park", 37.283439, 127.065989),
    Course("skku", "성균관대학교", "Sungkyunkwan Univ. (Suwon)", 37.293788, 126.974365),
    Course("woncheon-stream-sindong", "원천리천(신동)", "Woncheon Stream (Sindong)", 37.248469, 127.041965),
    Course("paldalsan-hwaseong", "팔달산(수원화성, 행궁동)", "Paldalsan Fortress Area", 37.277614, 127.010650),
    Course("suwon-stream", "수원천", "Suwoncheon Stream", 37.266571, 127.015022),
    Course("gwanggyo-mountain", "광교산", "Gwanggyo Mountain", 37.328633, 127.038172),
    Course("suwon-worldcup", "수원월드컵경기장", "Suwon World Cup Stadium", 37.286545, 127.036871),
    Course("dongtan-yeoul-park", "동탄여울공원", "Dongtan Yeoul Park", 37.198689, 127.086609),
    Course("yeongheung-forest-park", "영흥숲공원", "Yeongheung Forest Park", 37.261067, 127.070470),
    Course("majung-park", "마중공원", "Majung Park", 37.236832, 127.020592),
]

KMA_ULTRA_NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
KMA_ULTRA_FCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst"
KMA_AIR_QUALITY_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"

DEFAULT_KMA_AIR_SIDO = os.getenv("KMA_AIR_SIDO_NAME", "경기도")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
