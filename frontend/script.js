const FIELDS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"];

let lastData = null;

function cropImage(crop) {
  return `images/crops/${crop.toLowerCase()}.jpg`;
}

// ── Auth screens: Welcome / Log In / Sign Up, plus session bootstrap ───────
const SLIDESHOW_CROPS = [
  "apple", "banana", "cabbage", "carrot", "cashew", "cassava", "coconut",
  "coffee", "cotton", "cowpea", "cucumber", "garlic", "ginger", "groundnut",
  "guava", "lettuce", "maize", "mango", "millet", "okra", "onion", "orange",
  "pear", "pepper", "potato", "rice", "rubber", "soybean", "sugarcane",
  "tomato", "watermelon", "wheat", "yam",
];

function initAuthSlideshow() {
  const container = document.getElementById("auth-slideshow");
  const order = [...SLIDESHOW_CROPS].sort(() => Math.random() - 0.5);

  const layerA = document.createElement("div");
  const layerB = document.createElement("div");
  layerA.className = "auth-slide active";
  layerB.className = "auth-slide";
  layerA.style.backgroundImage = `url(${cropImage(order[0])})`;
  container.append(layerA, layerB);

  let i = 0;
  let onA = true;
  setInterval(() => {
    i = (i + 1) % order.length;
    const incoming = onA ? layerB : layerA;
    const outgoing = onA ? layerA : layerB;
    incoming.style.backgroundImage = `url(${cropImage(order[i])})`;
    incoming.classList.add("active");
    outgoing.classList.remove("active");
    onA = !onA;
  }, 3500);
}

function showAuthView(view) {
  document.querySelectorAll(".auth-view").forEach((v) => v.classList.remove("active"));
  document.querySelector(`.auth-view[data-auth-view="${view}"]`).classList.add("active");
}

document.querySelectorAll("[data-go]").forEach((el) => {
  el.addEventListener("click", (e) => {
    e.preventDefault();
    showAuthView(el.dataset.go);
  });
});

function showAuthScreen() {
  document.getElementById("auth-screen").classList.remove("hidden");
  document.getElementById("app-root").classList.add("hidden");
  showAuthView("welcome");
}

let currentUser = null;

function showApp(user) {
  currentUser = user;
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("app-root").classList.remove("hidden");
  updateProfileView(user);
  showView("dashboard");
  loadRandomSample();
}

function updateProfileView(user) {
  document.getElementById("profile-name").textContent = user.full_name;
  document.getElementById("profile-email").textContent = user.email;
  const initials = user.full_name.trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  document.getElementById("profile-initials").textContent = initials || "?";
}

function setAuthError(id, message) {
  const el = document.getElementById(id);
  if (!message) { el.style.display = "none"; el.textContent = ""; return; }
  el.textContent = message;
  el.style.display = "block";
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setAuthError("login-error", "");
  const submitBtn = document.getElementById("login-submit");
  submitBtn.disabled = true;
  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: document.getElementById("login-email").value,
        password: document.getElementById("login-password").value,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not log in.");
    showApp(data);
  } catch (err) {
    setAuthError("login-error", err.message);
  } finally {
    submitBtn.disabled = false;
  }
});

document.getElementById("signup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setAuthError("signup-error", "");
  const submitBtn = document.getElementById("signup-submit");
  submitBtn.disabled = true;
  try {
    const res = await fetch("/api/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: document.getElementById("signup-name").value,
        email: document.getElementById("signup-email").value,
        password: document.getElementById("signup-password").value,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not create account.");
    showApp(data);
  } catch (err) {
    setAuthError("signup-error", err.message);
  } finally {
    submitBtn.disabled = false;
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  currentUser = null;
  showAuthScreen();
});

// ── Voice feature: reads English text aloud via the browser's built-in
// speech synthesis (no server round-trip, no translation). Each item in the
// lines array is spoken as its own sentence, with a short rest before the
// next one begins. Clicking the button again while it's playing stops it. ──
function cropSpeechText(rec) {
  const pct = Math.round(rec.confidence * 100);
  return [`${rec.crop}, ${pct} percent match.`, ...(rec.reasons || [])];
}

function speechFriendly(line) {
  return line
    .replace(/kg\/ha/gi, "kilograms per hectare")
    .replace(/°C/g, "degree Celsius");
}

const LINE_PAUSE_MS = 1000;
let speechToken = 0;
let speechTimeoutId = null;
let activeSpeechBtn = null;
let activeSpeechReset = null;

function stopActiveSpeech() {
  speechToken++; // invalidate any in-flight callbacks/timers from the current playback
  window.speechSynthesis.cancel();
  if (speechTimeoutId) { clearTimeout(speechTimeoutId); speechTimeoutId = null; }
  if (activeSpeechReset) activeSpeechReset();
  activeSpeechBtn = null;
  activeSpeechReset = null;
}

function speakInEnglish(lines, btn) {
  if (!window.speechSynthesis) return;

  const wasThisButton = activeSpeechBtn === btn;
  stopActiveSpeech();
  if (wasThisButton) return; // clicking a playing button again just stops it

  if (!lines) return;
  const linesArr = Array.isArray(lines) ? lines : [lines];
  if (!linesArr.length) return;

  const myToken = ++speechToken;
  const label = btn.querySelector(".listen-label");
  const icon = btn.querySelector(".listen-icon");
  const originalLabel = label.textContent;
  const originalIcon = icon ? icon.textContent : "";

  const reset = () => {
    label.textContent = originalLabel;
    if (icon) icon.textContent = originalIcon;
  };
  activeSpeechBtn = btn;
  activeSpeechReset = reset;

  const speakLine = (i) => {
    if (myToken !== speechToken || i >= linesArr.length) { stopActiveSpeech(); return; }
    const utterance = new SpeechSynthesisUtterance(speechFriendly(linesArr[i]));
    utterance.lang = "en-US";
    utterance.rate = 0.85; // a bit slower, so units like "hectare" come through clearly

    utterance.addEventListener("start", () => {
      if (myToken !== speechToken) return;
      label.textContent = "Stop";
      if (icon) icon.textContent = "⏹";
    });
    utterance.addEventListener("end", () => {
      if (myToken !== speechToken) return;
      if (i + 1 < linesArr.length) {
        speechTimeoutId = setTimeout(() => speakLine(i + 1), LINE_PAUSE_MS);
      } else {
        stopActiveSpeech();
      }
    });
    utterance.addEventListener("error", () => { if (myToken === speechToken) stopActiveSpeech(); });

    window.speechSynthesis.speak(utterance);
  };

  speakLine(0);
}

function collectInputs() {
  const values = {};
  for (const f of FIELDS) {
    const el = document.getElementById("in-" + f);
    values[f] = el.value === "" ? null : parseFloat(el.value);
  }
  return values;
}

function fillInputs(values) {
  for (const f of FIELDS) {
    if (values[f] !== undefined && values[f] !== null) {
      document.getElementById("in-" + f).value = Math.round(values[f] * 100) / 100;
    }
  }
}

function setGauge(gaugeId, pct, colorVar) {
  const gauge = document.getElementById(gaugeId);
  const color = getComputedStyle(document.documentElement).getPropertyValue(colorVar).trim();
  const deg = Math.max(0, Math.min(100, pct)) * 3.6;
  gauge.style.background = `conic-gradient(${color} ${deg}deg, #e7e9e4 ${deg}deg)`;
}

function renderResult(data) {
  lastData = data;

  // pH gauge: scale 0-14 -> 0-100%
  const ph = data.readings.ph.value;
  document.getElementById("ph-value").textContent = ph.toFixed(1);
  document.getElementById("ph-label").textContent = data.readings.ph.label;
  setGauge("gauge-ph", (ph / 14) * 100, "--forest");

  // Moisture gauge from humidity
  const hum = data.readings.humidity.value;
  document.getElementById("moisture-value").textContent = Math.round(hum) + "%";
  document.getElementById("moisture-label").textContent = data.readings.humidity.label;
  setGauge("gauge-moisture", hum, "--green-light");

  // Weather card (temperature + rainfall, KNUST-style widget)
  const temp = data.readings.temperature;
  const rain = data.readings.rainfall;
  document.getElementById("weather-temp-value").textContent = temp.value.toFixed(1) + "°C";
  document.getElementById("weather-rainfall-value").textContent = Math.round(rain.value) + " mm";
  document.getElementById("weather-humidity-value").textContent = Math.round(data.readings.humidity.value) + "%";
  document.getElementById("weather-condition-value").textContent = `${temp.label}, ${rain.label} rain`;
  document.getElementById("weather-icon").textContent =
    rain.label === "High" ? "🌧️" : rain.label === "Moderate" ? "⛅" : "☀️";

  // N/P/K bars
  document.getElementById("bar-n").style.width = data.readings.N.percent + "%";
  document.getElementById("pct-n").textContent = data.readings.N.percent + "%";
  document.getElementById("trend-n").textContent = data.readings.N.percent >= 50 ? "↗" : "↘";
  document.getElementById("trend-n").style.color = data.readings.N.percent >= 50
    ? getComputedStyle(document.documentElement).getPropertyValue("--green-light")
    : getComputedStyle(document.documentElement).getPropertyValue("--red");

  document.getElementById("bar-p").style.width = data.readings.P.percent + "%";
  document.getElementById("pct-p").textContent = data.readings.P.percent + "%";
  document.getElementById("trend-p").textContent = data.readings.P.percent >= 50 ? "↗" : "↘";
  document.getElementById("trend-p").style.color = data.readings.P.percent >= 50
    ? getComputedStyle(document.documentElement).getPropertyValue("--green-light")
    : getComputedStyle(document.documentElement).getPropertyValue("--red");

  document.getElementById("bar-k").style.width = data.readings.K.percent + "%";
  document.getElementById("pct-k").textContent = data.readings.K.percent + "%";
  document.getElementById("trend-k").textContent = data.readings.K.percent >= 50 ? "↗" : "↘";
  document.getElementById("trend-k").style.color = data.readings.K.percent >= 50
    ? getComputedStyle(document.documentElement).getPropertyValue("--green-light")
    : getComputedStyle(document.documentElement).getPropertyValue("--red");

  // Recommendations
  const box = document.getElementById("recommendations");
  box.innerHTML = "";
  data.recommendations.forEach((rec, i) => {
    const pct = Math.round(rec.confidence * 100);
    const reasons = rec.reasons || [];
    const row = document.createElement("div");
    row.className = "crop-card";
    row.innerHTML = `
      <div class="crop-card-img-wrap">
        <img class="crop-card-img" src="${cropImage(rec.crop)}" alt="${rec.crop}" loading="lazy">
        <span class="crop-rank ${i === 0 ? "top" : ""}">${i + 1}</span>
      </div>
      <div class="crop-card-body">
        <div class="crop-card-head">
          <div class="crop-name">${rec.crop}</div>
          <div class="crop-conf">${pct}% match</div>
        </div>
        <div class="crop-bar-track"><div class="crop-bar-fill" style="width:${pct}%"></div></div>
        ${reasons.length ? `
          <button class="reasons-toggle" type="button" aria-expanded="false">
            <span>Why this crop?</span>
            <span class="reasons-chevron">&#9662;</span>
          </button>
          <ul class="crop-reasons" style="display:none;">${reasons.map((r) => `<li>${r}</li>`).join("")}</ul>
        ` : ""}
        <button class="listen-btn" type="button">
          <span class="listen-icon">&#128266;</span>
          <span class="listen-label">Listen</span>
        </button>
      </div>
    `;
    row.addEventListener("click", () => openCropDetail(rec));
    const toggle = row.querySelector(".reasons-toggle");
    if (toggle) {
      toggle.addEventListener("click", (e) => {
        e.stopPropagation();
        const list = row.querySelector(".crop-reasons");
        const open = list.style.display !== "none";
        list.style.display = open ? "none" : "flex";
        toggle.setAttribute("aria-expanded", String(!open));
        toggle.classList.toggle("open", !open);
      });
    }
    const listenBtn = row.querySelector(".listen-btn");
    listenBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      speakInEnglish(cropSpeechText(rec), listenBtn);
    });
    box.appendChild(row);
  });

  document.getElementById("fuzzy-note").style.display = data.used_fuzzy ? "block" : "none";

  renderTopPick(data);
  renderIdeas(data);
  renderFields(data);
}

function renderTopPick(data) {
  const top = data.recommendations[0];
  const pct = Math.round(top.confidence * 100);
  const img = cropImage(top.crop);

  document.getElementById("top-pick-placeholder").style.display = "none";

  const fgImg = document.getElementById("top-pick-img");
  fgImg.src = img;
  fgImg.alt = top.crop;
  fgImg.style.display = "block";

  document.getElementById("top-pick-name").textContent = top.crop;
  document.getElementById("top-pick-conf").textContent = `${pct}% match for your current soil sample`;
  document.getElementById("top-pick-overlay").style.display = "flex";

  const whyCard = document.getElementById("why-card");
  const whyList = document.getElementById("why-list");
  const whyToggle = document.getElementById("why-toggle");
  const reasons = top.reasons || [];
  if (reasons.length) {
    whyList.innerHTML = reasons.map((r) => `<li>${r}</li>`).join("");
    whyList.style.display = "none";
    whyToggle.setAttribute("aria-expanded", "false");
    whyToggle.classList.remove("open");
    whyCard.style.display = "block";
    currentTopSpeechText = cropSpeechText(top);
  } else {
    whyCard.style.display = "none";
    currentTopSpeechText = "";
  }
}

let currentTopSpeechText = "";
document.getElementById("why-listen-btn").addEventListener("click", () => {
  speakInEnglish(currentTopSpeechText, document.getElementById("why-listen-btn"));
});

document.getElementById("why-toggle").addEventListener("click", () => {
  const whyList = document.getElementById("why-list");
  const whyToggle = document.getElementById("why-toggle");
  const open = whyList.style.display !== "none";
  whyList.style.display = open ? "none" : "flex";
  whyToggle.setAttribute("aria-expanded", String(!open));
  whyToggle.classList.toggle("open", !open);
});

// ── Crop detail overlay (click a crop to read about it, alone, full screen) ──
function openCropDetail(rec) {
  const pct = Math.round(rec.confidence * 100);
  const img = cropImage(rec.crop);

  document.getElementById("crop-detail-img").src = img;
  document.getElementById("crop-detail-img").alt = rec.crop;
  document.getElementById("crop-detail-name").textContent = rec.crop;
  document.getElementById("crop-detail-conf").textContent = `${pct}% match for your current soil sample`;
  document.getElementById("crop-detail-reasons").innerHTML = (rec.reasons || []).map((r) => `<li>${r}</li>`).join("");
  currentDetailSpeechText = cropSpeechText(rec);

  document.getElementById("crop-detail-overlay").classList.add("open");
  document.body.style.overflow = "hidden";
}

let currentDetailSpeechText = "";
document.getElementById("crop-detail-listen-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  speakInEnglish(currentDetailSpeechText, document.getElementById("crop-detail-listen-btn"));
});

function closeCropDetail() {
  document.getElementById("crop-detail-overlay").classList.remove("open");
  document.body.style.overflow = "";
}

document.getElementById("top-pick").addEventListener("click", () => {
  if (lastData && lastData.recommendations && lastData.recommendations[0]) {
    openCropDetail(lastData.recommendations[0]);
  }
});
document.getElementById("crop-detail-back").addEventListener("click", closeCropDetail);
document.getElementById("crop-detail-overlay").addEventListener("click", (e) => {
  if (e.target.id === "crop-detail-overlay") closeCropDetail();
});

function renderIdeas(data) {
  const r = data.readings;
  const tips = [];

  if (r.N.percent < 30) {
    tips.push(["🟢", "Nitrogen is low", "Consider a nitrogen-rich fertilizer or compost to support leaf growth."]);
  } else if (r.N.percent > 75) {
    tips.push(["🟢", "Nitrogen is high", "Good for leafy crops, but excess nitrogen can delay fruiting in some plants."]);
  } else {
    tips.push(["🟢", "Nitrogen is balanced", "Levels are in a healthy range for most crops."]);
  }

  if (r.P.percent < 30) {
    tips.push(["🟣", "Phosphorus is low", "Low phosphorus can limit root development — a phosphate fertilizer may help."]);
  } else {
    tips.push(["🟣", "Phosphorus looks good", "Supports strong root and flower development."]);
  }

  if (r.K.percent < 30) {
    tips.push(["🟠", "Potassium is low", "May affect disease resistance and fruit quality — consider a potash supplement."]);
  } else {
    tips.push(["🟠", "Potassium looks good", "Supports disease resistance and overall plant strength."]);
  }

  if (r.ph.label === "Acidic") {
    tips.push(["⚗️", "Soil is acidic", "Adding agricultural lime can help raise pH for crops that prefer neutral soil."]);
  } else if (r.ph.label === "Alkaline") {
    tips.push(["⚗️", "Soil is alkaline", "Adding organic matter or sulfur can help lower pH over time."]);
  } else {
    tips.push(["⚗️", "pH is optimal", "Most crops thrive in this range — no adjustment needed."]);
  }

  if (r.humidity.label === "Low") {
    tips.push(["💧", "Moisture is low", "Increase irrigation frequency, especially for water-sensitive crops."]);
  } else if (r.humidity.label === "High") {
    tips.push(["💧", "Moisture is high", "Watch for fungal disease risk; ensure good drainage and airflow."]);
  }

  const top = data.recommendations[0];

  document.getElementById("ideas-box").innerHTML = tips.map(([icon, title, text]) => `
    <div class="idea-item">
      <div class="idea-icon">${icon}</div>
      <div>
        <div class="idea-title">${title}</div>
        <div class="idea-text">${text}</div>
      </div>
    </div>
  `).join("") + `
    <div class="idea-item idea-crop">
      <img class="idea-crop-img" src="${cropImage(top.crop)}" alt="${top.crop}">
      <div>
        <div class="idea-title">Best fit: ${top.crop}</div>
        <div class="idea-text">This soil profile matches ${top.crop} with ${Math.round(top.confidence * 100)}% confidence based on similar samples in the dataset.</div>
      </div>
    </div>
  `;

  currentIdeasSpeechText = tips.map(([, title, text]) => `${title}. ${text}`)
    .concat(`Best fit: ${top.crop}, matching with ${Math.round(top.confidence * 100)} percent confidence.`);
  document.getElementById("ideas-listen-btn").style.display = "flex";
}

let currentIdeasSpeechText = "";
document.getElementById("ideas-listen-btn").addEventListener("click", () => {
  speakInEnglish(currentIdeasSpeechText, document.getElementById("ideas-listen-btn"));
});

function renderFields(data) {
  const r = data.readings;
  const rows = [
    ["Nitrogen (N)", `${r.N.value} kg/ha`],
    ["Phosphorus (P)", `${r.P.value} kg/ha`],
    ["Potassium (K)", `${r.K.value} kg/ha`],
    ["Soil pH", `${r.ph.value} (${r.ph.label})`],
    ["Humidity", `${r.humidity.value}% (${r.humidity.label})`],
    ["Temperature", `${r.temperature.value} °C`],
    ["Rainfall", `${r.rainfall.value} mm`],
    ["Source", data.used_fuzzy ? "Estimated (fuzzy match)" : "Direct reading"],
  ];
  document.getElementById("field-info").innerHTML = rows.map(([label, value]) => `
    <div class="field-row"><span class="label">${label}</span><span class="value">${value}</span></div>
  `).join("");
}

async function analyze() {
  const btn = document.getElementById("analyze-btn");
  btn.disabled = true;
  btn.textContent = "Analyzing...";
  try {
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectInputs()),
    });
    if (!res.ok) throw new Error("Prediction failed");
    const data = await res.json();
    renderResult(data);
  } catch (err) {
    alert("Could not get a recommendation. Please check your inputs and that the server is running.");
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "&#129514; Analyze Soil Sample";
  }
}

async function loadRandomSample() {
  const res = await fetch("/api/sample");
  const data = await res.json();
  fillInputs(data);
  analyze();
}

document.getElementById("analyze-btn").addEventListener("click", analyze);
document.getElementById("random-btn").addEventListener("click", loadRandomSample);

// ── Tab navigation ──────────────────────────────────────────────────────
const TITLES = { dashboard: "Akuafo Ani", crops: "Crops", ideas: "Ideas", fields: "Summary", profile: "Profile" };

function showView(view) {
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.querySelector(`.view[data-view="${view}"]`).classList.add("active");
  document.getElementById("page-title").textContent = TITLES[view] || "";
  window.scrollTo({ top: 0, behavior: "instant" });
}

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => showView(item.dataset.view));
});

document.getElementById("profile-avatar-btn").addEventListener("click", () => showView("profile"));

// ── Boot: show the dashboard if already logged in, otherwise the auth screens ──
(async function boot() {
  initAuthSlideshow();
  try {
    const res = await fetch("/api/me");
    if (res.ok) {
      showApp(await res.json());
    } else {
      showAuthScreen();
    }
  } catch (err) {
    console.error(err);
    showAuthScreen();
  }
})();
