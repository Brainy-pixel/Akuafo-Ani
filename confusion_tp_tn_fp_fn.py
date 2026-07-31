"""
Reproduces the RF+XGBoost soft-voting ensemble from train_model.py, then
collapses the 33-class confusion matrix into an aggregated (micro-averaged,
one-vs-rest summed over all classes) TP / TN / FP / FN 2x2 matrix.

Run:
    python confusion_tp_tn_fp_fn.py
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import confusion_matrix
from xgboost import XGBClassifier

DATA_PATH = "Crop_recommendation_filtered.csv"
FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
TARGET = "label"
SEED = 42

df = pd.read_csv(DATA_PATH)
X = df[FEATURES].copy()
y = df[TARGET].copy()

encoder = LabelEncoder()
y_encoded = encoder.fit_transform(y)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y_encoded, test_size=0.2, random_state=SEED, stratify=y_encoded
)

rf_model = RandomForestClassifier(
    n_estimators=200, max_depth=None, class_weight="balanced",
    random_state=SEED, n_jobs=-1,
)
xgb_model = XGBClassifier(
    n_estimators=200, max_depth=6, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    objective="multi:softprob", eval_metric="mlogloss",
    random_state=SEED, n_jobs=-1, verbosity=0,
)
ensemble_model = VotingClassifier(
    estimators=[("rf", rf_model), ("xgb", xgb_model)],
    voting="soft", weights=[0.5, 0.5], n_jobs=-1,
)
ensemble_model.fit(X_train, y_train)
ensemble_pred = ensemble_model.predict(X_test)

cm = confusion_matrix(y_test, ensemble_pred)
n_classes = cm.shape[0]
total = cm.sum()

# One-vs-rest per class, then summed (micro-averaged) across all classes.
TP = np.diag(cm).sum()
FP = (cm.sum(axis=0) - np.diag(cm)).sum()
FN = (cm.sum(axis=1) - np.diag(cm)).sum()
TN = total * n_classes - (TP + FP + FN)

print(f"Classes: {n_classes}   Test samples: {total}")
print(f"TP = {TP}")
print(f"FP = {FP}")
print(f"FN = {FN}")
print(f"TN = {TN}")

agg = np.array([[TP, FN], [FP, TN]])
labels = np.array([["TP", "FN"], ["FP", "TN"]])
annot = np.array([[f"TP\n{TP}", f"FN\n{FN}"], [f"FP\n{FP}", f"TN\n{TN}"]])

fig, ax = plt.subplots(figsize=(5, 5))
sns.heatmap(
    agg, annot=annot, fmt="", cmap="YlGn", cbar=True,
    xticklabels=["Predicted Positive", "Predicted Negative"],
    yticklabels=["Actual Positive", "Actual Negative"],
    linewidths=0.5, ax=ax,
)
ax.set_title("Aggregated Confusion Matrix — Ensemble (RF + XGBoost)\n(micro-averaged, one-vs-rest summed over all classes)",
             fontsize=11, fontweight="bold")
plt.tight_layout()
plt.savefig("outputs/confusion_tp_tn_fp_fn.png", dpi=150, bbox_inches="tight")
print("\nSaved plot to outputs/confusion_tp_tn_fp_fn.png")
# plt.show() removed - non-interactive run
