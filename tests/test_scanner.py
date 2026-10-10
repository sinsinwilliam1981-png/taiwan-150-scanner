import pandas as pd
import pytest

from scanner.indicators import add_indicators, evaluate, normalize_ohlcv
from scanner.run import ROOT, load_constituents


def test_constituent_gate_is_exactly_50_plus_100():
    rows = load_constituents(ROOT / "config/constituents.csv")
    assert len(rows) == 150
    assert len({r["stock_id"] for r in rows}) == 150


def test_constituent_gate_rejects_duplicate(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("index,stock_id,stock_name\nTW50,2330,x\nTW50,2330,x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_constituents(path)


def test_indicators_and_strategy():
    dates = pd.date_range("2026-01-01", periods=140, freq="B")
    close = pd.Series(range(100, 240), dtype=float)
    raw = pd.DataFrame({"date": dates, "open": close-1, "max": close+1, "min": close-2, "close": close, "Trading_Volume": [1000]*139+[2000]})
    latest = add_indicators(normalize_ohlcv(raw)).iloc[-1]
    result = evaluate(latest, {"volume_ratio_min":1.2,"rsi_min":50,"rsi_max":100,"max_extension_from_ma20_pct":8,"near_trigger_score":60,"candidate_score":75})
    assert latest.ma60 > 0
    assert result["score"] >= 75

