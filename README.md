# SRC Weather

A public-good weather and air-quality board built for the SRC runners' community. The page exists to help runners make safe, informed choices, and is used only for community/public-interest purposes.

- 서비스: https://suwonsrc.github.io/weather/
- 대상 지역: 수원/화성 지역 러닝 코스 12곳

## 동작 방식 (아키텍처)

```
GitHub Actions (schedule: 매시 03분)
        │
        ▼
fetch_weather.py  ──▶  KMA API (1순위) / Open-Meteo API (폴백)
        │
        ▼
data/src_weather.json 생성
        │
        ▼
git commit & push (같은 워크플로우가 자동 수행)
        │
        ▼
GitHub Pages가 정적 파일(index.html, app.js, style.css, data/*.json) 서빙
        │
        ▼
브라우저(app.js)가 data/src_weather.json을 fetch해서 화면에 렌더링
```

서버가 따로 없는 완전 정적 사이트입니다. GitHub Actions가 주기적으로 날씨 데이터를 JSON 파일로 만들어 저장소에 커밋해 두면, GitHub Pages가 그걸 그대로 서빙하고, 브라우저 쪽 JS가 그 JSON을 읽어 화면을 그립니다.

## 프로젝트 구조

```
fetch_weather.py            데이터 수집 CLI 진입점 (GitHub Actions가 이걸 실행)
src/
  config.py                 코스 12곳 좌표, KMA API URL, 대기질 관측소 근사 좌표 등 상수
  kma_api.py                KMA API 클라이언트 + Open-Meteo 폴백, 좌표/시간 변환 유틸
  scoring.py                러닝 적합도 점수·등급·체감온도·잔설 계산 로직
  advisor.py                복장/페이스 추천 문구 생성
data/src_weather.json       생성된 결과 JSON (워크플로우가 자동 커밋)
index.html / app.js / style.css   정적 프론트엔드 (빌드 도구 없음, 순수 JS)
.github/workflows/update_weather.yml   데이터 자동 수집·배포 워크플로우
```

## 데이터 소스 & 폴백 규칙

- **날씨(기온/바람/강수)**: 1순위 KMA 초단기실황·예보(`getUltraSrtNcst`/`getUltraSrtFcst`), 실패 시 Open-Meteo로 자동 전환.
- **대기질(PM10/PM2.5)**: 1순위 KMA/AirKorea 실시간측정정보(`getCtprvnRltmMesureDnsty`, 경기도 전체 조회 후 코스와 가장 가까운 관측소를 거리 계산으로 선택), 실패 시 Open-Meteo 대기질 API로 자동 전환.
- `KMA_SERVICE_KEY`가 아예 없으면 날씨/대기질 둘 다 처음부터 Open-Meteo만 사용합니다.
- 화면에 표시되는 "○시 관측 기준"은 **데이터를 받아온 시각이 아니라, 그 수치가 대표하는 관측 시각**입니다. KMA 특성상 최대 1시간, 여기에 GitHub Actions 스케줄 지연이 더해지면 그 이상 차이 날 수 있습니다.

## 로컬에서 실행하기

```bash
python -m venv .venv
source .venv/bin/activate
pip install requests

# KMA로 시도 후 실패 시 Open-Meteo로 자동 폴백
python fetch_weather.py --provider kma --air-provider kma --kma-service-key <KMA_SERVICE_KEY>

# 키 없이 Open-Meteo만 쓰려면
python fetch_weather.py --provider open-meteo --air-provider open-meteo
```

실행하면 `data/src_weather.json`이 갱신됩니다. 프론트엔드는 정적 파일이라 아무 로컬 서버로 띄우면 됩니다:

```bash
python -m http.server 8000
# 브라우저에서 http://localhost:8000 접속
```

## 운용 설정

### 실행 트리거 구조 (GitHub 자체 스케줄 + 외부 cron-job.org)

GitHub Actions의 `schedule` 트리거는 GitHub 인프라 특성상 예정 시각보다 훨씬 늦게(경우에 따라 수 시간) 발동될 수 있습니다. GitHub는 `schedule` 이벤트를 다른 트리거보다 낮은 우선순위로 처리하기 때문에 코드/설정을 아무리 바꿔도 이 지연 자체는 근본적으로 없앨 수 없습니다. 그래서 이 저장소는 두 가지 트리거를 병행합니다.

- **외부 스케줄러(cron-job.org)가 `workflow_dispatch`를 API로 직접 호출**: 매시 0분·30분에 정확히 트리거되는 실질적인 주 트리거.
- **GitHub 자체 `schedule`**: `.github/workflows/update_weather.yml`의 `schedule.cron` (현재 `"15 * * * *"`, 매시 15분 1회). cron-job.org가 어떤 이유로든(토큰 만료, 계정 문제 등) 실패했을 때를 대비한 백업.

**두 트리거를 항상 동시에 켜둡니다.** 데이터를 매번 덮어쓰는 방식이라 중복 실행돼도 문제가 없고, 퍼블릭 저장소라 Actions 실행 시간도 무료라 낭비도 아닙니다 — 끄고 켜는 토글 없이 둘 다 상시 활성 상태가 가장 튼튼합니다. GitHub 쪽 시각(15분)을 cron-job.org의 0분·30분과 겹치지 않게 잡아둔 것도, 혹시 cron-job.org가 한 타임을 놓쳐도 그 공백을 메워주기 위해서입니다.

### cron-job.org 연동 설정

1. **GitHub Fine-grained Personal Access Token 발급**
   - GitHub 프로필 → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token
   - Resource owner: 이 저장소를 소유한 계정/조직 (`suwonsrc`)
   - Repository access: **Only select repositories** → `suwonsrc/weather`
   - Permissions → Repository permissions → **Actions: Read and write** (다른 권한은 불필요)
   - Expiration: 1년으로 설정 (아래 "매년 갱신" 참고)

2. **cron-job.org에 Job 생성**

   | 항목 | 값 |
   |---|---|
   | URL | `https://api.github.com/repos/suwonsrc/weather/actions/workflows/update_weather.yml/dispatches` |
   | Method | `POST` |
   | Headers | `Accept: application/vnd.github+json`<br>`Authorization: Bearer <위 1번 토큰>`<br>`X-GitHub-Api-Version: 2022-11-28`<br>`Content-Type: application/json` |
   | Body | `{"ref":"main"}` |
   | Schedule | 원하는 주기 (예: `*/30 * * * *`, cron-job.org는 GitHub와 달리 1분 단위까지 정확하게 지원) |

   설정 후 **Test run**으로 `204` 응답이 오는지 먼저 확인합니다. `401`이면 헤더가 저장 전에 테스트됐거나 `Authorization` 값에 `Bearer ` 접두어/공백이 빠진 경우가 대부분입니다.

3. GitHub Actions 탭에 `workflow_dispatch` 실행이 새로 생기는지 확인하면 설정 완료입니다.

### 매년 GitHub PAT 갱신 (예: 2026-07-25 발급 → 2027-07-25까지 갱신 필요)

Fine-grained PAT은 최장 1년까지만 유효합니다. 이 저장소는 **2026-07-25에 발급한 토큰을 기준으로 매년 7월 25일 전에 갱신**해야 cron-job.org 트리거가 끊기지 않습니다. 만료되면 cron-job.org 호출이 `401`로 실패하기 시작합니다(“execution of the cronjob fails” 알림을 켜뒀다면 이메일로 통보됨). GitHub 자체 `schedule` 백업이 있어서 사이트가 완전히 멈추진 않지만, 업데이트 주기가 매시 15분 1회로 뚝 떨어지니 방치하지 말고 갱신해야 합니다.

갱신 절차:
1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens에서 기존 토큰 선택
2. **Regenerate token** (같은 권한/저장소 범위 유지, 만료일만 갱신) — 옵션이 없으면 위 "cron-job.org 연동 설정 1번" 절차로 동일한 설정의 새 토큰을 다시 생성
3. 새 토큰 값 복사
4. cron-job.org → 해당 Job 편집 → Headers → `Authorization` 값을 `Bearer <새 토큰>`으로 교체 → 저장
5. **Test run**으로 `204` 확인
6. (새 토큰을 새로 만든 경우) GitHub에서 예전 토큰은 **Delete**로 정리

### 환경변수 / CLI 옵션 (`fetch_weather.py`)

| 이름 | 설명 | 기본값 |
|---|---|---|
| `KMA_SERVICE_KEY` (env) / `--kma-service-key` | data.go.kr에서 발급받은 서비스키. 없으면 자동으로 Open-Meteo로 전환 | 없음 |
| `--provider` | 날씨 데이터 소스 (`kma` \| `open-meteo`) | `kma` |
| `--air-provider` | 대기질 데이터 소스 (`kma` \| `open-meteo`) | `kma` |
| `KMA_AIR_SIDO_NAME` (env) / `--kma-air-sido-name` | AirKorea 조회 시도명. **"경기도"가 아니라 "경기"처럼 짧은 이름**이어야 정상 조회됨 | `경기` |

### 코스 추가/수정
`src/config.py`의 `COURSES` 리스트에 `Course(id, name_ko, name_en, lat, lon, location_ko, location_en, name_en_short, location_en_short)`를 추가/수정합니다. 대기질 관측소 매칭 정확도를 높이려면 `KMA_AIR_STATION_COORDS`에 해당 지역과 가까운 AirKorea 관측소 좌표도 함께 보완하는 게 좋습니다.

## GitHub Secrets에 API 키 등록하기 (보안)

**API 키는 절대 코드나 워크플로우 파일에 직접 적으면 안 됩니다.** 커밋 이력에 그대로 남아 공개 저장소라면 누구나 볼 수 있게 됩니다. 대신 GitHub의 암호화된 Secrets 기능을 씁니다 — 워크플로우 실행 중에만 환경변수로 주입되고, 로그에도 자동으로 마스킹(`***`)됩니다.

### 등록 절차
1. 저장소 페이지에서 **Settings** 탭 이동
2. 왼쪽 메뉴 **Secrets and variables → Actions**
3. **New repository secret** 클릭
4. Name에 정확히 `KMA_SERVICE_KEY` 입력 (워크플로우 파일의 `${{ secrets.KMA_SERVICE_KEY }}`와 이름이 일치해야 함)
5. Value에 data.go.kr에서 발급받은 서비스키(디코딩 키) 값을 붙여넣고 저장

등록 후에는 `.github/workflows/update_weather.yml`의 아래 부분이 자동으로 그 값을 읽어 씁니다:
```yaml
env:
  KMA_SERVICE_KEY: ${{ secrets.KMA_SERVICE_KEY }}
```

### 키 발급 (data.go.kr 공공데이터포털)
아래 두 Open API 상품을 **각각** "활용신청" 해야 합니다 (하나 신청했다고 다른 것도 자동으로 되지 않음):
- 기상청_단기예보 조회서비스 (초단기실황/초단기예보 — `getUltraSrtNcst`, `getUltraSrtFcst`)
- 한국환경공단_에어코리아_대기오염정보 (`getCtprvnRltmMesureDnsty`, 시도별 실시간 측정정보 조회)

승인 후 마이페이지에서 확인 가능한 "일반 인증키(Decoding)" 값을 위 Secrets 등록 절차의 Value로 사용하면 됩니다.

### 로컬에서 테스트할 때
로컬 환경에는 절대 키를 파일로 저장하지 말고(예: `.env`도 `.gitignore`에 포함돼 있긴 하지만), 실행할 때마다 셸 환경변수로만 넘기는 걸 권장합니다:
```bash
export KMA_SERVICE_KEY='발급받은키'
python fetch_weather.py --provider kma --air-provider kma
```
