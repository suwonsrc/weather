import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List

from src.config import (
    COURSES,
    DEFAULT_PROVIDER,
    SUPPORTED_PROVIDERS,
    DEFAULT_KMA_AIR_SIDO,
    DEFAULT_OPENAI_MODEL,
    KST,
)
from src.kma_api import fetch_kma_weather, fetch_air_quality_kma, kst_now
from src.scoring import summarize_course_weather
from src.advisor import call_chatgpt_coach


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch running weather data from KMA.")
    parser.add_argument("--provider", choices=list(SUPPORTED_PROVIDERS), default=DEFAULT_PROVIDER)
    parser.add_argument("--kma-service-key", dest="kma_service_key", default=os.getenv("KMA_SERVICE_KEY"))
    parser.add_argument("--air-provider", choices=("kma",), default="kma")
    parser.add_argument("--kma-air-sido-name", dest="kma_air_sido_name", default=DEFAULT_KMA_AIR_SIDO)
    parser.add_argument("--with-coach", action="store_true")
    parser.add_argument("--openai-api-key", dest="openai_api_key", default=os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--openai-model", dest="openai_model", default=DEFAULT_OPENAI_MODEL)
    return parser


def load_previous_course_states(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        courses = payload.get("courses")
        if not isinstance(courses, list):
            return {}
        return {str(item["id"]): item for item in courses if isinstance(item, dict) and "id" in item}
    except Exception as e:
        print(f"[WARN] Failed to read previous states: {e}")
        return {}


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    kma_service_key = args.kma_service_key
    if not kma_service_key:
        print("[ERROR] KMA_SERVICE_KEY가 필요합니다.")
        return

    out_path = Path("data") / "src_weather.json"
    previous_states = load_previous_course_states(out_path)
    results: List[Dict[str, Any]] = []

    for course in COURSES:
        print(f"[INFO] Fetching weather (KMA) for {course.name_ko}")
        raw_weather = fetch_kma_weather(course, kma_service_key)
        if raw_weather is None:
            continue

        raw_air = None
        try:
            raw_air = fetch_air_quality_kma(course, kma_service_key, args.kma_air_sido_name)
        except Exception as e:
            print(f"[WARN] Failed air quality fetch for {course.name_ko}: {e}")

        summary = summarize_course_weather(
            course, raw_weather, raw_air, prev_state=previous_states.get(course.id)
        )

        if args.with_coach and args.openai_api_key:
            coach = call_chatgpt_coach(
                course, summary, raw_weather, raw_air, args.openai_api_key, args.openai_model
            )
            if coach:
                summary["coach_advice"] = coach

        results.append(summary)
        time.sleep(1)

    output = {
        "generated_at": kst_now().isoformat(),
        "courses": results,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] Successfully saved {out_path} ({len(results)} courses)")


if __name__ == "__main__":
    main()
