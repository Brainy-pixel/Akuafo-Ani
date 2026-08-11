const FIELDS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"];

let lastData = null;

function cropImage(crop) {
  return `images/crops/${crop.toLowerCase()}.jpg`;
}

// ── i18n: translates static UI chrome only (nav, headers, buttons, labels).
// Crop names, model-generated reasons, and live weather/soil readings stay
// in English regardless of language — translating generated text is out of
// scope here. Twi text is a best-effort machine/AI translation and has NOT
// been reviewed by a native speaker — verify before relying on it publicly. ──
const TRANSLATIONS = {
  en: {
    "auth.tagline": "Smarter crop choices, straight from your soil.",
    "auth.getStarted": "Get Started",
    "auth.logIn": "Log In",
    "auth.signUp": "Sign Up",
    "auth.welcomeBack": "Welcome Back",
    "auth.loginSubtitle": "Log in to your account",
    "auth.email": "Email",
    "auth.password": "Password",
    "auth.noAccount": "Don't have an account?",
    "auth.createAccount": "Create Account",
    "auth.signupSubtitle": "Sign up to get started",
    "auth.fullName": "Full Name",
    "auth.haveAccount": "Already have an account?",

    "nav.dashboard": "Dashboard",
    "nav.crops": "Crops",
    "nav.ideas": "Ideas",
    "nav.summary": "Summary",
    "nav.profile": "Profile",
    "app.title": "Akuafo Ani",

    "common.listen": "Listen",
    "common.back": "Back",

    "dashboard.topRecommendation": "Top Recommendation",
    "dashboard.welcomeHeading": "Welcome",
    "dashboard.welcomeTagline": "A Happy, Informed and Cost-effective Farming with Akuafo Ani",
    "dashboard.whyThisCrop": "Why this crop?",
    "dashboard.soilWeatherToday": "Soil Weather Today",
    "dashboard.rainfall": "Rainfall",
    "dashboard.humidity": "Humidity",
    "dashboard.condition": "Condition",
    "dashboard.soilPh": "Soil pH",
    "dashboard.moisture": "Moisture",
    "dashboard.nutrientBalance": "Nutrient Balance",
    "dashboard.nitrogen": "Nitrogen",
    "dashboard.nitrogenDesc": "Essential for leaf growth and lush green foliage.",
    "dashboard.phosphorus": "Phosphorus",
    "dashboard.phosphorusDesc": "Supports strong root and flower development.",
    "dashboard.potassium": "Potassium",
    "dashboard.potassiumDesc": "Boosts disease resistance and overall plant strength.",

    "crops.recommendedCrops": "Recommended Crops",
    "crops.fuzzyNote": "Some values were estimated from similar soil samples (fuzzy match).",
    "crops.soilSampleInput": "Soil Sample Input",
    "crops.nitrogenLabel": "Nitrogen N (kg/ha)",
    "crops.phosphorusLabel": "Phosphorus P (kg/ha)",
    "crops.potassiumLabel": "Potassium K (kg/ha)",
    "crops.temperatureLabel": "Temperature (°C)",
    "crops.humidityLabel": "Humidity (%)",
    "crops.phLabel": "Soil pH",
    "crops.rainfallLabel": "Rainfall (mm)",
    "crops.hint": "Leave any field blank if unknown — the model will estimate it from similar soil samples.",
    "crops.analyzeBtn": "Analyze Soil Sample",
    "crops.analyzing": "Analyzing...",
    "crops.clearAll": "Clear All",
    "crops.randomBtn": "Load a random real sample",

    "cropsHero.plant": "Plant Best Crop",
    "cropsHero.harvest": "Harvest Crop Yields",
    "cropsHero.market": "Food for All",

    "ideas.insightsTips": "Insights & Tips",
    "ideas.placeholder": "Analyze a soil sample on the Crops tab to get tailored tips here.",
    "ideas.listenToTips": "Listen to tips",

    "summary.sampleSummary": "Sample Summary",
    "summary.placeholder": "No sample analyzed yet. Your soil readings will appear here.",
    "summary.source": "Source",
    "summary.estimated": "Estimated (fuzzy match)",
    "summary.directReading": "Direct reading",

    "cropDetail.subtitle": "Why this crop matches your soil",

    "profile.removePhoto": "Remove photo",
    "profile.personalDetails": "Personal Details",
    "profile.saved": "Saved.",
    "profile.fullName": "Full Name",
    "profile.email": "Email",
    "profile.phone": "Phone Number",
    "profile.avatarStyle": "Avatar Style",
    "profile.male": "Male",
    "profile.female": "Female",
    "profile.saveChanges": "Save Changes",
    "profile.loginSecurity": "Login & Security",
    "profile.passwordUpdated": "Password updated.",
    "profile.currentPassword": "Current Password",
    "profile.newPassword": "New Password",
    "profile.confirmPassword": "Confirm New Password",
    "profile.updatePassword": "Update Password",
    "profile.twoFactor": "Two-Factor Authentication",
    "profile.activeSessions": "Active Sessions",
    "profile.comingSoon": "Coming soon",
    "profile.preferences": "Preferences",
    "profile.darkMode": "Dark Mode",
    "profile.darkModeSub": "Switch between light and dark themes",
    "profile.notifications": "Notifications",
    "profile.notificationsSub": "Get updates about your soil samples",
    "profile.language": "Language",
    "profile.languageSub": "Choose your preferred language",
    "profile.logOut": "Log Out",
  },
  tw: {
    "auth.tagline": "Nnɔbae a wɔpaw yiye, fi wo asase mu tee.",
    "auth.getStarted": "Fi Ase",
    "auth.logIn": "Kɔ Akawnt Mu",
    "auth.signUp": "Yɛ Akawnt Foforo",
    "auth.welcomeBack": "Akwaaba Bio",
    "auth.loginSubtitle": "Kɔ wo akawnt mu",
    "auth.email": "Email",
    "auth.password": "Password",
    "auth.noAccount": "Wonni akawnt?",
    "auth.createAccount": "Yɛ Akawnt",
    "auth.signupSubtitle": "Yɛ akawnt na fi ase",
    "auth.fullName": "Din Mu Nyinaa",
    "auth.haveAccount": "Wowɔ akawnt dedaw?",

    "nav.dashboard": "Dashboard",
    "nav.crops": "Nnɔbae",
    "nav.ideas": "Nsusuwii",
    "nav.summary": "Nkyerɛmu",
    "nav.profile": "Wo Ho Nsɛm",
    "app.title": "Akuafo Ani",

    "common.listen": "Tie",
    "common.back": "San Kɔ",

    "dashboard.topRecommendation": "Deɛ Ɛfata Paa",
    "dashboard.welcomeHeading": "Akwaaba",
    "dashboard.welcomeTagline": "Kuayɛ a Ɛyɛ Anigye, Ɛma Nimdeɛ, Na Ɛnhyɛ Sika Bebree Wɔ Akuafo Ani",
    "dashboard.whyThisCrop": "Adɛn nti na ɛyɛ saa aduane yi?",
    "dashboard.soilWeatherToday": "Asase Wim Tebea Ɛnnɛ",
    "dashboard.rainfall": "Osu",
    "dashboard.humidity": "Fɔntɔm",
    "dashboard.condition": "Tebea",
    "dashboard.soilPh": "Asase pH",
    "dashboard.moisture": "Fɔntɔm",
    "dashboard.nutrientBalance": "Aduannuru Nkabom",
    "dashboard.nitrogen": "Nitrogen",
    "dashboard.nitrogenDesc": "Ɛho hia ma nhaban nyin na ɛma ɛyɛ ahonoahono.",
    "dashboard.phosphorus": "Phosphorus",
    "dashboard.phosphorusDesc": "Ɛboa ma ntini ne nhwiren nyin yiye.",
    "dashboard.potassium": "Potassium",
    "dashboard.potassiumDesc": "Ɛma afifide tumi gyina nyarewa ano na ɛma emu yɛ den.",

    "crops.recommendedCrops": "Nnɔbae a Yɛkamfo",
    "crops.fuzzyNote": "Wɔkyerɛɛ nsɛm bi fi asase nhwɛso a ɛte saa ara mu (fuzzy match).",
    "crops.soilSampleInput": "Asase Nhwɛso Nsɛm",
    "crops.nitrogenLabel": "Nitrogen N (kg/ha)",
    "crops.phosphorusLabel": "Phosphorus P (kg/ha)",
    "crops.potassiumLabel": "Potassium K (kg/ha)",
    "crops.temperatureLabel": "Ɔhyew (°C)",
    "crops.humidityLabel": "Fɔntɔm (%)",
    "crops.phLabel": "Asase pH",
    "crops.rainfallLabel": "Osu (mm)",
    "crops.hint": "Gyae kwan biara mu kwaadu sɛ wonnim — model no bɛkyerɛ fi asase nhwɛso a ɛte saa ara mu.",
    "crops.analyzeBtn": "Hwehwɛ Asase Nhwɛso Mu",
    "crops.analyzing": "Ɛrehwehwɛ Mu...",
    "crops.clearAll": "Yi Nyinaa",
    "crops.randomBtn": "Fa nhwɛso ankasa bi kwa",

    "cropsHero.plant": "Dua Aduane Pa",
    "cropsHero.harvest": "Twa Aduane",
    "cropsHero.market": "Aduane Ma Obiara",

    "ideas.insightsTips": "Nteɛso ne Afotu",
    "ideas.placeholder": "Hwehwɛ asase nhwɛso mu wɔ Nnɔbae tab so na nya afotu wɔ ha.",
    "ideas.listenToTips": "Tie afotu",

    "summary.sampleSummary": "Nhwɛso Nkyerɛmu",
    "summary.placeholder": "Wonnhwehwɛɛ nhwɛso biara mu. Wo asase nsɛm bɛba ha.",
    "summary.source": "Nea Efi",
    "summary.estimated": "Wɔkyerɛɛ (fuzzy match)",
    "summary.directReading": "Nhwɛso Tee",

    "cropDetail.subtitle": "Adɛn nti na saa aduane yi fata wo asase",

    "profile.removePhoto": "Yi Mfoni",
    "profile.personalDetails": "Wo Ho Nsɛm",
    "profile.saved": "Makora.",
    "profile.fullName": "Din Mu Nyinaa",
    "profile.email": "Email",
    "profile.phone": "Foon Nɔma",
    "profile.avatarStyle": "Mfoni Su",
    "profile.male": "Ɔbarima",
    "profile.female": "Ɔbaa",
    "profile.saveChanges": "Kora Nsakraeɛ",
    "profile.loginSecurity": "Akawnt Mu Kɔ ne Bammɔ",
    "profile.passwordUpdated": "Password asesa.",
    "profile.currentPassword": "Password a Wode Di Dwuma Seesei",
    "profile.newPassword": "Password Foforo",
    "profile.confirmPassword": "Sisi Password Foforo No Mu",
    "profile.updatePassword": "Sesa Password",
    "profile.twoFactor": "Akwan Mmienu Bammɔ",
    "profile.activeSessions": "Mmerɛ a Woda so wɔ Mu",
    "profile.comingSoon": "Ɛreba",
    "profile.preferences": "Nea Wopɛ",
    "profile.darkMode": "Sum Mode",
    "profile.darkModeSub": "Sesa ntam hann ne sum",
    "profile.notifications": "Amanneɛbɔ",
    "profile.notificationsSub": "Nya nsɛm foforo fa wo asase nhwɛso ho",
    "profile.language": "Kasa",
    "profile.languageSub": "Paw kasa a wopɛ",
    "profile.logOut": "Fi Adi",
  },
};

let currentLanguage = "en";

function t(key) {
  return (TRANSLATIONS[currentLanguage] && TRANSLATIONS[currentLanguage][key])
    || TRANSLATIONS.en[key]
    || key;
}

function applyLanguage(lang) {
  currentLanguage = TRANSLATIONS[lang] ? lang : "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  const activeView = document.querySelector(".view.active");
  if (activeView) {
    document.getElementById("page-title").textContent = pageTitle(activeView.dataset.view);
  }
  updateWelcomeHeading();
  refreshCropsHeroCaption();
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

// ── Crops tab pre-analysis carousel: cycles the three themed photos until
// the user runs an analysis (Analyze Soil Sample / Load a random sample),
// at which point renderResult() clears #recommendations and stops this. ──
const CROPS_HERO_SLIDES = [
  { image: "plant", captionKey: "cropsHero.plant" },
  { image: "harvest", captionKey: "cropsHero.harvest" },
  { image: "market", captionKey: "cropsHero.market" },
];
let cropsHeroInterval = null;
let cropsHeroIndex = 0;

function initCropsHero() {
  const container = document.getElementById("crops-hero-slideshow");
  const captionEl = document.getElementById("crops-hero-caption");
  if (!container || !captionEl || container.children.length) return;

  const layerA = document.createElement("div");
  const layerB = document.createElement("div");
  layerA.className = "crops-hero-slide active";
  layerB.className = "crops-hero-slide";
  layerA.style.backgroundImage = `url(images/hero/${CROPS_HERO_SLIDES[0].image}.jpg)`;
  container.append(layerA, layerB);
  cropsHeroIndex = 0;
  captionEl.textContent = t(CROPS_HERO_SLIDES[0].captionKey);

  let onA = true;
  cropsHeroInterval = setInterval(() => {
    cropsHeroIndex = (cropsHeroIndex + 1) % CROPS_HERO_SLIDES.length;
    const incoming = onA ? layerB : layerA;
    const outgoing = onA ? layerA : layerB;
    incoming.style.backgroundImage = `url(images/hero/${CROPS_HERO_SLIDES[cropsHeroIndex].image}.jpg)`;
    incoming.classList.add("active");
    outgoing.classList.remove("active");
    captionEl.textContent = t(CROPS_HERO_SLIDES[cropsHeroIndex].captionKey);
    onA = !onA;
  }, 3500);
}

function stopCropsHero() {
  if (cropsHeroInterval) { clearInterval(cropsHeroInterval); cropsHeroInterval = null; }
}

function refreshCropsHeroCaption() {
  const captionEl = document.getElementById("crops-hero-caption");
  if (captionEl && cropsHeroInterval) captionEl.textContent = t(CROPS_HERO_SLIDES[cropsHeroIndex].captionKey);
}

// ── Cover screen helpers ─────────────────────────────────────────────────
// showAuthScreen: show the cover ("Get Started") splash; hides the app.
// showAppShell: show the app without a user — used by "Get Started" so the
//   profile tab can display the login/signup forms before authentication.
function showAuthScreen() {
  document.getElementById("auth-screen").classList.remove("hidden");
  document.getElementById("app-root").classList.add("hidden");
}

// Neutral person SVG shown in topbar when no user is signed in
const UNSIGNED_AVATAR_SVG = `<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
  <circle cx="60" cy="60" r="60" fill="#e7ecf3"/>
  <circle cx="60" cy="46" r="22" fill="#b0bec5"/>
  <path d="M60 80c26 0 46 18 46 48H14c0-30 20-48 46-48z" fill="#b0bec5"/>
</svg>`;

function showAppShell() {
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("app-root").classList.remove("hidden");
  // Show unsigned avatar in topbar while no user is logged in
  document.getElementById("profile-avatar-btn").innerHTML = UNSIGNED_AVATAR_SVG;
  renderProfileSectionState();
  updateWelcomeHeading(); // show "Welcome Okuafo" on dashboard before sign-in
  showView("profile");
}

// Profile view: shows auth forms when not logged in, profile details when in.
// Notifications row is hidden when not logged in (no account to save it to).
function renderProfileSectionState() {
  const authSec  = document.getElementById("profile-auth-section");
  const userSec  = document.getElementById("profile-user-section");
  const notifRow = document.querySelector(".pref-row-notifications");
  if (currentUser) {
    authSec.classList.add("hidden");
    userSec.classList.remove("hidden");
    if (notifRow) notifRow.classList.remove("hidden");
  } else {
    authSec.classList.remove("hidden");
    userSec.classList.add("hidden");
    if (notifRow) notifRow.classList.add("hidden");
    // Apply saved local preferences (dark mode, language) when not logged in
    const lp = loadLocalPrefs();
    if (lp.theme)    { applyTheme(lp.theme);       document.getElementById("theme-toggle").checked = lp.theme === "dark"; }
    if (lp.language) { applyLanguage(lp.language);  document.getElementById("language-select").value = lp.language; }
  }
}

// Profile auth tab switching (Log In ↔ Sign Up)
document.querySelectorAll(".profile-auth-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".profile-auth-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const which = tab.dataset.profileTab;
    document.getElementById("profile-login-card").classList.toggle("hidden", which !== "login");
    document.getElementById("profile-signup-card").classList.toggle("hidden", which !== "signup");
  });
});

// "Get Started" on the cover screen → open the app at the Profile tab
document.getElementById("get-started-btn").addEventListener("click", showAppShell);

let currentUser = null;

const RECOMMENDATIONS_PLACEHOLDER_HTML = `
  <div class="crops-hero" id="crops-hero">
    <div class="crops-hero-slideshow" id="crops-hero-slideshow"></div>
    <div class="welcome-hero-text">
      <div class="crops-hero-caption" id="crops-hero-caption"></div>
    </div>
  </div>
`;

// Restores every "no analysis yet" placeholder. Needed because renderResult()
// permanently replaces #recommendations' markup — without this, logging out
// and back in (no page reload) would leave the crops carousel gone for good.
function resetDashboardState() {
  stopCropsHero();
  lastData = null;

  document.getElementById("recommendations").innerHTML = RECOMMENDATIONS_PLACEHOLDER_HTML;
  document.getElementById("top-pick-img").style.display = "none";
  document.getElementById("top-pick-overlay").style.display = "none";
  document.getElementById("top-pick-placeholder").style.display = "block";
  document.getElementById("why-card").style.display = "none";
  document.getElementById("fuzzy-note").style.display = "none";
  document.getElementById("ideas-listen-btn").style.display = "none";
  document.getElementById("ideas-box").innerHTML =
    `<div class="placeholder-text" data-i18n="ideas.placeholder">${t("ideas.placeholder")}</div>`;
  document.getElementById("field-info").innerHTML =
    `<div class="placeholder-text" data-i18n="summary.placeholder">${t("summary.placeholder")}</div>`;
  clearAllInputs();
  updateWelcomeHeading();
}

function showApp(user) {
  currentUser = user;
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("app-root").classList.remove("hidden");
  renderProfileSectionState();   // show user section, hide auth forms
  applyTheme(user.theme);
  applyLanguage(user.language);
  updateProfileView(user);
  resetDashboardState();
  showView("dashboard");
  initCropsHero();
  loadWeather(); // kick off GPS → Open-Meteo in the background
}

// Switches the Dashboard heading between "Welcome Okuafo / Welcome, {Name}"
// (pre-analysis) and "Top Recommendation" (post-analysis).
function updateWelcomeHeading() {
  const el = document.getElementById("dashboard-heading");
  if (!el) return;
  if (lastData) {
    el.textContent = t("dashboard.topRecommendation");
  } else if (currentUser) {
    const firstName = currentUser.full_name.trim().split(/\s+/)[0];
    el.textContent = `${t("dashboard.welcomeHeading")}, ${firstName}`;
  } else {
    el.textContent = "Welcome Okuafo";
  }
}

// ── Avatars: uploaded photo, else an original male/female default icon,
// else initials. Not a copy of any reference image — simple original shapes. ─
const DEFAULT_AVATAR_SVG = {
  male: `<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
    <circle cx="60" cy="60" r="60" fill="#e7ecf3"/>
    <circle cx="60" cy="48" r="20" fill="#f2b48a"/>
    <path d="M60 26c-13 0-22 9-22 20 0 3 1 6 2 8 2-10 10-16 20-16s18 6 20 16c1-2 2-5 2-8 0-11-9-20-22-20z" fill="#3a2a1e"/>
    <path d="M60 78c22 0 40 16 40 42H20c0-26 18-42 40-42z" fill="#1f3a63"/>
  </svg>`,
  female: `<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
    <circle cx="60" cy="60" r="60" fill="#e7ecf3"/>
    <path d="M60 20c16 0 28 12 28 30 0 6-1 12-4 16l-3-3c1-11-3-20-9-20-2 7-7 12-12 12s-10-5-12-12c-6 0-10 9-9 20l-3 3c-3-4-4-10-4-16 0-18 12-30 28-30z" fill="#3a2a1e"/>
    <circle cx="60" cy="50" r="18" fill="#f2b48a"/>
    <path d="M60 78c22 0 40 16 40 42H20c0-26 18-42 40-42z" fill="#6a3f9e"/>
  </svg>`,
};

function avatarMarkup(user) {
  if (user.avatar_data_url) {
    return `<img src="${user.avatar_data_url}" alt="">`;
  }
  if (user.gender === "male" || user.gender === "female") {
    return DEFAULT_AVATAR_SVG[user.gender];
  }
  const initials = user.full_name.trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return initials || "?";
}

function renderAvatars(user) {
  document.getElementById("profile-avatar-display").innerHTML = avatarMarkup(user);
  document.getElementById("profile-avatar-btn").innerHTML = avatarMarkup(user);
}

function updateProfileView(user) {
  document.getElementById("profile-name-display").textContent = user.full_name;
  document.getElementById("profile-email-display").textContent = user.email;
  renderAvatars(user);

  document.getElementById("details-name").value = user.full_name;
  document.getElementById("details-email").value = user.email;
  document.getElementById("details-phone").value = user.phone || "";
  document.getElementById("details-gender").value = user.gender || "male";

  document.getElementById("theme-toggle").checked = user.theme === "dark";
  document.getElementById("notifications-toggle").checked = !!user.notifications_enabled;
  document.getElementById("language-select").value = user.language || "en";
}

function setAuthError(id, message) {
  const el = document.getElementById(id);
  if (!message) { el.classList.add("hidden"); el.textContent = ""; return; }
  el.textContent = message;
  el.classList.remove("hidden");
}

// Errors carry dynamic server text; successes reuse their static, already
// translated markup, so only their visibility toggles.
function showFormError(id, message) {
  const el = document.getElementById(id);
  if (!message) { el.classList.add("hidden"); el.textContent = ""; return; }
  el.textContent = message;
  el.classList.remove("hidden");
}

function flashFormSuccess(id) {
  const el = document.getElementById(id);
  el.classList.remove("hidden");
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => el.classList.add("hidden"), 2500);
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
  stopActiveSpeech();
  resetDashboardState();
  showAuthScreen();
});

// ── Personal Details ─────────────────────────────────────────────────────
document.getElementById("details-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  showFormError("details-error", "");
  const submitBtn = document.getElementById("details-save-btn");
  submitBtn.disabled = true;
  try {
    const res = await fetch("/api/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: document.getElementById("details-name").value,
        email: document.getElementById("details-email").value,
        phone: document.getElementById("details-phone").value,
        gender: document.getElementById("details-gender").value,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not save changes.");
    currentUser = data;
    updateProfileView(data);
    flashFormSuccess("details-success");
  } catch (err) {
    showFormError("details-error", err.message);
  } finally {
    submitBtn.disabled = false;
  }
});

// ── Avatar upload / remove ───────────────────────────────────────────────
const MAX_AVATAR_BYTES = 2 * 1024 * 1024;

document.getElementById("avatar-edit-btn").addEventListener("click", () => {
  document.getElementById("avatar-file-input").click();
});

document.getElementById("avatar-file-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    showFormError("details-error", "Please choose an image file.");
    return;
  }
  if (file.size > MAX_AVATAR_BYTES) {
    showFormError("details-error", "Image is too large (max 2MB).");
    return;
  }
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
  await saveAvatar(dataUrl);
});

document.getElementById("avatar-remove-btn").addEventListener("click", () => saveAvatar(null));

async function saveAvatar(dataUrl) {
  showFormError("details-error", "");
  try {
    const res = await fetch("/api/profile/avatar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ avatar_data_url: dataUrl }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not update photo.");
    currentUser = data;
    renderAvatars(data);
    document.getElementById("avatar-remove-btn").classList.toggle("hidden", !data.avatar_data_url);
  } catch (err) {
    showFormError("details-error", err.message);
  }
}

// ── Login & Security: change password ────────────────────────────────────
document.getElementById("password-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  showFormError("password-error", "");
  const newPassword = document.getElementById("new-password").value;
  const confirmPassword = document.getElementById("confirm-password").value;
  if (newPassword !== confirmPassword) {
    showFormError("password-error", "New password and confirmation don't match.");
    return;
  }
  const submitBtn = document.getElementById("password-save-btn");
  submitBtn.disabled = true;
  try {
    const res = await fetch("/api/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: document.getElementById("current-password").value,
        new_password: newPassword,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not update password.");
    document.getElementById("password-form").reset();
    flashFormSuccess("password-success");
  } catch (err) {
    showFormError("password-error", err.message);
  } finally {
    submitBtn.disabled = false;
  }
});

// ── Preferences: theme, notifications, language ──────────────────────────
// When logged in, preferences sync to the server.
// When not logged in, dark-mode and language are saved to localStorage so
// they persist across the session without requiring an account.
const LOCAL_PREFS_KEY = "akuafo_prefs";
function loadLocalPrefs() {
  try { return JSON.parse(localStorage.getItem(LOCAL_PREFS_KEY) || "{}"); }
  catch { return {}; }
}
function saveLocalPref(key, value) {
  const p = loadLocalPrefs(); p[key] = value;
  localStorage.setItem(LOCAL_PREFS_KEY, JSON.stringify(p));
}

async function savePreference(patch) {
  const res = await fetch("/api/preferences", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  const data = await res.json();
  if (res.ok) currentUser = data;
  return data;
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme === "dark" ? "dark" : "light");
}

document.getElementById("theme-toggle").addEventListener("change", async (e) => {
  const theme = e.target.checked ? "dark" : "light";
  applyTheme(theme);
  if (currentUser) { await savePreference({ theme }); }
  else             { saveLocalPref("theme", theme); }
});

document.getElementById("notifications-toggle").addEventListener("change", async (e) => {
  if (currentUser) await savePreference({ notifications_enabled: e.target.checked });
});

document.getElementById("language-select").addEventListener("change", async (e) => {
  applyLanguage(e.target.value);
  if (currentUser) { await savePreference({ language: e.target.value }); }
  else             { saveLocalPref("language", e.target.value); }
});

// ── Voice feature: reads English text aloud via the browser's built-in
// speech synthesis. Features: pause/resume, prev/next-line seeking via a
// floating player bar, stop. Rate 0.85 for clarity. ──────────────────────
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
// Player state
let speechLines = [];      // pre-processed lines array
let speechCurrentLine = 0; // index of line currently being (or about to be) spoken
let speechIsPaused = false;

// ── Inline seek strip helpers ────────────────────────────────────────────
let activeSeekWrap = null;

function showSeekFor(btn) {
  hideActiveSeek();
  // The seek strip is the immediate next sibling of the listen button
  const wrap = btn ? btn.nextElementSibling : null;
  if (wrap && wrap.classList.contains("listen-seek")) {
    const slider = wrap.querySelector(".sp-seek");
    if (slider) { slider.max = Math.max(0, speechLines.length - 1); slider.value = 0; }
    const pauseBtn = wrap.querySelector(".sp-pause-btn");
    if (pauseBtn) pauseBtn.textContent = "⏸";
    wrap.classList.remove("hidden");
    activeSeekWrap = wrap;
  }
}

function hideActiveSeek() {
  if (activeSeekWrap) { activeSeekWrap.classList.add("hidden"); activeSeekWrap = null; }
}

function updateSeekSlider() {
  if (!activeSeekWrap) return;
  const slider = activeSeekWrap.querySelector(".sp-seek");
  if (slider) slider.value = speechCurrentLine;
}

// ── Core speech functions ────────────────────────────────────────────────
function stopActiveSpeech() {
  speechToken++;
  window.speechSynthesis.cancel();
  if (speechTimeoutId) { clearTimeout(speechTimeoutId); speechTimeoutId = null; }
  if (activeSpeechReset) activeSpeechReset();
  activeSpeechBtn = null;
  activeSpeechReset = null;
  speechIsPaused = false;
  hideActiveSeek();
}

function speakCurrentLine(myToken) {
  if (myToken !== speechToken || speechCurrentLine >= speechLines.length) {
    if (myToken === speechToken) stopActiveSpeech();
    return;
  }
  const utterance = new SpeechSynthesisUtterance(speechLines[speechCurrentLine]);
  utterance.lang = "en-US";
  utterance.rate = 0.85;

  utterance.addEventListener("start", () => {
    if (myToken !== speechToken) return;
    if (activeSpeechBtn) {
      const label = activeSpeechBtn.querySelector(".listen-label");
      const icon  = activeSpeechBtn.querySelector(".listen-icon");
      if (label) label.textContent = "Stop";
      if (icon)  icon.textContent  = "⏹";
    }
  });
  utterance.addEventListener("end", () => {
    if (myToken !== speechToken) return;
    speechCurrentLine++;
    updateSeekSlider();
    if (speechCurrentLine < speechLines.length) {
      speechTimeoutId = setTimeout(() => speakCurrentLine(myToken), LINE_PAUSE_MS);
    } else {
      stopActiveSpeech();
    }
  });
  utterance.addEventListener("error", () => {
    if (myToken === speechToken) stopActiveSpeech();
  });
  window.speechSynthesis.speak(utterance);
}

function speakInEnglish(lines, btn) {
  if (!window.speechSynthesis) return;

  const wasThisButton = activeSpeechBtn === btn;
  stopActiveSpeech();
  if (wasThisButton) return; // clicking a playing button again stops it

  if (!lines) return;
  const linesArr = Array.isArray(lines) ? lines : [lines];
  if (!linesArr.length) return;

  speechLines = linesArr.map(speechFriendly);
  speechCurrentLine = 0;
  speechIsPaused = false;

  const myToken = ++speechToken;
  const label = btn.querySelector(".listen-label");
  const icon  = btn.querySelector(".listen-icon");
  const origLabel = label ? label.textContent : "";
  const origIcon  = icon  ? icon.textContent  : "";

  activeSpeechBtn = btn;
  activeSpeechReset = () => {
    if (label) label.textContent = origLabel;
    if (icon)  icon.textContent  = origIcon;
  };

  speakCurrentLine(myToken);
  showSeekFor(btn);
}

// ── Inline seek strip controls (delegated — one handler covers all buttons) ─
document.addEventListener("click", (e) => {
  // Pause / Resume
  const pauseBtn = e.target.closest(".sp-pause-btn");
  if (pauseBtn && window.speechSynthesis) {
    if (speechIsPaused) {
      window.speechSynthesis.resume();
      speechIsPaused = false;
      pauseBtn.textContent = "⏸";
    } else {
      window.speechSynthesis.pause();
      speechIsPaused = true;
      pauseBtn.textContent = "▶";
    }
    return;
  }
  // Stop
  if (e.target.closest(".sp-stop-btn")) {
    stopActiveSpeech();
  }
});

// Seek — dragging the range slider jumps to that line
document.addEventListener("input", (e) => {
  if (!e.target.classList.contains("sp-seek")) return;
  const tok = speechToken;
  window.speechSynthesis.cancel();
  if (speechTimeoutId) { clearTimeout(speechTimeoutId); speechTimeoutId = null; }
  speechIsPaused = false;
  speechCurrentLine = parseInt(e.target.value, 10);
  if (activeSeekWrap) {
    const pb = activeSeekWrap.querySelector(".sp-pause-btn");
    if (pb) pb.textContent = "⏸";
  }
  speakCurrentLine(tok);
});

// ── GPS + Open-Meteo rainfall integration ─────────────────────────────────
// On login: requests GPS coordinates, calls /api/rainfall (Open-Meteo free
// historical archive — no API key needed) for the past-12-month total, then
// reveals a "📍 GPS" button next to the Rainfall input on the Crops tab so
// the farmer can pre-fill that field with their location's annual average.
// ──────────────────────────────────────────────────────────────────────────

let annualRainfallMm = null; // set once GPS + Open-Meteo data arrives

function applyAnnualRainfall() {
  if (annualRainfallMm === null) return;
  document.getElementById("in-rainfall").value = annualRainfallMm;
  showView("crops"); // jump to Crops tab so the user sees the filled field
}

async function loadWeather() {
  if (!navigator.geolocation) return;

  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const { latitude: lat, longitude: lon } = pos.coords;

      // Annual rainfall from Open-Meteo historical archive (free, no key)
      try {
        const rRes = await fetch(`/api/rainfall?lat=${lat}&lon=${lon}`);
        if (rRes.ok) {
          const rData = await rRes.json();
          if (!rData.error && rData.annual_mm != null) {
            annualRainfallMm = rData.annual_mm;
            const gpsBtn = document.getElementById("gps-fill-rainfall-btn");
            if (gpsBtn) {
              gpsBtn.style.display = "inline-flex";
              gpsBtn.title = `Your location's annual rainfall: ${annualRainfallMm} mm — tap to pre-fill`;
            }
          }
        }
      } catch (e) { console.warn("Rainfall fetch failed:", e); }
    },
    (err) => { console.warn("Geolocation not available:", err.message); },
    { timeout: 10000, maximumAge: 300000 }
  );
}

// "📍 GPS" button next to the Rainfall input (crops tab)
document.getElementById("gps-fill-rainfall-btn").addEventListener("click", applyAnnualRainfall);

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

function clearAllInputs() {
  for (const f of FIELDS) {
    document.getElementById("in-" + f).value = "";
  }
}

document.getElementById("clear-all-btn").addEventListener("click", () => {
  resetDashboardState();
  initCropsHero();
});

function setGauge(gaugeId, pct, colorVar) {
  const gauge = document.getElementById(gaugeId);
  const color = getComputedStyle(document.documentElement).getPropertyValue(colorVar).trim();
  const deg = Math.max(0, Math.min(100, pct)) * 3.6;
  gauge.style.background = `conic-gradient(${color} ${deg}deg, #e7e9e4 ${deg}deg)`;
}

function renderResult(data) {
  lastData = data;
  stopCropsHero();

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

  // Weather card — update from soil analysis readings
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
            <span>${t("dashboard.whyThisCrop")}</span>
            <span class="reasons-chevron">&#9662;</span>
          </button>
          <ul class="crop-reasons" style="display:none;">${reasons.map((r) => `<li>${r}</li>`).join("")}</ul>
        ` : ""}
        <button class="listen-btn" type="button">
          <span class="listen-icon">&#128266;</span>
          <span class="listen-label">${t("common.listen")}</span>
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

  updateWelcomeHeading();
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
    [`${t("dashboard.nitrogen")} (N)`, `${r.N.value} kg/ha`],
    [`${t("dashboard.phosphorus")} (P)`, `${r.P.value} kg/ha`],
    [`${t("dashboard.potassium")} (K)`, `${r.K.value} kg/ha`],
    [t("dashboard.soilPh"), `${r.ph.value} (${r.ph.label})`],
    [t("dashboard.humidity"), `${r.humidity.value}% (${r.humidity.label})`],
    [t("crops.temperatureLabel").replace(" (°C)", ""), `${r.temperature.value} °C`],
    [t("dashboard.rainfall"), `${r.rainfall.value} mm`],
    [t("summary.source"), data.used_fuzzy ? t("summary.estimated") : t("summary.directReading")],
  ];
  document.getElementById("field-info").innerHTML = rows.map(([label, value]) => `
    <div class="field-row"><span class="label">${label}</span><span class="value">${value}</span></div>
  `).join("");
}

async function analyze() {
  const btn = document.getElementById("analyze-btn");
  btn.disabled = true;
  btn.textContent = t("crops.analyzing");
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
    btn.innerHTML = `&#129514; ${t("crops.analyzeBtn")}`;
  }
}

document.getElementById("analyze-btn").addEventListener("click", analyze);

// ── Tab navigation ──────────────────────────────────────────────────────
const PAGE_TITLE_KEYS = { dashboard: "", crops: "nav.crops", ideas: "nav.ideas", fields: "nav.summary", profile: "nav.profile" };
function pageTitle(view) {
  const key = PAGE_TITLE_KEYS[view];
  return key ? t(key) : ""; // dashboard maps to "" → title hidden
}

// Track the last non-profile view so the back button can return there.
let previousView = "dashboard";

function showView(view) {
  // Record where we came from before navigating to profile
  const activeView = document.querySelector(".view.active");
  if (view === "profile" && activeView && activeView.dataset.view !== "profile") {
    previousView = activeView.dataset.view;
  }

  document.querySelectorAll(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.querySelector(`.view[data-view="${view}"]`).classList.add("active");
  const title = pageTitle(view);
  const pageTitleEl = document.getElementById("page-title");
  pageTitleEl.textContent = title;
  // Dashboard has its own heading — hide the topbar title there to avoid duplication
  pageTitleEl.style.visibility = title ? "" : "hidden";
  window.scrollTo({ top: 0, behavior: "instant" });
}

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => showView(item.dataset.view));
});

document.getElementById("profile-avatar-btn").addEventListener("click", () => showView("profile"));

// Back button on the profile tab → return to previous view
document.getElementById("profile-back-btn").addEventListener("click", () => {
  showView(previousView || "dashboard");
});

// ── Boot: restore session if one exists, otherwise show the cover screen ──
(async function boot() {
  initAuthSlideshow();
  try {
    const res = await fetch("/api/me");
    if (res.ok) {
      showApp(await res.json()); // already logged in → straight to dashboard
    } else {
      showAuthScreen();          // no session → cover screen ("Get Started")
    }
  } catch (err) {
    console.error(err);
    showAuthScreen();
  }
})();
