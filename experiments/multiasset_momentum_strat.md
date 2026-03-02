
# Live Trading with OpenAlgo — HMM + XGBoost Regime Strategy

## Model Provenance

| Config | Value |
|---|---|
| **Stock** | `RELIANCE` (NSE) |
| **Timeframe** | `1h` (1-hour candles) |
| **Training Period** | 2021-01-01 → 2024-01-01 (3 years) |
| **Saved to** | `experiments/models/RELIANCE_1h/` |

**Artifacts saved:**
- `hmm_model.joblib` — GaussianHMM regime detector (3 states: Bull/Sideways/Bear)
- `hmm_scaler.joblib` — StandardScaler fitted to HMM feature window
- `booster_xgb.json` — XGBoost triple-barrier classifier (predicts: upper/time/lower barrier)
- `metadata.json` — Feature lists, label maps, thresholds, trade barriers

---

## Architecture Overview

```
New 1h candle arrives
        │
        ▼
1. Compute HMM features        (log_ret, vol_spread, asset_vix_corr, vix_velocity)
        │
        ▼
2. HMM predict_proba()         → p_bull, p_sideways, p_bear
        │
        ▼
3. Compute XGBoost features    (dist_sma200, adx, atr, force_index, ret_1h/6h/24h, rsi)
        │
        ▼
4. XGBoost predict_proba()     → p_upper_first (PT hit), p_time, p_lower_first (SL hit)
        │
        ▼
5. Tech signal scoring         (RSI + MACD histogram + EMA crossover → score ∈ [-2, +2])
        │
        ▼
6. Signal gate:
   BUY  if p_bull  ≥ 0.80 AND tech_score ≥ 0
   SELL if p_bear  ≥ 0.70 AND tech_score ≤ 0
   HOLD otherwise
        │
        ▼
7. Send order to OpenAlgo      POST /api/v1/placeorder
```

---

## Prerequisites

1. **OpenAlgo running** locally: `http://127.0.0.1:5000`
   - Login → Settings → copy your **API Key**
   - Ensure your broker is connected and market session is live
2. **Python packages**: `joblib`, `hmmlearn`, `xgboost`, `ta`, `requests`
3. **INDIAVIX data** must be fetchable alongside RELIANCE for HMM features

---

## Step 1 — Load Saved Models

```python
import json, joblib, pathlib
from xgboost import XGBClassifier

MODEL_DIR = pathlib.Path("models/RELIANCE_1h")

hmm_model  = joblib.load(MODEL_DIR / "hmm_model.joblib")
scaler     = joblib.load(MODEL_DIR / "hmm_scaler.joblib")
booster    = XGBClassifier()
booster.load_model(str(MODEL_DIR / "booster_xgb.json"))

with open(MODEL_DIR / "metadata.json") as f:
    meta = json.load(f)

hmm_feature_cols  = meta["hmm_feature_cols"]
feature_cols_long = meta["feature_cols_long"]
BUY_THRESHOLD     = meta["buy_threshold"]   # 0.80
SELL_THRESHOLD    = meta["sell_threshold"]  # 0.70
state_name_map    = {int(k): v for k, v in meta["state_name_map"].items()}
```

---

## Step 2 — Signal Inference on a New Candle

```python
import numpy as np
import pandas as pd
import ta

def compute_signal(ohlcv_df: pd.DataFrame, vix_df: pd.DataFrame) -> str:
    """
    Given recent OHLCV history (>= 200 rows) and aligned VIX history,
    returns 'BUY', 'SELL', or 'HOLD'.
    """
    # --- HMM features ---
    asset_log_ret = np.log(ohlcv_df["close"]).diff()
    vix_log_ret   = np.log(vix_df["close"]).diff()
    vol_spread    = asset_log_ret.rolling(20).std() - vix_log_ret.rolling(20).std()
    corr          = asset_log_ret.rolling(20).corr(vix_log_ret)
    vix_vel       = vix_df["close"].diff()

    hmm_feats = pd.DataFrame({
        "asset_log_ret":      asset_log_ret,
        "vol_spread_20h":     vol_spread,
        "asset_vix_corr_20h": corr,
        "vix_velocity_1h":    vix_vel,
    }).dropna()

    X_hmm = scaler.transform(hmm_feats[hmm_feature_cols].tail(1).values)
    p_states = hmm_model.predict_proba(X_hmm)  # shape (1, 3)

    # Map raw state indices to semantic labels using saved state_name_map
    bull_state = next(k for k, v in state_name_map.items() if v == "Bull/Low-Vol")
    bear_state = next(k for k, v in state_name_map.items() if v == "Bear/High-Vol")
    p_bull = float(p_states[0, bull_state])
    p_bear = float(p_states[0, bear_state])

    # --- XGBoost features ---
    close = ohlcv_df["close"]
    sma200 = close.rolling(200).mean()
    feats = {
        "dist_sma_200":    (close / sma200 - 1.0).iloc[-1],
        "adx_14":          ta.trend.adx(ohlcv_df["high"], ohlcv_df["low"], close, window=14).iloc[-1],
        "atr_14":          ta.volatility.average_true_range(ohlcv_df["high"], ohlcv_df["low"], close, window=14).iloc[-1],
        "atr_pct_14":      ta.volatility.average_true_range(ohlcv_df["high"], ohlcv_df["low"], close, window=14).iloc[-1] / close.iloc[-1],
        "force_index_13":  ta.volume.force_index(close, ohlcv_df["volume"], window=13).iloc[-1],
        "ret_1h":          close.pct_change().iloc[-1],
        "ret_6h":          close.pct_change(6).iloc[-1],
        "ret_24h":         close.pct_change(24).iloc[-1],
        "rsi_14":          ta.momentum.rsi(close, window=14).iloc[-1],
    }
    X_boost = pd.DataFrame([feats])[feature_cols_long]
    # Not used for direct signal in this setup — HMM drives entry, XGBoost for confidence
    # Optionally gate: only enter if p_upper_first is highest class
    boost_proba = booster.predict_proba(X_boost)[0]  # [p_lower, p_time, p_upper]

    # --- Technical scoring ---
    rsi_val   = feats["rsi_14"]
    macd_obj  = ta.trend.MACD(close, window_fast=12, window_slow=26, window_sign=9)
    macd_hist = (macd_obj.macd_diff() - macd_obj.macd_signal()).iloc[-1]
    ema12     = ta.trend.ema_indicator(close, window=12).iloc[-1]
    ema26     = ta.trend.ema_indicator(close, window=26).iloc[-1]
    price     = close.iloc[-1]

    tech_score = 0.0
    if pd.notna(rsi_val):
        if rsi_val > 70: tech_score -= 1
        elif rsi_val < 30: tech_score += 1
    if pd.notna(macd_hist):
        tech_score += 0.5 if macd_hist > 0 else -0.5
    if all(pd.notna(x) for x in [ema12, ema26, price]):
        if price > ema12 > ema26: tech_score += 1
        elif price < ema12 < ema26: tech_score -= 1

    # --- Gating ---
    if p_bull >= BUY_THRESHOLD and tech_score >= 0:
        return "BUY"
    elif p_bear >= SELL_THRESHOLD and tech_score <= 0:
        return "SELL"
    return "HOLD"
```

---

## Step 3 — Place Order via OpenAlgo

```python
import requests

OPENALGO_URL = "http://127.0.0.1:5000"
API_KEY      = "your_api_key_here"   # from OpenAlgo Settings
SYMBOL       = "RELIANCE"
EXCHANGE     = "NSE"
QUANTITY     = 1                     # adjust to your position size
PRODUCT      = "MIS"                 # intraday; use "NRML" for positional

def place_openalgo_order(action: str) -> dict:
    """action must be 'BUY' or 'SELL'."""
    payload = {
        "apikey":    API_KEY,
        "strategy":  "HMM_XGB_Regime",
        "symbol":    SYMBOL,
        "exchange":  EXCHANGE,
        "action":    action,
        "quantity":  QUANTITY,
        "pricetype": "MARKET",
        "product":   PRODUCT,
    }
    resp = requests.post(
        f"{OPENALGO_URL}/api/v1/placeorder",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
```

---

## Step 4 — Live Loop (1h polling)

```python
import time
from datetime import datetime, timezone

last_action = "HOLD"

while True:
    now = datetime.now(timezone.utc)
    # Fetch latest 1h candles (minimum 250 bars for SMA-200 warm-up)
    result      = fetch_ohlcv_data(base_url, "RELIANCE", "1h", years=2)
    ohlcv_data  = result["ohlcv_data"].get("candles", [])
    ohlcv_df    = candles_to_ohlcv_df(ohlcv_data)

    vix_result  = fetch_ohlcv_data(base_url, "INDIAVIX", "1h",
                                   start_dt=result["start_dt"], end_dt=result["end_dt"])
    vix_candles = vix_result["ohlcv_data"].get("candles", [])
    vix_df_live = candles_to_ohlcv_df(vix_candles).rename(columns={"close": "close"})

    signal = compute_signal(ohlcv_df, vix_df_live)
    print(f"[{now:%Y-%m-%d %H:%M}] Signal: {signal}  (prev: {last_action})")

    if signal != last_action and signal in ("BUY", "SELL"):
        order_resp = place_openalgo_order(signal)
        print(f"  → Order sent: {order_resp}")
        last_action = signal
    elif signal == "HOLD" and last_action == "BUY":
        # Optional: square off on HOLD after BUY (remove if using triple-barrier SL/PT)
        pass

    # Sleep until next 1h candle close (3600s minus processing time)
    time.sleep(3600)
```

> **Tip:** Run the loop inside a screen/tmux session or wrap it in a systemd service to keep it alive.

---

## Retraining the Model

### A) Retrain on the same stock with more recent data

1. In the data-fetch cell, extend `end_dt` to today:
   ```python
   end_dt = datetime.now(timezone.utc)
   start_dt = datetime(2021, 1, 1, tzinfo=timezone.utc)
   ```
2. Re-run all cells sequentially from the feature-engineering cell onwards.
3. Re-run the HMM training cell — `n_iter=500` and `random_state=42` are fixed for reproducibility.
4. Re-run the XGBoost training cell — early stopping is already enabled.
5. Re-run the export cell — it overwrites `models/RELIANCE_1h/` with the fresh artifacts.

### B) Train on a different stock

1. Update the ticker and date range in the data-fetch cell:
   ```python
   ticker    = "HDFCBANK"   # or any NSE symbol
   timeframe = "1h"
   start_dt  = datetime(2021, 1, 1, tzinfo=timezone.utc)
   end_dt    = datetime(2024, 1, 1, tzinfo=timezone.utc)
   ```
2. Re-run all cells from feature engineering through to the export cell.
3. The export cell automatically creates `models/HDFCBANK_1h/` — the original `RELIANCE_1h/` models are **not overwritten**.

### C) Change timeframe (e.g. 15m)

1. Set `timeframe = "15m"` in the data-fetch cell.
2. Adjust rolling windows proportionally (e.g. `window=20` → `window=80` for roughly 1h equivalent context).
3. Adjust `TIME_BARRIER_H` in the triple-barrier cell to match the new granularity.
4. Re-run and export as above.

### D) Hyperparameter tuning

| Model | Key parameters | Where to change |
|---|---|---|
| HMM | `n_components` (default 3), `n_iter` | HMM training cell |
| HMM thresholds | `BUY_THRESHOLD`, `SELL_THRESHOLD` | Posterior probabilities cell |
| XGBoost | `n_estimators`, `max_depth`, `learning_rate` | Boosted model cell |
| Triple Barrier | `PT_PCT=0.05`, `SL_PCT=0.02`, `TIME_BARRIER_H=20` | Triple barrier cell |

> After any change, **always** re-run the comparison cell to verify the updated strategy still outperforms HMM-only on the in-sample period before deploying.
