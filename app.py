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
import os
import json
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
DATA_PATH = "Crop_recommendation_filtered4.csv"
CONF_THRESHOLD   = 0.30   # below this, blend in nearest-neighbour "fuzzy" matches
MIN_SLOT_CONF    = 0.08   # individual recommendation slots below this are suppressed
NPK_TOLERANCE    = 10.0   # ±10 mg/kg buffer applied to per-crop N/P/K training range
DB_PATH = "users.db"
SECRET_KEY_PATH = os.path.join(OUTPUT_DIR, ".flask_secret")

FEATURE_META = {
    "N": {"label": "Nitrogen", "unit": "mg/kg"},
    "P": {"label": "Phosphorus", "unit": "mg/kg"},
    "K": {"label": "Potassium", "unit": "mg/kg"},
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
crop_profiles = joblib.load(os.path.join(OUTPUT_DIR, "crop_profiles.pkl"))

df = pd.read_csv(DATA_PATH)
_df_feat = df[FEATURES].values.astype(float)
_df_labels = df["label"].values
_col_mins = _df_feat.min(axis=0)
_col_maxs = _df_feat.max(axis=0)
_col_ranges = np.where(_col_maxs - _col_mins == 0, 1.0, _col_maxs - _col_mins)

# Crop labels known to the dataset, used to validate `explain_crop` input.
_crop_means = df.groupby("label")[FEATURES].mean()


def _npk_in_tolerance(crop: str, filled: dict) -> bool:
    """Return True if the filled N, P and K values all fall within the crop's
    training-data range extended by ±NPK_TOLERANCE on each side."""
    if crop not in crop_profiles:
        return True  # unknown crop — let model handle it
    prof = crop_profiles[crop]
    for feat in ("N", "P", "K"):
        lo = prof[feat]["min"] - NPK_TOLERANCE
        hi = prof[feat]["max"] + NPK_TOLERANCE
        if not (lo <= filled[feat] <= hi):
            return False
    return True


def _improvement_tips(crop: str, filled: dict) -> list[str]:
    """Return a list of actionable improvement tips comparing the user's filled
    values to the crop profile means. Empty list when all values are good."""
    if crop not in crop_profiles:
        return []
    prof = crop_profiles[crop]
    tips = []
    n_val, n_mean = filled["N"], prof["N"]["mean"]
    p_val, p_mean = filled["P"], prof["P"]["mean"]
    k_val, k_mean = filled["K"], prof["K"]["mean"]
    ph_val, ph_mean = filled["ph"], prof["ph"]["mean"]
    temp_val, temp_mean = filled["temperature"], prof["temperature"]["mean"]
    rain_val, rain_mean = filled["rainfall"], prof["rainfall"]["mean"]

    if n_val < n_mean - 10:
        tips.append(f"Increase nitrogen by applying a nitrogen-rich fertilizer "
                    f"(e.g. urea or ammonium nitrate). Current level is {round(n_val,1)} mg/kg, "
                    f"below the optimal {round(n_mean,1)} mg/kg for {crop}.")
    elif n_val > n_mean + 10:
        tips.append(f"Reduce nitrogen input. Current level ({round(n_val,1)} mg/kg) "
                    f"exceeds the optimal {round(n_mean,1)} mg/kg for {crop}.")

    if p_val < p_mean - 8:
        tips.append(f"Boost phosphorus with a phosphate fertilizer (e.g. DAP or SSP). "
                    f"Current level is {round(p_val,1)} mg/kg, below the optimal {round(p_mean,1)} mg/kg.")
    elif p_val > p_mean + 8:
        tips.append(f"Reduce phosphorus input. Current level ({round(p_val,1)} mg/kg) "
                    f"exceeds the optimal {round(p_mean,1)} mg/kg.")

    if k_val < k_mean - 8:
        tips.append(f"Apply a potash supplement (e.g. muriate of potash) to raise "
                    f"potassium from {round(k_val,1)} mg/kg to the optimal {round(k_mean,1)} mg/kg.")
    elif k_val > k_mean + 8:
        tips.append(f"Reduce potassium application. Current level ({round(k_val,1)} mg/kg) "
                    f"is above the optimal {round(k_mean,1)} mg/kg.")

    if ph_val < ph_mean - 0.5:
        tips.append(f"Soil pH {round(ph_val,2)} is below the preferred "
                    f"~{round(ph_mean,2)} for {crop}. Apply agricultural lime "
                    f"(calcium carbonate) to raise pH.")
    elif ph_val > ph_mean + 0.5:
        tips.append(f"Soil pH {round(ph_val,2)} is above the preferred "
                    f"~{round(ph_mean,2)} for {crop}. Apply elemental sulfur "
                    f"or acidifying fertilizer to lower pH.")

    if abs(temp_val - temp_mean) > 4:
        direction = "warmer" if temp_val < temp_mean else "cooler"
        tips.append(f"Average temperature {round(temp_val,1)} °C differs from the "
                    f"ideal ~{round(temp_mean,1)} °C for {crop}. "
                    f"Consider shade structures or windbreaks for a {direction} microclimate.")

    if rain_val < rain_mean * 0.6:
        tips.append(f"Rainfall {round(rain_val,1)} mm is well below the "
                    f"~{round(rain_mean,1)} mm preferred by {crop}. "
                    f"Supplement with drip or furrow irrigation.")
    elif rain_val > rain_mean * 1.5:
        tips.append(f"Rainfall {round(rain_val,1)} mm significantly exceeds "
                    f"the ~{round(rain_mean,1)} mm preferred by {crop}. "
                    f"Ensure good drainage to prevent waterlogging.")

    return tips

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
    Returns (top3 list of {crop, confidence}, used_fuzzy: bool, no_match: bool)

    no_match is True when inputs are all near-zero or when no crop survives the
    NPK tolerance check and confidence threshold — caller should return the
    "no matching soil" response instead of crop recommendations.
    """
    raw = np.array([values.get(f) for f in FEATURES], dtype=float)
    known_mask = ~np.isnan(raw)

    # ── Guard: all-zero / near-zero NPK means no soil data provided ───────
    n_val = values.get("N") or 0
    p_val = values.get("P") or 0
    k_val = values.get("K") or 0
    if n_val < 1 and p_val < 1 and k_val < 1:
        return [], False, True  # no_match

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

    filled_dict = {f: float(filled[i]) for i, f in enumerate(FEATURES)}

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

    # ── Filter: remove slots below confidence threshold or outside NPK ±5 ──
    top3 = []
    for crop, conf in ranked:
        conf_norm = round(float(conf) / total, 4) if used_fuzzy else round(float(conf), 4)
        if conf_norm < MIN_SLOT_CONF:
            continue
        if not _npk_in_tolerance(crop, filled_dict):
            continue
        top3.append({"crop": crop, "confidence": conf_norm})

    no_match = len(top3) == 0
    return top3, used_fuzzy, no_match


def normalize_pct(feature: str, value: float) -> int:
    lo = feature_ranges[feature]["min"]
    hi = feature_ranges[feature]["max"]
    if hi == lo:
        return 0
    pct = (value - lo) / (hi - lo) * 100
    return int(round(max(0, min(100, pct))))


def npk_shares(n: float, p: float, k: float):
    """N, P and K expressed as a share of their combined mg/kg total, summing to 100%."""
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

    top3, used_fuzzy, no_match = predict_crop_fuzzy(values)

    # ── Resolve filled values (for readings + tips), filling missing with
    # nearest-neighbour imputation (same logic as predict_crop_fuzzy). ──────
    filled = {f: values[f] for f in FEATURES}
    raw = np.array([values.get(f) for f in FEATURES], dtype=float)
    if any(v is None for v in values.values()):
        known_mask = ~np.isnan(raw)
        norm_known = (_df_feat[:, known_mask] - _col_mins[known_mask]) / _col_ranges[known_mask]
        norm_query = (raw[known_mask] - _col_mins[known_mask]) / _col_ranges[known_mask]
        dist = np.sqrt(((norm_known - norm_query) ** 2).sum(axis=1))
        nearest_idx = np.argmin(dist)
        for i, f in enumerate(FEATURES):
            if filled[f] is None:
                filled[f] = float(_df_feat[nearest_idx, i])

    n_pct, p_pct, k_pct = npk_shares(filled["N"], filled["P"], filled["K"])

    readings = {
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
    }

    # ── No-match path ─────────────────────────────────────────────────────
    if no_match:
        ph_val = filled["ph"]

        # Build the pH tip and advice only when pH is outside the acceptable band
        if ph_val < 5.5:
            # Acidic soil, apply a base (alkaline substance) to raise pH
            ph_tip = (
                f"Soil pH is {round(ph_val, 2)} (acidic, below 5.5). "
                "Apply agricultural lime (calcium carbonate, a basic compound) to neutralise "
                "the acidity and raise pH into the ideal range (5.5 to 7.0)."
            )
            ph_advice = (
                f"Soil pH of {round(ph_val, 2)} is too acidic for most crops. "
                "Apply agricultural lime (calcium carbonate) to raise pH. "
                "Lime is alkaline and neutralises excess soil acids, making nutrients more available for plant uptake."
            )
        elif ph_val > 7.0:
            # Alkaline soil, apply an acid to lower pH
            ph_tip = (
                f"Soil pH is {round(ph_val, 2)} (alkaline, above 7.0). "
                "Apply elemental sulfur (an acidifying agent, e.g. ammonium sulfate) to "
                "lower pH into the ideal range (5.5 to 7.0)."
            )
            ph_advice = (
                f"Soil pH of {round(ph_val, 2)} is too alkaline for most crops. "
                "Apply elemental sulfur, which is oxidised by soil bacteria into sulfuric acid, "
                "gradually lowering pH to the preferred range (5.5 to 7.0)."
            )
        else:
            ph_tip   = None
            ph_advice = None

        general_tips = [
            "Apply a balanced NPK fertilizer (e.g. 15-15-15) to build up soil nutrient levels before the next planting season.",
            "Conduct a full soil test to identify which nutrients are most deficient.",
            "Improve soil organic matter by incorporating compost or well-rotted manure.",
            "Ensure proper drainage to avoid waterlogging, which limits nutrient uptake.",
        ]
        if ph_tip:
            general_tips.insert(2, ph_tip)  # insert after the soil-test tip

        base_advice = (
            "Consider applying a balanced NPK fertilizer to improve soil nutrient levels "
            "before the next planting season."
        )
        advice = f"{ph_advice} {base_advice}" if ph_advice else base_advice

        return jsonify({
            "no_match": True,
            "used_fuzzy": used_fuzzy,
            "readings": readings,
            "message": (
                "No crop matches this soil profile. The current nutrient levels and soil "
                "characteristics do not fall within the acceptable range for any crop "
                "to be recommended yet."
            ),
            "advice": advice,
            "improvement_tips": general_tips,
        })

    # ── Normal path ───────────────────────────────────────────────────────
    top_crop = top3[0]["crop"] if top3 else None
    improvement_tips = _improvement_tips(top_crop, filled) if top_crop else []

    response = {
        "no_match": False,
        "recommendations": [
            {**rec, "reasons": explain_crop(rec["crop"], filled, rank)} for rank, rec in enumerate(top3)
        ],
        "used_fuzzy": used_fuzzy,
        "readings": readings,
        "improvement_tips": improvement_tips,
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
    """Proxy to the Abena TTS API so the browser avoids CORS restrictions.
    Accepts JSON {text, voice, speed} and forwards to Abena, returning
    {audio_base64, duration_seconds, mime_type, status}."""
    body = request.get_json(silent=True) or {}
    text  = str(body.get("text", "")).strip()[:500]   # API limit: 500 chars
    voice = str(body.get("voice", "kwabena_eng"))
    speed = float(body.get("speed", 1.0))

    if not text:
        return jsonify({"error": "text is required"}), 400
    if voice not in ABENA_ALLOWED_VOICES:
        voice = "kwabena_eng"

    payload = json.dumps({"text": text, "voice": voice, "speed": speed}).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "AkuafoAni/1.0"}
    if ABENA_API_KEY:
        headers["Authorization"] = f"Bearer {ABENA_API_KEY}"

    req = urllib.request.Request(
        ABENA_TTS_URL,
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        return jsonify(data), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
