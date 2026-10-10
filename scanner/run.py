from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .finmind import FinMindClient
from .indicators import add_indicators, evaluate, normalize_ohlcv


ROOT = Path(__file__).resolve().parents[1]
TAIPEI = timezone(timedelta(hours=8))


def load_constituents(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    counts = {key: sum(row["index"] == key for row in rows) for key in ("TW50", "MID100")}
    ids = [row["stock_id"] for row in rows]
    if counts != {"TW50": 50, "MID100": 100} or len(set(ids)) != 150:
        raise ValueError(f"constituent gate failed: counts={counts}, unique={len(set(ids))}")
    return rows


def serial_number(value):
    if value is None or value != value:
        return None
    return round(float(value), 4)


def scan(today: date | None = None) -> dict:
    now = datetime.now(TAIPEI)
    today = today or now.date()
    config = json.loads((ROOT / "config/strategy.json").read_text(encoding="utf-8"))
    meta = json.loads((ROOT / "config/constituents.meta.json").read_text(encoding="utf-8"))
    members = load_constituents(ROOT / "config/constituents.csv")
    start = today - timedelta(days=config["lookback_calendar_days"])
    client = FinMindClient(
        token=os.getenv("FINMIND_TOKEN", ""),
        max_workers=config["max_workers"],
        pause_seconds=config["request_pause_seconds"],
    )
    frames, fetch_errors = client.fetch_many([m["stock_id"] for m in members], start.isoformat(), today.isoformat())
    results, failures = [], []
    names = {m["stock_id"]: m for m in members}
    minimum = config["minimum_trading_days"]
    for sid in names:
        if sid in fetch_errors:
            failures.append({"stock_id": sid, "reason": fetch_errors[sid]})
            continue
        try:
            normalized = normalize_ohlcv(frames[sid])
            if len(normalized) < minimum:
                failures.append({"stock_id": sid, "reason": f"only {len(normalized)} trading days"})
                continue
            enriched = add_indicators(normalized)
            latest = enriched.iloc[-1]
            verdict = evaluate(latest, config["strategy"])
            results.append({
                **names[sid], "date": latest.date.date().isoformat(),
                "trading_days": len(normalized), "close": serial_number(latest.close),
                "ma5": serial_number(latest.ma5), "ma10": serial_number(latest.ma10),
                "ma20": serial_number(latest.ma20), "ma60": serial_number(latest.ma60),
                "rsi14": serial_number(latest.rsi14), "volume_ratio": serial_number(latest.volume_ratio),
                "boll_upper": serial_number(latest.boll_upper), "boll_lower": serial_number(latest.boll_lower),
                "position120": serial_number(latest.position120),
                "extension_ma20_pct": serial_number(latest.extension_ma20_pct),
                "return_20d_pct": serial_number(latest.return_20d_pct), **verdict,
            })
        except Exception as exc:
            failures.append({"stock_id": sid, "reason": str(exc)})
    complete = len(results) == 150 and not failures
    results.sort(key=lambda row: (-row["score"], row["stock_id"]))
    return {
        "schema_version": 1, "generated_at": now.isoformat(), "requested_end_date": today.isoformat(),
        "status": "complete" if complete else "blocked", "publishable": complete,
        "gate": {"expected": 150, "passed": len(results), "failed": len(failures), "minimum_trading_days": minimum},
        "constituents": meta, "token_used": bool(client.token), "failures": failures, "results": results if complete else [],
        "disclaimer": "技術指標僅供研究，不構成投資建議。完整性閘門未通過時不發布候選股。"
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD; defaults to Taipei today")
    parser.add_argument("--output", default=str(ROOT / "site/data/latest.json"))
    args = parser.parse_args()
    result = scan(date.fromisoformat(args.date) if args.date else None)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    history = ROOT / "site/data/history" / f'{result["requested_end_date"]}.json'
    history.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output, history)
    print(json.dumps(result["gate"], ensure_ascii=False))
    raise SystemExit(0 if result["publishable"] else 2)


if __name__ == "__main__":
    main()

