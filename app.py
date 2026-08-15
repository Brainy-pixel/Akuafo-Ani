"""
Akuafo Ani — local web server.

Loads the trained crop-recommendation model and serves:
  - the dashboard web page (frontend/)
  - a JSON prediction API at POST /api/predict
  - account signup/login/logout at /api/signup, /api/login, /api/logout,
    /api/me — backed by SQLite locally, or Postgres in production when a
    DATABASE_URL env var is set (see _get_db below).

Run with:
    python app.py
Then open http://127.0.0.1:5000 in your browser.
"""
import io
import os
import json
import wave
import base64
import secrets
import urllib.request
import urllib.parse
from datetime import datetime, date, timedelta, timezone

import numpy as np
import pandas as pd
import joblib
from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
OUTPUT_DIR = "outputs"
DATA_PATH = "Crop_recommendation_filtered.csv"
CONF_THRESHOLD = 0.30  # below this, blend in nearest-neighbour "fuzzy" matches
DB_PATH = "users.db"
SECRET_KEY_PATH = os.path.join(OUTPUT_DIR, ".flask_secret")

FEATURE_META = {
    "N": {"label": "Nitrogen", "unit": "kg/ha"},
    "P": {"label": "Phosphorus", "unit": "kg/ha"},
    "K": {"label": "Potassium", "unit": "kg/ha"},
    "temperature": {"label": "Temperature", "unit": "°C"},
    "humidity": {"label": "Humidity", "unit": "%"},
    "ph": {"label": "Soil pH", "unit": ""},
    "rainfall": {"label": "Rainfall", "unit": "mm"},
}

app = Flask(__name__, static_folder="frontend", static_url_path="")

# OpenWeatherMap API key — set OPENWEATHER_API_KEY in your environment / Render settings.
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")


def _load_or_create_secret_key():
    """Persists a random session-signing key across restarts (set the
    SECRET_KEY env var instead in production)."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    if os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    os.makedirs(os.path.dirname(SECRET_KEY_PATH), exist_ok=True)
    with open(SECRET_KEY_PATH, "w") as f:
        f.write(key)
    return key


app.secret_key = _load_or_create_secret_key()
app.config.update(SESSION_COOKIE_SAMESITE="Lax")

# ── Stable-Twi-TTS local model ─────────────────────────────────────────────
# Downloaded once into models/ at build time (render.yaml) or on first run.
# When loaded, Twi voice requests are served locally (no Abena quota used).
_TWI_TTS_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
_twi_tts = None
try:
    from stable_twi_tts import StableTwiTTS
    _twi_tts = StableTwiTTS.from_pretrained(cache_dir=_TWI_TTS_MODEL_DIR, quiet=True)
    print("[twi-tts] model loaded OK")
except Exception as _e:
    print(f"[twi-tts] unavailable, Twi audio will fall back to browser TTS: {_e}")


def _synthesis_to_wav_b64(synth) -> tuple[str, float]:
    """Convert a Synthesis object to (base64-WAV-string, duration_seconds)."""
    import numpy as np
    buf = io.BytesIO()
    pcm = np.clip(synth.audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(synth.sample_rate)
        w.writeframes(pcm.tobytes())
    return base64.b64encode(buf.getvalue()).decode("ascii"), round(synth.duration, 2)


# Emails are always lowercased before storage/lookup (see signup/login), so
# no case-insensitive collation is needed at the schema level in either DB.
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Production: Postgres (e.g. a free Neon/Supabase database). Render's
    # own disk is not guaranteed to survive a redeploy, so accounts must
    # live in an external, persistent database.
    import psycopg2
    import psycopg2.extras

    class _PgConn:
        """Wraps a psycopg2 connection so call sites can use conn.execute(...)
        the same way they would with sqlite3.Connection."""

        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, params=()):
            cur = self._conn.cursor()
            cur.execute(sql.replace("?", "%s"), params)
            return cur

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            (self._conn.rollback() if exc_type else self._conn.commit())
            self._conn.close()

    def _get_db():
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return _PgConn(conn)

    _USERS_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """

    def _existing_user_columns(conn):
        return {row["name"] for row in conn.execute(
            "SELECT column_name AS name FROM information_schema.columns WHERE table_name = 'users'"
        )}

else:
    # Local dev: zero-config SQLite file.
    import sqlite3

    def _get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    _USERS_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """

    def _existing_user_columns(conn):
        return {row["name"] for row in conn.execute("PRAGMA table_info(users)")}


USER_COLUMNS = {
    "phone": "TEXT",
    "gender": "TEXT",
    "avatar_data_url": "TEXT",
    "theme": "TEXT NOT NULL DEFAULT 'light'",
    "notifications_enabled": "INTEGER NOT NULL DEFAULT 1",
    "language": "TEXT NOT NULL DEFAULT 'en'",
}


def _init_db():
    with _get_db() as conn:
        conn.execute(_USERS_TABLE_SQL)
        existing = _existing_user_columns(conn)
        for col, decl in USER_COLUMNS.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")


_init_db()

# ── Load model artifacts once at startup ───────────────────────────────────
model = joblib.load(os.path.join(OUTPUT_DIR, "crop_prediction_model.pkl"))
encoder = joblib.load(os.path.join(OUTPUT_DIR, "label_encoder.pkl"))
scaler = joblib.load(os.path.join(OUTPUT_DIR, "scaler.pkl"))
feature_ranges = joblib.load(os.path.join(OUTPUT_DIR, "feature_ranges.pkl"))

df = pd.read_csv(DATA_PATH)
_df_feat = df[FEATURES].values.astype(float)
_df_labels = df["label"].values
_col_mins = _df_feat.min(axis=0)
_col_maxs = _df_feat.max(axis=0)
_col_ranges = np.where(_col_maxs - _col_mins == 0, 1.0, _col_maxs - _col_mins)

# Crop labels known to the dataset, used to validate `explain_crop` input.
_crop_means = df.groupby("label")[FEATURES].mean()

_RANK_VERDICTS = {
    0: "These values closely match typical {crop} conditions, hence {crop} is the best crop to grow.",
    1: "These values match typical {crop} conditions moderately, hence {crop} is a good option after the top recommended crop.",
    2: "These values are a bit off the mark for typical {crop} conditions, but growing {crop} is still the best option among the rest.",
}


def explain_crop(crop: str, filled: dict, rank: int):
    """List every soil parameter and its value, then a closing verdict on
    this crop's fit based on its rank among the top-3 recommendations
    (0 = top pick, 1 = second, 2 = third)."""
    if crop not in _crop_means.index:
        return []

    reasons = []
    for f in FEATURES:
        meta = FEATURE_META[f]
        unit = f" {meta['unit']}".rstrip()
        value = round(filled[f], 1)
        reasons.append(f"{meta['label']}: {value}{unit}")

    verdict = _RANK_VERDICTS.get(rank, _RANK_VERDICTS[2])
    reasons.append(verdict.format(crop=crop))
    return reasons


def predict_crop_fuzzy(values: dict):
    """
    values: dict with keys from FEATURES, any of which may be None/missing.
    Returns (top3 list of {crop, confidence}, used_fuzzy: bool)
    """
    raw = np.array([values.get(f) for f in FEATURES], dtype=float)
    known_mask = ~np.isnan(raw)

    filled = raw.copy()
    used_fuzzy = False

    if not known_mask.all():
        # Nearest-neighbour fill for unknown columns, based on known columns only.
        used_fuzzy = True
        norm_known = (_df_feat[:, known_mask] - _col_mins[known_mask]) / _col_ranges[known_mask]
        norm_query = (raw[known_mask] - _col_mins[known_mask]) / _col_ranges[known_mask]
        dist = np.sqrt(((norm_known - norm_query) ** 2).sum(axis=1))
        nearest_idx = np.argmin(dist)
        filled[~known_mask] = _df_feat[nearest_idx, ~known_mask]

    scaled = scaler.transform(pd.DataFrame([filled], columns=FEATURES))
    proba = model.predict_proba(scaled)[0]

    top_conf = proba.max()
    if top_conf < CONF_THRESHOLD:
        used_fuzzy = True
        norm_known = (_df_feat - _col_mins) / _col_ranges
        norm_query = (filled - _col_mins) / _col_ranges
        dist = np.sqrt(((norm_known - norm_query) ** 2).sum(axis=1))
        closeness = 1 - (dist / (dist.max() if dist.max() > 0 else 1))

        combined = {}
        for i, cls in enumerate(encoder.classes_):
            combined[cls] = proba[i]
        for i, lbl in enumerate(_df_labels):
            score = closeness[i] * combined.get(lbl, 0.05)
            combined[lbl] = max(combined.get(lbl, 0), score)

        ranked = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)[:3]
    else:
        top_idx = np.argsort(proba)[::-1][:3]
        ranked = [(encoder.classes_[i], float(proba[i])) for i in top_idx]

    total = sum(max(c, 0) for _, c in ranked) or 1.0
    top3 = [
        {"crop": crop, "confidence": round(float(conf) / total, 4) if used_fuzzy else round(float(conf), 4)}
        for crop, conf in ranked
    ]
    return top3, used_fuzzy


def normalize_pct(feature: str, value: float) -> int:
    lo = feature_ranges[feature]["min"]
    hi = feature_ranges[feature]["max"]
    if hi == lo:
        return 0
    pct = (value - lo) / (hi - lo) * 100
    return int(round(max(0, min(100, pct))))


def npk_shares(n: float, p: float, k: float):
    """N, P and K expressed as a share of their combined kg/ha, summing to 100%."""
    total = max(n, 0) + max(p, 0) + max(k, 0)
    if total <= 0:
        return 0, 0, 0
    n_pct = int(round(max(n, 0) / total * 100))
    p_pct = int(round(max(p, 0) / total * 100))
    k_pct = 100 - n_pct - p_pct
    return n_pct, p_pct, k_pct


def ph_label(ph: float) -> str:
    if ph < 5.5:
        return "Acidic"
    if ph <= 7.5:
        return "Optimal"
    return "Alkaline"


def moisture_label(humidity: float) -> str:
    if humidity < 30:
        return "Low"
    if humidity <= 70:
        return "Adequate"
    return "High"


_temp_q1, _temp_q2 = df["temperature"].quantile([0.33, 0.66])
_rain_q1, _rain_q2 = df["rainfall"].quantile([0.33, 0.66])


def temperature_label(temp: float) -> str:
    if temp < _temp_q1:
        return "Cool"
    if temp <= _temp_q2:
        return "Moderate"
    return "Hot"


def rainfall_label(rainfall: float) -> str:
    if rainfall < _rain_q1:
        return "Low"
    if rainfall <= _rain_q2:
        return "Moderate"
    return "High"


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


def _user_public(row):
    return {
        "full_name": row["full_name"],
        "email": row["email"],
        "created_at": row["created_at"],
        "phone": row["phone"],
        "gender": row["gender"],
        "avatar_data_url": row["avatar_data_url"],
        "theme": row["theme"],
        "notifications_enabled": bool(row["notifications_enabled"]),
        "language": row["language"],
    }


def _current_user_row(conn):
    user_id = session.get("user_id")
    if not user_id:
        return None
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


@app.route("/api/signup", methods=["POST"])
def signup():
    body = request.get_json(force=True) or {}
    full_name = (body.get("full_name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not full_name or not email or not password:
        return jsonify({"error": "Full name, email and password are all required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    with _get_db() as conn:
        if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            return jsonify({"error": "An account with this email already exists."}), 409
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO users (full_name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (full_name, email, generate_password_hash(password), created_at),
        )
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    session["user_id"] = row["id"]
    return jsonify(_user_public(row))


@app.route("/api/login", methods=["POST"])
def login():
    body = request.get_json(force=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    with _get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Incorrect email or password."}), 401

    session["user_id"] = row["id"]
    return jsonify(_user_public(row))


@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    return jsonify({"ok": True})


@app.route("/api/me", methods=["GET"])
def me():
    user_id = session.get("user_id")
    row = None
    if user_id:
        with _get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        session.pop("user_id", None)
        return jsonify({"error": "Not logged in."}), 401
    return jsonify(_user_public(row))


@app.route("/api/profile", methods=["PATCH"])
def update_profile():
    body = request.get_json(force=True) or {}

    with _get_db() as conn:
        row = _current_user_row(conn)
        if not row:
            return jsonify({"error": "Not logged in."}), 401

        updates = {}

        if "full_name" in body:
            full_name = (body["full_name"] or "").strip()
            if not full_name:
                return jsonify({"error": "Full name can't be empty."}), 400
            updates["full_name"] = full_name

        if "email" in body:
            email = (body["email"] or "").strip().lower()
            if not email:
                return jsonify({"error": "Email can't be empty."}), 400
            clash = conn.execute(
                "SELECT id FROM users WHERE email = ? AND id != ?", (email, row["id"])
            ).fetchone()
            if clash:
                return jsonify({"error": "An account with this email already exists."}), 409
            updates["email"] = email

        if "phone" in body:
            updates["phone"] = (body["phone"] or "").strip()

        if "gender" in body:
            gender = body["gender"] or None
            if gender not in (None, "male", "female"):
                return jsonify({"error": "Invalid gender value."}), 400
            updates["gender"] = gender

        if updates:
            set_clause = ", ".join(f"{col} = ?" for col in updates)
            conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", (*updates.values(), row["id"]))
            row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()

    return jsonify(_user_public(row))


MAX_AVATAR_DATA_URL_LEN = 2_800_000  # ~2MB image, base64-encoded


@app.route("/api/profile/avatar", methods=["POST"])
def update_avatar():
    body = request.get_json(force=True) or {}
    data_url = body.get("avatar_data_url") or None

    if data_url is not None:
        if not data_url.startswith("data:image/"):
            return jsonify({"error": "Invalid image data."}), 400
        if len(data_url) > MAX_AVATAR_DATA_URL_LEN:
            return jsonify({"error": "Image is too large (max ~2MB)."}), 400

    with _get_db() as conn:
        row = _current_user_row(conn)
        if not row:
            return jsonify({"error": "Not logged in."}), 401
        conn.execute("UPDATE users SET avatar_data_url = ? WHERE id = ?", (data_url, row["id"]))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()

    return jsonify(_user_public(row))


@app.route("/api/change-password", methods=["POST"])
def change_password():
    body = request.get_json(force=True) or {}
    current_password = body.get("current_password") or ""
    new_password = body.get("new_password") or ""

    with _get_db() as conn:
        row = _current_user_row(conn)
        if not row:
            return jsonify({"error": "Not logged in."}), 401
        if not check_password_hash(row["password_hash"], current_password):
            return jsonify({"error": "Current password is incorrect."}), 401
        if len(new_password) < 6:
            return jsonify({"error": "New password must be at least 6 characters."}), 400
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(new_password), row["id"]),
        )

    return jsonify({"ok": True})


@app.route("/api/preferences", methods=["PATCH"])
def update_preferences():
    body = request.get_json(force=True) or {}

    with _get_db() as conn:
        row = _current_user_row(conn)
        if not row:
            return jsonify({"error": "Not logged in."}), 401

        updates = {}
        if "theme" in body:
            if body["theme"] not in ("light", "dark"):
                return jsonify({"error": "Invalid theme."}), 400
            updates["theme"] = body["theme"]
        if "notifications_enabled" in body:
            updates["notifications_enabled"] = 1 if body["notifications_enabled"] else 0
        if "language" in body:
            if body["language"] not in ("en", "tw"):
                return jsonify({"error": "Invalid language."}), 400
            updates["language"] = body["language"]

        if updates:
            set_clause = ", ".join(f"{col} = ?" for col in updates)
            conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", (*updates.values(), row["id"]))
            row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()

    return jsonify(_user_public(row))


@app.route("/api/predict", methods=["POST"])
def predict():
    body = request.get_json(force=True) or {}
    values = {}
    for f in FEATURES:
        v = body.get(f, None)
        values[f] = None if v in (None, "") else float(v)

    top3, used_fuzzy = predict_crop_fuzzy(values)

    filled = dict(values)
    if any(v is None for v in values.values()):
        raw = np.array([values.get(f) for f in FEATURES], dtype=float)
        known_mask = ~np.isnan(raw)
        norm_known = (_df_feat[:, known_mask] - _col_mins[known_mask]) / _col_ranges[known_mask]
        norm_query = (raw[known_mask] - _col_mins[known_mask]) / _col_ranges[known_mask]
        dist = np.sqrt(((norm_known - norm_query) ** 2).sum(axis=1))
        nearest_idx = np.argmin(dist)
        for i, f in enumerate(FEATURES):
            if filled[f] is None:
                filled[f] = float(_df_feat[nearest_idx, i])

    n_pct, p_pct, k_pct = npk_shares(filled["N"], filled["P"], filled["K"])

    response = {
        "recommendations": [
            {**rec, "reasons": explain_crop(rec["crop"], filled, rank)} for rank, rec in enumerate(top3)
        ],
        "used_fuzzy": used_fuzzy,
        "readings": {
            "N": {"value": round(filled["N"], 1), "percent": n_pct},
            "P": {"value": round(filled["P"], 1), "percent": p_pct},
            "K": {"value": round(filled["K"], 1), "percent": k_pct},
            "ph": {"value": round(filled["ph"], 2), "label": ph_label(filled["ph"])},
            "humidity": {"value": round(filled["humidity"], 1), "label": moisture_label(filled["humidity"])},
            "temperature": {
                "value": round(filled["temperature"], 1),
                "percent": normalize_pct("temperature", filled["temperature"]),
                "label": temperature_label(filled["temperature"]),
            },
            "rainfall": {
                "value": round(filled["rainfall"], 1),
                "percent": normalize_pct("rainfall", filled["rainfall"]),
                "label": rainfall_label(filled["rainfall"]),
            },
        },
    }
    return jsonify(response)


@app.route("/api/sample", methods=["GET"])
def random_sample():
    """Returns a random real row from the dataset, useful as a demo starting point."""
    row = df.sample(1).iloc[0]
    return jsonify({f: float(row[f]) for f in FEATURES} | {"label": row["label"]})


@app.route("/api/weather")
def get_weather():
    """Proxy to OpenWeatherMap current-weather (keeps API key server-side).
    Returns location name, temperature, humidity, description, and hourly rain."""
    lat = request.args.get("lat", "").strip()
    lon = request.args.get("lon", "").strip()
    if not lat or not lon:
        return jsonify({"error": "lat and lon query params are required"}), 400
    if not OPENWEATHER_API_KEY:
        return jsonify({"error": "Weather service not configured — add OPENWEATHER_API_KEY to env"}), 503

    try:
        params = urllib.parse.urlencode({
            "lat": lat, "lon": lon,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
        })
        url = f"https://api.openweathermap.org/data/2.5/weather?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "AkuafoAni/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            w = json.loads(resp.read().decode())

        rain_raw = w.get("rain") or {}
        rain_mm = round(float(rain_raw.get("1h") or rain_raw.get("3h") or 0), 2)

        return jsonify({
            "location": w.get("name", ""),
            "country": (w.get("sys") or {}).get("country", ""),
            "temperature": (w.get("main") or {}).get("temp"),
            "humidity": (w.get("main") or {}).get("humidity"),
            "description": ((w.get("weather") or [{}])[0]).get("description", "").title(),
            "icon_code": ((w.get("weather") or [{}])[0]).get("icon", ""),
            "rain_mm_hr": rain_mm,
            "wind_speed": (w.get("wind") or {}).get("speed"),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/rainfall")
def get_annual_rainfall():
    """Returns the total annual rainfall (mm) for the given GPS location by
    summing the past 365 days of daily precipitation from Open-Meteo's free
    historical archive (no API key required).  This value pre-fills the Rainfall
    input on the Crops form so farmers don't have to look it up manually."""
    lat = request.args.get("lat", "").strip()
    lon = request.args.get("lon", "").strip()
    if not lat or not lon:
        return jsonify({"error": "lat and lon query params are required"}), 400

    try:
        end = date.today()
        start = end - timedelta(days=365)
        params = urllib.parse.urlencode({
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": "precipitation_sum",
            "timezone": "auto",
        })
        url = f"https://archive-api.open-meteo.com/v1/archive?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "AkuafoAni/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())

        precip_list = (data.get("daily") or {}).get("precipitation_sum") or []
        annual_mm = round(sum(v for v in precip_list if v is not None), 1)
        return jsonify({"annual_mm": annual_mm})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


ABENA_TTS_URL = "https://abena.mobobi.com/playground/api/v1/tts/synthesize/"
ABENA_ALLOWED_VOICES = {
    "abena_twi_high", "abena_twi_lite",
    "kwabena_eng", "akua_eng",
    "kobby_gpe", "mawuli_ewe",
}
# Optional: set ABENA_API_KEY in the Render dashboard (or .env locally) to use
# your own Abena account key and bypass the 30-request anonymous free tier.
ABENA_API_KEY = os.environ.get("ABENA_API_KEY", "")

@app.route("/api/tts", methods=["POST"])
def tts_proxy():
    """TTS endpoint — routes by voice:
      • Twi voices (abena_twi_lite / abena_twi_high): served locally via
        stable-twi-tts ONNX model (no quota, no external API).
      • English/other voices: forwarded to the Abena cloud API.
    Returns {audio_base64, duration_seconds, mime_type, status}.
    """
    body = request.get_json(silent=True) or {}
    text  = str(body.get("text", "")).strip()[:500]
    voice = str(body.get("voice", "kwabena_eng"))
    speed = float(body.get("speed", 1.0))

    if not text:
        return jsonify({"error": "text is required"}), 400

    # ── Twi: use local ONNX model ─────────────────────────────────────────
    if voice in ("abena_twi_lite", "abena_twi_high") and _twi_tts:
        try:
            # length_scale is the inverse of speed (slower = longer duration)
            length_scale = 1.0 / max(float(speed), 0.25)
            synth = _twi_tts.synthesize(
                text, voice="twi-1", language="mixed",
                length_scale=length_scale,
            )
            audio_b64, duration = _synthesis_to_wav_b64(synth)
            return jsonify({
                "status": "success",
                "audio_base64": audio_b64,
                "duration_seconds": duration,
                "mime_type": "audio/wav",
            })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    # ── English / other voices: forward to Abena cloud API ───────────────
    if voice not in ABENA_ALLOWED_VOICES:
        voice = "kwabena_eng"

    payload = json.dumps({"text": text, "voice": voice, "speed": speed}).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "AkuafoAni/1.0"}
    if ABENA_API_KEY:
        headers["Authorization"] = f"Bearer {ABENA_API_KEY}"

    req = urllib.request.Request(
        ABENA_TTS_URL, data=payload, headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        return jsonify(data), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
