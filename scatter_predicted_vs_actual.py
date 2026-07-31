"""
Reproduces the RF+XGBoost soft-voting ensemble from train_model.py, then
plots each crop class's actual total (support) against its predicted total,
with a y = x reference line (perfect prediction) and a fitted line of best
fit. Vertical segments show exactly how far each class's predictions drift
from actual.

Run:
    python scatter_predicted_vs_actual.py
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

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
class_names = encoder.classes_

# actual_totals[i]    = how many test samples truly belong to class i (row sum)
# predicted_totals[i] = how many samples the model predicted as class i (col sum)
# A perfect model puts every point on the y = x diagonal; the vertical segment
# from each point down to the diagonal is exactly how far predictions drift
# from actual for that crop.
actual_totals = cm.sum(axis=1).astype(float)
predicted_totals = cm.sum(axis=0).astype(float)

fig, (ax, ax_text) = plt.subplots(1, 2, figsize=(11, 7), gridspec_kw={"width_ratios": [3, 1.3]})
lims = [0, max(actual_totals.max(), predicted_totals.max()) + 3]
ax.plot(lims, lims, color="#888888", linewidth=1.5, linestyle="--", label="Perfect prediction (y = x)")

for xi, yi in zip(actual_totals, predicted_totals):
    ax.plot([xi, xi], [xi, yi], color="#E65100", linewidth=1, alpha=0.6, zorder=1)

ax.scatter(actual_totals, predicted_totals, color="#2C5F2D", edgecolor="white", s=60, zorder=2)

slope, intercept = np.polyfit(actual_totals, predicted_totals, 1)
x_line = np.linspace(lims[0], lims[1], 100)
ax.plot(x_line, slope * x_line + intercept, color="#1565C0", linewidth=2,
        label=f"Best fit: y = {slope:.3f}x + {intercept:.3f}")

ax.set_xlim(lims)
ax.set_ylim(lims)
ax.set_aspect("equal")
ax.set_xlabel("Actual total (support)")
ax.set_ylabel("Predicted total")
ax.legend(fontsize=9, loc="upper left")

# ── Side panel: classes whose predicted total deviates from actual ────────────
deviations = sorted(
    ((name, xi, yi) for name, xi, yi in zip(class_names, actual_totals, predicted_totals) if abs(xi - yi) > 0.5),
    key=lambda t: abs(t[1] - t[2]), reverse=True,
)
ax_text.axis("off")
ax_text.set_title("Deviation from actual", fontsize=10, fontweight="bold", loc="left")
lines = [f"{name}: {int(yi)} vs {int(xi)}  ({'+' if yi > xi else ''}{int(yi - xi)})" for name, xi, yi in deviations]
ax_text.text(0, 1, "\n".join(lines) if lines else "All classes match exactly.",
             fontsize=9, va="top", ha="left", transform=ax_text.transAxes, family="monospace")

fig.suptitle("Ensemble (RF + XGBoost) — Predicted vs Actual Totals per Crop Class",
             fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig("outputs/scatter_predicted_vs_actual.png", dpi=150, bbox_inches="tight")
print("Saved plot to outputs/scatter_predicted_vs_actual.png")
