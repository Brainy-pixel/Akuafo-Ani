"""
Akuafo Ani — local web server.

Loads the trained crop-recommendation model and serves:
  - the dashboard web page (frontend/)
  - a JSON prediction API at POST /api/predict
  - account signup/login/logout (SQLite-backed) at /api/signup, /api/login,
    /api/logout, /api/me

Run with:
    python app.py
Then open http://127.0.0.1:5000 in your browser.
"""
import os
import secrets
import sqlite3
from datetime import datetime, timezone

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


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
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


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
