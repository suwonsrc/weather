let currentLang = "ko";
let LAST_DATA = null;
let currentTheme = localStorage.getItem("theme") || "light";

const statusEl = document.getElementById("status");
const coursesEl = document.getElementById("courses");
const appTitleEl = document.getElementById("app-title");
const courseListUpdatedEl = document.getElementById("course-list-updated");
const summaryShortcutsEl = document.getElementById("summary-shortcuts");

// 다중 앤드포인트 URL (GitHub Raw는 CORS 완전 허용 및 Push 즉시 반영됨)
const JSON_URLS = [
  "./data/src_weather.json",
  "https://raw.githubusercontent.com/jcoderain/src-weather/main/data/src_weather.json",
  "https://jcoderain.github.io/src-weather/data/src_weather.json"
];

const uiText = {
  appTitle: {
    ko: "SRC Weather",
    en: "SRC Weather",
  },
  statusLoading: {
    ko: "기상 데이터를 불러오는 중…",
    en: "Loading weather data…",
  },
  statusLoaded: (count) => ({
    ko: "SRC 주요 코스 날씨 현황",
    en: "SRC Major Course Weather Status",
  }),
  fail: {
    ko: "코스 데이터를 불러오는데 실패했습니다. 잠시 후 다시 시도해 주세요.",
    en: "Failed to load course data. Please try again later.",
  },
  outfitTitle: {
    ko: "추천 복장 가이드",
    en: "Outfit Guide",
  },
  paceTitle: {
    ko: "러닝 페이스 & 안전 팁",
    en: "Pace & Safety Tip",
  },
  tempLabel: { ko: "기온 / 체감", en: "Air / Feels" },
  windLabel: { ko: "바람", en: "Wind" },
  precipLabel: { ko: "습도 / 예보강수", en: "Hum / Rain" },
  airLabel: { ko: "공기질 (PM)", en: "Air Quality" },
  openMap: { ko: "구글맵 지점 보기", en: "Google Maps" },
};

function applyTheme() {
  document.documentElement.setAttribute("data-theme", currentTheme);
  if (document.body) {
    document.body.setAttribute("data-theme", currentTheme);
  }
  const themeIcon = document.getElementById("theme-icon");
  if (themeIcon) {
    const sunIcon = `<svg class="svg-theme-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>`;
    const moonIcon = `<svg class="svg-theme-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>`;
    themeIcon.innerHTML = currentTheme === "dark" ? sunIcon : moonIcon;
  }
}

function toggleTheme() {
  currentTheme = currentTheme === "dark" ? "light" : "dark";
  localStorage.setItem("theme", currentTheme);
  applyTheme();
}

window.toggleTheme = toggleTheme;
window.applyTheme = applyTheme;
applyTheme();

function applyLanguage() {
  if (appTitleEl) appTitleEl.textContent = uiText.appTitle[currentLang];

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    const lang = btn.dataset.lang;
    if (lang === currentLang) btn.classList.add("active");
    else btn.classList.remove("active");
  });

  renderStatus();
  renderUpdatedAt();
  renderSummaryShortcuts();
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
  if (LAST_DATA.generated_at) return LAST_DATA.generated_at;
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

function getScoreGrade(score, explicitGrade) {
  if (explicitGrade && ["A", "B", "C", "D", "E"].includes(explicitGrade.toUpperCase())) {
    const g = explicitGrade.toUpperCase();
    if (g === "A") return { grade: "A", color: "#3b82f6", bgClass: "score-grade-a" };
    if (g === "B") return { grade: "B", color: "#10b981", bgClass: "score-grade-b" };
    if (g === "C") return { grade: "C", color: "#eab308", bgClass: "score-grade-c" };
    if (g === "D") return { grade: "D", color: "#f59e0b", bgClass: "score-grade-d" };
    return { grade: "E", color: "#ef4444", bgClass: "score-grade-e" };
  }

  const s = Number(score) || 0;
  if (s >= 80) return { grade: "A", color: "#3b82f6", bgClass: "score-grade-a" };
  if (s >= 65) return { grade: "B", color: "#10b981", bgClass: "score-grade-b" };
  if (s >= 50) return { grade: "C", color: "#eab308", bgClass: "score-grade-c" };
  if (s >= 35) return { grade: "D", color: "#f59e0b", bgClass: "score-grade-d" };
  return { grade: "E", color: "#ef4444", bgClass: "score-grade-e" };
}

function getScoreColor(score) {
  return getScoreGrade(score).color;
}

function createScoreGaugeSvg(score, grade) {
  const numScore = Number(score) || 0;
  const gradeInfo = getScoreGrade(numScore, grade);
  const radius = 22;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (numScore / 100) * circumference;

  return `
    <div class="score-gauge-wrap">
      <svg class="gauge-svg" viewBox="0 0 52 52">
        <circle class="gauge-bg" cx="26" cy="26" r="${radius}"></circle>
        <circle class="gauge-fill" cx="26" cy="26" r="${radius}" 
          stroke="${gradeInfo.color}" 
          stroke-dasharray="${circumference}" 
          stroke-dashoffset="${strokeDashoffset}"></circle>
      </svg>
      <span class="gauge-score-val" style="color: ${gradeInfo.color}">${gradeInfo.grade}</span>
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

function stripEmojis(str) {
  if (!str || typeof str !== "string") return "";
  return str.replace(/[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]/gu, "").trim();
}

const metricIcons = {
  temp: `<svg class="svg-metric-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/><path d="M12 9v4"/></svg>`,
  wind: `<svg class="svg-metric-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/></svg>`,
  precip: `<svg class="svg-metric-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7Z"/></svg>`,
  air: `<svg class="svg-metric-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>`
};

const titleIcons = {
  outfit: `<svg class="svg-title-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.38 3.46 16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z"/></svg>`,
  pace: `<svg class="svg-title-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`
};

function renderCourseCard(info) {
  if (!info) return document.createElement("div");

  const div = document.createElement("div");
  div.className = "course-card";
  if (info.id) {
    div.id = `course-card-${info.id}`;
  }

  const displayName = currentLang === "ko" ? (info.name_ko || info.name || "코스") : (info.name_en || info.name || "Course");
  const windDirText = windDirectionToText(info.wind_direction);
  const windSpeedText = info.wind_speed != null && typeof info.wind_speed === "number" ? `${info.wind_speed.toFixed(1)}m/s` : "-";
  
  const temp = info.temperature != null && typeof info.temperature === "number" ? info.temperature.toFixed(1) : "-";
  const apparent = info.apparent_temperature != null && typeof info.apparent_temperature === "number" ? info.apparent_temperature.toFixed(1) : "-";
  const humidity = info.humidity != null && typeof info.humidity === "number" ? `${info.humidity.toFixed(0)}%` : "60%";
  
  const rainVal = info.forecast_rain_3h ?? info.recent_rain_3h ?? 0;
  const forecastRain = typeof rainVal === "number" ? `${rainVal.toFixed(1)}mm` : "0.0mm";
  
  const airText = classifyAirQualityText(info.pm10, info.pm25);

  const rawOutfit = currentLang === "ko" 
    ? (info.outfit_ko || "통풍 좋은 반팔 T셔츠 + 러닝 숏츠") 
    : (info.outfit_en || "Breathable short-sleeve T-shirt & running shorts");

  const rawPaceTip = currentLang === "ko"
    ? (info.pace_tip_ko || info.advice_detail_ko || "컨디션에 따라 페이스를 조절하세요.")
    : (info.pace_tip_en || info.advice_detail_en || "Adjust pace according to weather conditions.");

  const outfit = stripEmojis(rawOutfit);
  const paceTip = stripEmojis(rawPaceTip);

  const rawTags = currentLang === "ko" ? (info.tags_ko || []) : (info.tags_en || []);
  const safeTags = Array.isArray(rawTags) ? rawTags.filter(t => typeof t === "string" && t.trim() !== "") : [];

  const lat = typeof info.lat === "number" ? info.lat : null;
  const lon = typeof info.lon === "number" ? info.lon : null;
  const googleLink = lat != null && lon != null 
    ? `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`
    : null;

  const locationText = currentLang === "ko" 
    ? (info.location_ko || "수원시 코스") 
    : (info.location_en || "Suwon Area");

  div.innerHTML = `
    <div>
      <div class="card-header-row">
        <div class="course-name-box">
          <h2 class="course-name">${displayName}</h2>
        </div>
        ${createScoreGaugeSvg(info.run_score ?? 0, info.run_grade)}
      </div>

      <div class="metrics-grid">
        <div class="metric-item">
          <span class="metric-icon-wrap">${metricIcons.temp}</span>
          <div class="metric-data">
            <span class="metric-label">${uiText.tempLabel[currentLang]}</span>
            <span class="metric-val">${temp}°C <span style="font-weight:400; font-size:0.75rem; color:var(--text-muted);">(${apparent}°C)</span></span>
          </div>
        </div>

        <div class="metric-item">
          <span class="metric-icon-wrap">${metricIcons.wind}</span>
          <div class="metric-data">
            <span class="metric-label">${uiText.windLabel[currentLang]}</span>
            <span class="metric-val">${windDirText} ${windSpeedText}</span>
          </div>
        </div>

        <div class="metric-item">
          <span class="metric-icon-wrap">${metricIcons.precip}</span>
          <div class="metric-data">
            <span class="metric-label">${uiText.precipLabel[currentLang]}</span>
            <span class="metric-val">${humidity} · ${forecastRain}</span>
          </div>
        </div>

        <div class="metric-item">
          <span class="metric-icon-wrap">${metricIcons.air}</span>
          <div class="metric-data">
            <span class="metric-label">${uiText.airLabel[currentLang]}</span>
            <span class="metric-val">${airText}</span>
          </div>
        </div>
      </div>

      <div class="tags-group">
        ${safeTags.map(t => {
          let extraClass = "";
          if (t.includes("최적") || t.includes("쾌적") || t.includes("건조") || t.includes("공기좋음") || t.includes("Good") || t.includes("Optimal") || t.includes("Comfortable") || t.includes("Dry")) {
            extraClass = "tag-great";
          } else if (t.includes("더움") || t.includes("다소바람") || t.includes("살짝젖음") || t.includes("공기보통") || t.includes("Warm") || t.includes("Damp")) {
            extraClass = "tag-caution";
          } else if (t.includes("찜통") || t.includes("폭염") || t.includes("쌀쌀") || t.includes("혹한") || t.includes("강풍") || t.includes("노면젖음") || t.includes("폭우") || t.includes("결빙") || t.includes("눈슬러시") || t.includes("공기나쁨") || t.includes("황사경보") || t.includes("Bad") || t.includes("Severe")) {
            extraClass = "tag-risk";
          }
          return `<span class="badge-tag ${extraClass}">${t}</span>`;
        }).join("")}
      </div>

      <div class="advice-section">
        <div class="advice-card advice-outfit">
          <div class="advice-title">${titleIcons.outfit} ${uiText.outfitTitle[currentLang]}</div>
          <div>${outfit}</div>
        </div>
        <div class="advice-card advice-pace">
          <div class="advice-title">${titleIcons.pace} ${uiText.paceTitle[currentLang]}</div>
          <div>${paceTip}</div>
        </div>
      </div>
    </div>

    <div class="card-bottom-bar">
      <span class="location-coords">GPS: ${lat ? lat.toFixed(3) : ''}, ${lon ? lon.toFixed(3) : ''}</span>
      ${googleLink ? `<a href="${googleLink}" target="_blank" rel="noopener" class="map-btn">${uiText.openMap[currentLang]}</a>` : ""}
    </div>
  `;
  return div;
}

function getSortedCourses() {
  if (!LAST_DATA || !Array.isArray(LAST_DATA.courses)) return [];
  return [...LAST_DATA.courses]
    .map((course, idx) => ({ course, idx }))
    .sort((a, b) => {
      const scoreA = Number(a.course.run_score ?? 0);
      const scoreB = Number(b.course.run_score ?? 0);
      if (scoreB !== scoreA) {
        return scoreB - scoreA;
      }
      if (currentLang === "ko") {
        const nameA = String(a.course.name_ko || a.course.name || "");
        const nameB = String(b.course.name_ko || b.course.name || "");
        const comp = nameA.localeCompare(nameB, "ko");
        if (comp !== 0) return comp;
      } else {
        const nameA = String(a.course.name_en || a.course.name_en_short || a.course.name || "");
        const nameB = String(b.course.name_en || b.course.name_en_short || b.course.name || "");
        const comp = nameA.localeCompare(nameB, "en", { sensitivity: "base" });
        if (comp !== 0) return comp;
      }
      return a.idx - b.idx;
    })
    .map(item => item.course);
}

let selectedCourseId = null;

function renderSummaryShortcuts() {
  if (!summaryShortcutsEl || !LAST_DATA || !LAST_DATA.courses) return;
  const courses = getSortedCourses();
  if (!courses.length) return;

  if (!selectedCourseId || !courses.find(c => c.id === selectedCourseId)) {
    selectedCourseId = courses[0].id;
  }

  const gridDiv = document.createElement("div");
  gridDiv.className = "shortcut-grid";

  courses.forEach((c) => {
    const chip = document.createElement("button");
    chip.className = `shortcut-chip ${c.id === selectedCourseId ? "active" : ""}`;

    const name = currentLang === "ko" ? (c.name_ko || c.name) : (c.name_en_short || c.name_en || c.name);
    const score = c.run_score ?? 0;
    const gradeInfo = getScoreGrade(score, c.run_grade);

    chip.innerHTML = `
      <span class="shortcut-name">${name}</span>
      <span class="shortcut-score ${gradeInfo.bgClass}">${gradeInfo.grade}</span>
    `;

    chip.addEventListener("click", () => {
      selectedCourseId = c.id;
      document.querySelectorAll(".shortcut-chip").forEach((ch) => ch.classList.remove("active"));
      chip.classList.add("active");
      renderAllCourses();
    });

    gridDiv.appendChild(chip);
  });

  summaryShortcutsEl.innerHTML = "";
  summaryShortcutsEl.appendChild(gridDiv);
}

function renderAllCourses() {
  if (!coursesEl || !LAST_DATA || !LAST_DATA.courses) return;
  const courses = getSortedCourses();
  if (!courses.length) return;

  if (!selectedCourseId || !courses.find(c => c.id === selectedCourseId)) {
    selectedCourseId = courses[0].id;
  }

  const selectedCourse = courses.find(c => c.id === selectedCourseId) || courses[0];
  coursesEl.innerHTML = "";

  try {
    coursesEl.appendChild(renderCourseCard(selectedCourse));
  } catch (e) {
    console.error("Error rendering course card:", e, selectedCourse);
  }
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
  const themeBtn = document.getElementById("theme-toggle");
  if (themeBtn) {
    themeBtn.addEventListener("click", toggleTheme);
  }

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
    applyTheme();
    setupEventListeners();
    applyLanguage();
    renderStatus();

    const data = await fetchWeatherData();
    LAST_DATA = data;

    renderStatus();
    renderUpdatedAt();
    renderSummaryShortcuts();
    renderAllCourses();
  } catch (err) {
    console.error("Failed to load weather data:", err);
    if (statusEl) {
      statusEl.innerHTML = `<p style="color: #ef4444;">${uiText.fail[currentLang]}</p>`;
    }
  }
}

document.addEventListener("DOMContentLoaded", init);
