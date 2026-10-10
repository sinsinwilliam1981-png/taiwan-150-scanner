from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import requests


API_URL = "https://api.finmindtrade.com/api/v4/data"


class FinMindError(RuntimeError):
    pass


@dataclass
class FinMindClient:
    token: str = ""
    max_workers: int = 5
    pause_seconds: float = 0.15
    timeout: int = 45

    def fetch_one(self, stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
        }
        if self.token:
            params["token"] = self.token
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = requests.get(API_URL, params=params, timeout=self.timeout)
                if response.status_code == 429:
                    raise FinMindError("FinMind rate limit (HTTP 429)")
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") != 200:
                    raise FinMindError(payload.get("msg", "FinMind API error"))
                return pd.DataFrame(payload.get("data", []))
            except (requests.RequestException, ValueError, FinMindError) as exc:
                last_error = exc
                if attempt == 3:
                    break
                time.sleep(2**attempt)
        raise FinMindError(f"{stock_id}: {last_error}")

    def fetch_many(self, stock_ids: Iterable[str], start_date: str, end_date: str):
        frames: dict[str, pd.DataFrame] = {}
        errors: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(self.fetch_one, sid, start_date, end_date): sid
                for sid in stock_ids
            }
            for future in as_completed(futures):
                sid = futures[future]
                try:
                    frames[sid] = future.result()
                except Exception as exc:  # recorded; completeness gate decides publication
                    errors[sid] = str(exc)
                time.sleep(self.pause_seconds)
        return frames, errors

