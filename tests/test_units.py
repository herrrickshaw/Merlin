"""Unit tests for pure functions and injected-client paths (no network)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import batch_screener as bs
import data_fetcher as df
import screener_runner as sr
from characterise import GOOD_FUND, _synthetic_stock

ROOT = Path(__file__).resolve().parent.parent


def _bars(n=300, close=100.0):
    idx = pd.bdate_range("2023-01-02", periods=n)
    return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1,
                         "Close": close, "Adj Close": close, "Volume": 10.0}, index=idx)


def test_fetchers_use_injected_downloader():
    calls = []

    def fake(symbol, start=None, end=None, progress=False):
        calls.append(symbol)
        return _bars()

    fetcher = df.MarketDataFetcher(download=fake, ticker_factory=lambda s: None)
    assert len(fetcher.us.fetch_us_data("AAPL", "a", "b")) == 300
    fetcher.nse.fetch_nse_data("TCS.NS", "a", "b")
    fetcher.nse.fetch_nse_data("INFY", "a", "b")
    assert calls == ["AAPL", "TCS.BO", "INFY.BO"]   # NSE symbols are rewritten to .BO


def test_download_failure_returns_none_and_logs(caplog):
    def boom(*a, **k):
        raise RuntimeError("down")

    assert df.USStockFetcher(boom).fetch_us_data("AAPL", "a", "b") is None
    assert "Error fetching US data for AAPL" in caplog.text


def test_historical_prices_are_cached():
    n = []

    def fake(*a, **k):
        n.append(1)
        return _bars()

    hist = df.HistoricalPriceFetcher(fake)
    first = hist.fetch_historical_prices("X", "a", "b")
    assert hist.fetch_historical_prices("X", "a", "b") is first
    assert len(n) == 1


def test_symbol_lists_are_copies():
    fetcher = df.MarketDataFetcher(download=lambda *a, **k: None, ticker_factory=lambda s: None)
    fetcher.us.get_us_symbols().clear()
    assert len(fetcher.us.get_us_symbols()) == 25
    assert set(fetcher.get_all_symbols(["India"])) == {"NSE", "BSE"}


def test_validate_data_rules():
    ok = {"prices": pd.DataFrame({"close": np.ones(300)}), "volumes": {"volume": [1.0]}}
    assert df.validate_data(ok) == (True, "Valid")
    short = {"prices": pd.DataFrame({"close": np.ones(10)}), "volumes": {"volume": [1.0]}}
    assert df.validate_data(short) == (False, "Insufficient data (10 days)")


def test_cmf_accumulation_detected():
    n = 20
    vol = {"close": np.full(n, 9.9), "high": np.full(n, 10.0), "low": np.full(n, 9.0),
           "volume": np.full(n, 100.0)}
    out = bs.StockFilters.chaikin_money_flow(vol)
    assert out["passed"] and out["status"] == "STRONG_ACCUMULATION"


def test_full_triple_hit_end_to_end():
    """Regression for the missing BatchScreener.chaikin_money_flow (see PR 'Behaviour changes')."""
    stock = _synthetic_stock("HIT", GOOD_FUND)
    close = stock["volumes"]["close"]
    stock["volumes"] = {**stock["volumes"], "high": close + 0.1, "low": close - 1.0}  # closes near highs
    screener = bs.BatchScreener()
    hits = screener.screen_market({"USA": [stock]})
    assert [h["symbol"] for h in hits] == ["HIT"]
    assert screener.get_results_dataframe().iloc[0]["Symbol"] == "HIT"


def test_screener_runner_registry_and_ranking():
    assert list(sr.STRATEGIES) == ["darvas", "piotroski", "coffee_can", "magic_formula", "golden_crossover"]
    assert sr.pct_change(110, 100) == 10.0 and sr.pct_change(1, 0) is None
    assert sr.cagr(200, 100, 1) == 100.0 and sr.cagr(200, 100, 0.5) is None
    assert sr.sma([1, 2, 3, 4], 2) == 3.5 and sr.sma([1], 2) is None


def test_parse_args():
    assert sr.parse_args(["x", "f.csv"]) == ("f.csv", None, 10)
    assert sr.parse_args(["x", "f.csv", "--strategy", "darvas", "--top", "3"]) == ("f.csv", "darvas", 3)


def test_screener_runner_top_flag_limits_rows():
    out = subprocess.run([sys.executable, "screener_runner.py", "examples/screener_test_data.csv",
                          "--top", "1"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert " 2. " not in out
