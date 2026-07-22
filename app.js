let currentLang = "ko";
let LAST_DATA = null;

const statusEl = document.getElementById("status");
const coursesEl = document.getElementById("courses");
const appTitleEl = document.getElementById("app-title");
const appSubtitleEl = document.getElementById("app-subtitle");
const courseListUpdatedEl = document.getElementById("course-list-updated");

// 다중 앤드포인트 URL (GitHub Raw는 CORS 완전 허용 및 Push 즉시 반영됨)
const JSON_URLS = [
  "https://raw.githubusercontent.com/jcoderain/src-weather/main/data/src_weather.json",
  "https://jcoderain.github.io/src-weather/data/src_weather.json",
  "./data/src_weather.json"
];

const uiText = {
  appTitle: {
    ko: "SRC Weather",
    en: "SRC Weather",
  },
  appSubtitle: {
    ko: "SRC 러너들을 위한 수원 12개 러닝 코스 기상 모니터링",
    en: "Current course conditions for 12 SRC running courses",
  },
  statusLoading: {
    ko: "SRC 러너용 기상 데이터를 불러오는 중…",
    en: "Loading weather data for SRC runners…",
  },
  statusLoaded: (count) => ({
    ko: `SRC의 주요 ${count}개 코스 현황을 한눈에 확인하세요. 화이팅! 🏃‍♂️`,
    en: `Current conditions for ${count} major SRC courses. Fighting! 🏃‍♂️`,
  }),
  fail: {
    ko: "코스 데이터를 불러오는데 실패했습니다. 잠시 후 다시 시도해 주세요.",
    en: "Failed to load course data. Please try again later.",
  },
  outfitTitle: {
    ko: "👕 추천 복장 가이드",
    en: "👕 Outfit Guide",
  },
  paceTitle: {
    ko: "⏱️ 러닝 페이스 & 안전 팁",
    en: "⏱️ Pace & Safety Tip",
  },
  tempLabel: { ko: "기온 / 체감", en: "Air / Feels" },
  windLabel: { ko: "바람", en: "Wind" },
  precipLabel: { ko: "습도 / 예보강수", en: "Hum / Forecast Rain" },
  airLabel: { ko: "공기질 (PM)", en: "Air Quality" },
  openMap: { ko: "구글맵 지점 보기 📍", en: "View on Google Maps 📍" },
};

function applyLanguage() {
  if (appTitleEl) appTitleEl.textContent = uiText.appTitle[currentLang];
  if (appSubtitleEl) appSubtitleEl.textContent = uiText.appSubtitle[currentLang];

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    const lang = btn.dataset.lang;
    if (lang === currentLang) btn.classList.add("active");
    else btn.classList.remove("active");
  });

  renderStatus();
  renderUpdatedAt();
  renderAllCourses();
}

function formatUpdatedAtLocalized(isoLikeStr) {
  if (!isoLikeStr) return "";
  const parts = String(isoLikeStr).split("T");
  if (parts.length < 2) return "";
  const datePart = parts[0];
  const timePart = parts[1];
  
  const [y, m, d] = datePart.split("-");
  const [hh, mm] = timePart.split(":");
  const pad2 = (v) => String(v || "00").padStart(2, "0");

  if (currentLang === "ko") {
    return `${y}년 ${Number(m)}월 ${Number(d)}일 ${pad2(hh)}시 ${pad2(mm)}분 수집 기준`;
  } else {
    return `Updated at ${y}-${pad2(m)}-${pad2(d)} ${pad2(hh)}:${pad2(mm)} (KST)`;
  }
}

function getCommonUpdatedAt() {
  if (!LAST_DATA) return null;
  const courses = LAST_DATA.courses || [];
  if (!courses.length) return null;
  return courses[0].updated_at || null;
}

function renderUpdatedAt() {
  if (!courseListUpdatedEl) return;
  const iso = getCommonUpdatedAt();
  if (!iso) {
    courseListUpdatedEl.textContent = "";
    return;
  }
  courseListUpdatedEl.textContent = formatUpdatedAtLocalized(iso);
}

function windDirectionToText(deg) {
  if (deg == null || typeof deg !== "number" || isNaN(deg)) return "-";
  const dirsKo = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"];
  const dirsEn = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const idx = Math.round((deg % 360) / 45) % 8;
  const validIdx = isNaN(idx) ? 0 : (idx < 0 ? idx + 8 : idx);
  return currentLang === "ko" ? dirsKo[validIdx] : dirsEn[validIdx];
}

function getScoreColor(score) {
  const s = Number(score) || 0;
  if (s >= 80) return "#10b981"; // Emerald
  if (s >= 60) return "#3b82f6"; // Blue
  if (s >= 40) return "#f59e0b"; // Amber
  return "#ef4444"; // Red
}

function createScoreGaugeSvg(score) {
  const numScore = Number(score) || 0;
  const color = getScoreColor(numScore);
  const radius = 22;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (numScore / 100) * circumference;

  return `
    <div class="score-gauge-wrap">
      <svg class="gauge-svg" viewBox="0 0 52 52">
        <circle class="gauge-bg" cx="26" cy="26" r="${radius}"></circle>
        <circle class="gauge-fill" cx="26" cy="26" r="${radius}" 
          stroke="${color}" 
          stroke-dasharray="${circumference}" 
          stroke-dashoffset="${strokeDashoffset}"></circle>
      </svg>
      <span class="gauge-score-val" style="color: ${color}">${score ?? "?"}</span>
    </div>
  `;
}

function classifyAirQualityText(pm10, pm25) {
  if (pm10 == null && pm25 == null) return "-";
  const pm10Str = pm10 != null && typeof pm10 === "number" ? `PM10 ${pm10.toFixed(0)}` : "";
  const pm25Str = pm25 != null && typeof pm25 === "number" ? `PM2.5 ${pm25.toFixed(0)}` : "";
  const res = [pm10Str, pm25Str].filter(Boolean).join(" · ");
  return res || "-";
}

function renderCourseCard(info) {
  if (!info) return document.createElement("div");

  const div = document.createElement("div");
  div.className = "course-card";

  const displayName = currentLang === "ko" ? (info.name_ko || info.name || "코스") : (info.name_en || info.name || "Course");
  const windDirText = windDirectionToText(info.wind_direction);
  const windSpeedText = info.wind_speed != null && typeof info.wind_speed === "number" ? `${info.wind_speed.toFixed(1)}m/s` : "-";
  
  const temp = info.temperature != null && typeof info.temperature === "number" ? info.temperature.toFixed(1) : "-";
  const apparent = info.apparent_temperature != null && typeof info.apparent_temperature === "number" ? info.apparent_temperature.toFixed(1) : "-";
  const humidity = info.humidity != null && typeof info.humidity === "number" ? `${info.humidity.toFixed(0)}%` : "60%";
  
  const rainVal = info.forecast_rain_3h ?? info.recent_rain_3h ?? 0;
  const forecastRain = typeof rainVal === "number" ? `${rainVal.toFixed(1)}mm` : "0.0mm";
  
  const airText = classifyAirQualityText(info.pm10, info.pm25);

  const outfit = currentLang === "ko" 
    ? (info.outfit_ko || "통풍 좋은 반팔 T셔츠 + 러닝 숏츠") 
    : (info.outfit_en || "Breathable short-sleeve T-shirt & running shorts");

  const paceTip = currentLang === "ko"
    ? (info.pace_tip_ko || info.advice_detail_ko || "컨디션에 따라 페이스를 조절하세요.")
    : (info.pace_tip_en || info.advice_detail_en || "Adjust pace according to weather conditions.");

  const rawTags = currentLang === "ko" ? (info.tags_ko || []) : (info.tags_en || []);
  const safeTags = Array.isArray(rawTags) ? rawTags.filter(t => typeof t === "string" && t.trim() !== "") : [];

  const lat = typeof info.lat === "number" ? info.lat : null;
  const lon = typeof info.lon === "number" ? info.lon : null;
  const googleLink = lat != null && lon != null 
    ? `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`
    : null;

  div.innerHTML = `
    <div>
      <div class="card-header-row">
        <div class="course-name-box">
          <h2 class="course-name">${displayName}</h2>
          <span class="course-location-sub">GPS ${lat ? lat.toFixed(3) : ''}, ${lon ? lon.toFixed(3) : ''}</span>
        </div>
        ${createScoreGaugeSvg(info.run_score ?? 0)}
      </div>

      <div class="metrics-grid">
        <div class="metric-item">
          <span class="metric-icon">🌡️</span>
          <div class="metric-data">
            <span class="metric-label">${uiText.tempLabel[currentLang]}</span>
            <span class="metric-val">${temp}°C <span style="font-weight:400; font-size:0.75rem; color:#94a3b8;">(${apparent}°C)</span></span>
          </div>
        </div>

        <div class="metric-item">
          <span class="metric-icon">💨</span>
          <div class="metric-data">
            <span class="metric-label">${uiText.windLabel[currentLang]}</span>
            <span class="metric-val">${windDirText} ${windSpeedText}</span>
          </div>
        </div>

        <div class="metric-item">
          <span class="metric-icon">💧</span>
          <div class="metric-data">
            <span class="metric-label">${uiText.precipLabel[currentLang]}</span>
            <span class="metric-val">${humidity} · ${forecastRain}</span>
          </div>
        </div>

        <div class="metric-item">
          <span class="metric-icon">😷</span>
          <div class="metric-data">
            <span class="metric-label">${uiText.airLabel[currentLang]}</span>
            <span class="metric-val">${airText}</span>
          </div>
        </div>
      </div>

      <div class="tags-group">
        ${safeTags.map(t => {
          let extraClass = "";
          if (t.includes("좋음") || t.includes("최적") || t.includes("Good") || t.includes("Optimal")) extraClass = "tag-great";
          else if (t.includes("주의") || t.includes("Caution") || t.includes("젖음")) extraClass = "tag-caution";
          else if (t.includes("위험") || t.includes("나쁨") || t.includes("Extreme")) extraClass = "tag-risk";
          return `<span class="badge-tag ${extraClass}">${t}</span>`;
        }).join("")}
      </div>

      <div class="advice-section">
        <div class="advice-card advice-outfit">
          <div class="advice-title">${uiText.outfitTitle[currentLang]}</div>
          <div>${outfit}</div>
        </div>
        <div class="advice-card advice-pace">
          <div class="advice-title">${uiText.paceTitle[currentLang]}</div>
          <div>${paceTip}</div>
        </div>
      </div>
    </div>

    <div class="card-bottom-bar">
      <span class="location-coords">수원/경기 코스</span>
      ${googleLink ? `<a href="${googleLink}" target="_blank" rel="noopener" class="map-btn">${uiText.openMap[currentLang]}</a>` : ""}
    </div>
  `;
  return div;
}

function renderAllCourses() {
  if (!coursesEl || !LAST_DATA || !LAST_DATA.courses) return;
  const courses = LAST_DATA.courses;
  coursesEl.innerHTML = "";

  courses.forEach((info) => {
    try {
      coursesEl.appendChild(renderCourseCard(info));
    } catch (e) {
      console.error("Error rendering course card:", e, info);
    }
  });
}

function renderStatus() {
  if (!statusEl) return;
  if (!LAST_DATA) {
    statusEl.innerHTML = `<p>${uiText.statusLoading[currentLang]}</p>`;
    return;
  }
  const courses = LAST_DATA.courses || [];
  const text = uiText.statusLoaded(courses.length)[currentLang];
  statusEl.innerHTML = `<p>${text}</p>`;
}

function setupEventListeners() {
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      currentLang = e.target.dataset.lang;
      applyLanguage();
    });
  });
}

async function fetchWeatherData() {
  const timestamp = Date.now();
  let lastError = null;

  for (const url of JSON_URLS) {
    try {
      const resp = await fetch(`${url}?t=${timestamp}`, { cache: "no-store" });
      if (resp.ok) {
        const json = await resp.json();
        if (json && Array.isArray(json.courses)) {
          return json;
        }
      }
    } catch (e) {
      console.warn(`Fetch failed for ${url}:`, e);
      lastError = e;
    }
  }

  throw lastError || new Error("All JSON fetch attempts failed");
}

async function init() {
  try {
    setupEventListeners();
    applyLanguage();
    renderStatus();

    const data = await fetchWeatherData();
    LAST_DATA = data;

    renderStatus();
    renderUpdatedAt();
    renderAllCourses();
  } catch (err) {
    console.error("Failed to load weather data:", err);
    if (statusEl) {
      statusEl.innerHTML = `<p style="color: #ef4444;">${uiText.fail[currentLang]}</p>`;
    }
  }
}

document.addEventListener("DOMContentLoaded", init);
