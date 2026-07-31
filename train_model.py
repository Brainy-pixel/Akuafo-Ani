"""
Trains the crop recommendation model from the CSV dataset and saves the
trained artifacts (model, label encoder, feature scaler) into outputs/.

Run this once (or whenever the dataset changes):
    python train_model.py
"""
import os
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from xgboost import XGBClassifier

DATA_PATH = "Crop_recommendation_filtered.csv"
OUTPUT_DIR = "outputs"
FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
TARGET = "label"
SEED = 42


def main():
    print(f"Loading dataset from '{DATA_PATH}'...")
    df = pd.read_csv(DATA_PATH)
    print(f"  Rows: {len(df):,}   Columns: {df.columns.tolist()}")
    print(f"  Crop classes ({df[TARGET].nunique()}): {sorted(df[TARGET].unique())}")

    X = df[FEATURES].copy()
    y = df[TARGET].copy()

    encoder = LabelEncoder()
    y_encoded = encoder.fit_transform(y)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y_encoded, test_size=0.2, random_state=SEED, stratify=y_encoded
    )

    print("\nTraining Random Forest...")
    rf_model = RandomForestClassifier(
        n_estimators=200, max_depth=None, class_weight="balanced",
        random_state=SEED, n_jobs=-1,
    )
    rf_model.fit(X_train, y_train)
    rf_acc = accuracy_score(y_test, rf_model.predict(X_test))
    print(f"  Random Forest accuracy: {rf_acc*100:.2f}%")

    print("Training XGBoost...")
    xgb_model = XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        objective="multi:softprob", eval_metric="mlogloss",
        random_state=SEED, n_jobs=-1, verbosity=0,
    )
    xgb_model.fit(X_train, y_train)
    xgb_acc = accuracy_score(y_test, xgb_model.predict(X_test))
    print(f"  XGBoost accuracy: {xgb_acc*100:.2f}%")

    print("Building weighted soft-voting ensemble (RF 0.5 / XGBoost 0.5)...")
    ensemble_model = VotingClassifier(
        estimators=[("rf", rf_model), ("xgb", xgb_model)],
        voting="soft", weights=[0.5, 0.5], n_jobs=-1,
    )
    ensemble_model.fit(X_train, y_train)
    ensemble_pred = ensemble_model.predict(X_test)

    acc = accuracy_score(y_test, ensemble_pred)
    prec = precision_score(y_test, ensemble_pred, average="macro")
    rec = recall_score(y_test, ensemble_pred, average="macro")
    f1 = f1_score(y_test, ensemble_pred, average="macro")

    print("\n" + "=" * 52)
    print("  ENSEMBLE MODEL — EVALUATION METRICS")
    print("=" * 52)
    print(f"  Accuracy  : {acc*100:.2f}%")
    print(f"  Precision : {prec*100:.2f}%  (macro avg)")
    print(f"  Recall    : {rec*100:.2f}%  (macro avg)")
    print(f"  F1-score  : {f1*100:.2f}%  (macro avg)")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    joblib.dump(ensemble_model, os.path.join(OUTPUT_DIR, "crop_prediction_model.pkl"))
    joblib.dump(encoder, os.path.join(OUTPUT_DIR, "label_encoder.pkl"))
    joblib.dump(scaler, os.path.join(OUTPUT_DIR, "scaler.pkl"))

    # Dataset-level min/max per feature, used by the app to normalise raw
    # readings (e.g. N in kg/ha) into 0-100% gauges for the dashboard.
    feature_ranges = {
        col: {"min": float(df[col].min()), "max": float(df[col].max())}
        for col in FEATURES
    }
    joblib.dump(feature_ranges, os.path.join(OUTPUT_DIR, "feature_ranges.pkl"))

    print(f"\nSaved model, encoder, scaler, and feature ranges to '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()
