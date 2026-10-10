from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {"date", "open", "max", "min", "close", "Trading_Volume"}


def normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    out = frame.rename(columns={"max": "high", "min": "low", "Trading_Volume": "volume"}).copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    return out.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    close = out["close"]
    for window in (5, 10, 20, 60):
        out[f"ma{window}"] = close.rolling(window).mean()
    out["vol_ma20"] = out["volume"].rolling(20).mean()
    out["volume_ratio"] = out["volume"] / out["vol_ma20"].replace(0, np.nan)
    std20 = close.rolling(20).std(ddof=0)
    out["boll_upper"] = out["ma20"] + 2 * std20
    out["boll_lower"] = out["ma20"] - 2 * std20
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi14"] = 100 - 100 / (1 + rs)
    out.loc[(loss == 0) & (gain > 0), "rsi14"] = 100
    out.loc[(loss == 0) & (gain == 0), "rsi14"] = 50
    out["high120"] = close.rolling(120).max()
    out["low120"] = close.rolling(120).min()
    spread = (out["high120"] - out["low120"]).replace(0, np.nan)
    out["position120"] = (close - out["low120"]) / spread * 100
    out["extension_ma20_pct"] = (close / out["ma20"] - 1) * 100
    out["return_20d_pct"] = close.pct_change(20) * 100
    return out


def evaluate(latest: pd.Series, strategy: dict) -> dict:
    checks = {
        "trend": bool(latest.ma5 > latest.ma10 > latest.ma20 > latest.ma60),
        "above_ma20": bool(latest.close > latest.ma20),
        "volume": bool(latest.volume_ratio >= strategy["volume_ratio_min"]),
        "rsi": bool(strategy["rsi_min"] <= latest.rsi14 <= strategy["rsi_max"]),
        "not_extended": bool(latest.extension_ma20_pct <= strategy["max_extension_from_ma20_pct"]),
        "positive_20d": bool(latest.return_20d_pct > 0),
    }
    weights = {"trend": 30, "above_ma20": 15, "volume": 20, "rsi": 15, "not_extended": 10, "positive_20d": 10}
    score = sum(weights[key] for key, passed in checks.items() if passed)
    if score >= strategy["candidate_score"]:
        label = "candidate"
    elif score >= strategy["near_trigger_score"]:
        label = "near"
    else:
        label = "watch"
    return {"score": score, "label": label, "checks": checks}
