# Akuafo Ani — Soil Nutrient & Crop Recommendation Dashboard

Flow: **Dataset -> Model -> App -> Recommendation**

- `Crop_recommendation_filtered.csv` — the dataset (soil N/P/K, temperature,
  humidity, pH, rainfall, and the crop that grows best under those conditions).
- `train_model.py` — trains a Random Forest + XGBoost ensemble on the dataset
  and saves it into `outputs/`. Run this once, or again if you replace the CSV.
- `app.py` — a small local web server that loads the trained model, answers
  prediction requests from the dashboard, and explains each recommendation
  by comparing the input readings against each crop's typical range in the
  dataset.
- `frontend/` — the dashboard web page (what you see in the browser).
- `frontend/images/crops/` — one photo per crop label, named to match the
  dataset's `label` column (lowercase, e.g. `rice.jpg`, `tomato.jpg`).

## How to run it

1. Install the required packages (only needed once):
   ```
   pip install -r requirements.txt
   ```
2. Train the model (only needed once, or after changing the dataset):
   ```
   python train_model.py
   ```
3. Start the app:
   ```
   python app.py
   ```
4. Open your browser to **http://127.0.0.1:5000**

The dashboard loads a real random soil sample automatically. Enter your own
N, P, K, temperature, humidity, pH and rainfall readings (leave any field
blank if you don't know it — the model will estimate it from similar
samples) and click **Analyze Soil Sample** to get the top-3 recommended
crops for that soil.

Sign up or log in to use the app — accounts are stored in `users.db`
(SQLite, created automatically on first run) with hashed passwords.

## Deploying to Render (free, permanent URL)

This repo includes `render.yaml`, so Render can configure everything
automatically via its "Blueprint" deploy:

1. Push this repo to GitHub.
2. On [render.com](https://render.com), choose **New +** → **Blueprint**,
   and point it at the GitHub repo. Render reads `render.yaml` and sets up
   the web service, install/start commands, and a random `SECRET_KEY`
   automatically.
3. Once deployed, the app is reachable at a stable
   `https://akuafo-ani.onrender.com`-style URL that doesn't expire.

**Note:** the free tier's disk is not guaranteed to persist across
redeploys, so `users.db` (sign-ups) could reset when you redeploy. This is
fine for demoing; if you need accounts to survive redeploys long-term,
swap SQLite for a hosted database (e.g. a free Postgres instance) — ask
and I can help wire that up.
