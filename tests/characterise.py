"""Characterisation driver: records observable behaviour of the Python modules.

``snapshot(repo_dir)`` imports the modules from ``repo_dir`` with a stubbed
``yfinance`` (no network) and returns a JSON-serialisable dict. The golden file
in ``tests/golden/`` was produced from the pre-refactor code (master) and the
tests assert that the refactored code reproduces it exactly.
"""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

N_DAYS = 300


def _frame(symbol: str) -> pd.DataFrame:
    """Deterministic OHLCV frame (300 business days) seeded from the symbol."""
    rng = np.random.default_rng(sum(map(ord, symbol)))
    idx = pd.bdate_range("2023-01-02", periods=N_DAYS)
    close = 100 + np.cumsum(rng.normal(0.2, 1.0, N_DAYS))
    high = close + rng.uniform(0.1, 2.0, N_DAYS)
    low = close - rng.uniform(0.1, 2.0, N_DAYS)
    return pd.DataFrame(
        {
            "Open": close - 0.1,
            "High": high,
            "Low": low,
            "Close": close,
            "Adj Close": close,
            "Volume": rng.integers(1_000, 2_000, N_DAYS).astype(float),
        },
        index=idx,
    )


def make_stub_yfinance() -> types.ModuleType:
    """Fake ``yfinance`` module; ``BAD`` symbols raise, ``EMPTY`` returns no rows."""
    stub = types.ModuleType("yfinance")

    def download(symbol, start=None, end=None, progress=False, **_kw):
        if symbol.startswith("BAD"):
            raise RuntimeError("boom")
        if symbol.startswith("EMPTY"):
            return pd.DataFrame()
        return _frame(symbol)

    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol
            if symbol.startswith("BAD"):
                raise RuntimeError("boom")

        @property
        def info(self):
            return {"marketCap": 5e9, "trailingPE": 20.0, "returnOnEquity": 0.2,
                    "currentPrice": 123.5, "totalRevenue": 1e9}

    stub.download = download
    stub.Ticker = Ticker
    return stub


def _load(repo_dir: Path):
    """Import data_fetcher and batch_screener fresh from ``repo_dir``."""
    for name in ("yfinance", "data_fetcher", "batch_screener", "screener_runner"):
        sys.modules.pop(name, None)
    sys.modules["yfinance"] = make_stub_yfinance()
    sys.modules.setdefault("requests", types.ModuleType("requests"))  # unused by the code
    sys.path.insert(0, str(repo_dir))
    try:
        return (importlib.import_module("data_fetcher"),
                importlib.import_module("batch_screener"),
                importlib.import_module("screener_runner"))
    finally:
        sys.path.remove(str(repo_dir))


def _digest(values: list) -> dict:
    """Compact fingerprint of a long list: length, head, tail and a checksum."""
    flat = [_jsonable(v) if not isinstance(v, (list, tuple)) else v for v in values]
    text = json.dumps(flat, default=str)
    return {"n": len(flat), "head": flat[:3], "tail": flat[-3:],
            "crc": __import__("zlib").crc32(text.encode())}


def _jsonable(obj):
    if isinstance(obj, (np.floating, float)):
        return round(float(obj), 9)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.ndarray, pd.api.extensions.ExtensionArray)):
        return _digest(obj.tolist())
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, pd.DataFrame):
        return {"shape": list(obj.shape), "columns": [str(c) for c in obj.columns],
                "data": _digest(obj.to_numpy(dtype=object).ravel().tolist())}
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj
    return str(obj)


def _synthetic_stock(symbol: str, fundamentals: dict | None) -> dict:
    """Rising-price stock that passes the Darvas stage (volume spike on last bar)."""
    close = np.linspace(100.0, 150.0, N_DAYS)
    volume = np.full(N_DAYS, 1000.0)
    volume[-1] = 5000.0
    prices = pd.DataFrame({"date": pd.bdate_range("2023-01-02", periods=N_DAYS), "close": close})
    volumes = {"close": close, "high": close + 1.0, "low": close - 1.0, "volume": volume}
    return {"symbol": symbol, "prices": prices, "volumes": volumes, "fundamentals": fundamentals}


GOOD_FUND = {"net_income": 1, "operating_cash_flow": 1, "roe": 0.2, "debt_to_equity": 0.5,
             "current_ratio": 2.0, "revenue": 1, "profit_margin": 0.1, "roa": 0.1,
             "free_cash_flow": 1, "pe_ratio": 20, "market_cap": 1e9}


def _stage_cases(bs) -> dict:
    """Run screen_market on stocks that stop at each stage; record counters/exceptions."""
    cases = {
        "stage1_only": _synthetic_stock("S1", {**GOOD_FUND, "net_income": -1, "revenue": 0,
                                               "operating_cash_flow": -1, "free_cash_flow": -1}),
        "stage2_pass_stage3_fail": _synthetic_stock("S2", {**GOOD_FUND, "pe_ratio": 80}),
        "all_stages": _synthetic_stock("S3", GOOD_FUND),
        "no_fundamentals": _synthetic_stock("S4", None),
    }
    out = {}
    for name, stock in cases.items():
        screener = bs.BatchScreener()
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                hits = screener.screen_market({"USA": [stock]})
            out[name] = {"hits": hits, "stdout": buf.getvalue()}
        except Exception as exc:  # recorded, not asserted on message text
            out[name] = {"raised": type(exc).__name__}
    return out


def snapshot(repo_dir: Path) -> dict:
    df, bs, sr = _load(Path(repo_dir))
    out: dict = {}
    # Error-path messages are print()ed pre-refactor and logged post-refactor, so
    # they are not part of the contract; silence stdout for that block.
    quiet = contextlib.redirect_stdout(io.StringIO())
    quiet.__enter__()

    fetcher = df.MarketDataFetcher()
    out["symbols"] = fetcher.get_all_symbols()
    out["symbols_us"] = fetcher.get_all_symbols(["USA"])
    out["nse_data_empty"] = fetcher.nse.fetch_nse_data("EMPTY.NS", "2023-01-01", "2024-01-01").shape
    out["bad_us"] = fetcher.us.fetch_us_data("BAD", "2023-01-01", "2024-01-01")
    out["bad_fund"] = fetcher.fundamentals.fetch_fundamentals("BAD")
    out["fund"] = fetcher.fundamentals.fetch_fundamentals("AAPL")
    out["price"] = fetcher.get_current_price("AAPL")
    out["bad_price"] = fetcher.get_current_price("BAD")
    out["volume"] = fetcher.volume.fetch_volume_data("AAPL", "2023-01-01", "2024-01-01")
    out["hist"] = fetcher.historical.fetch_historical_prices("AAPL", "2023-01-01", "2024-01-01")
    out["hist_empty"] = fetcher.historical.fetch_historical_prices("EMPTY", "2023-01-01", "2024-01-01")
    stock = fetcher.fetch_stock_data("MSFT", "2023-01-01", "2024-01-01")
    out["stock"] = stock
    out["validate"] = [df.validate_data(stock), df.validate_data(
        {"prices": None, "volumes": None, "fundamentals": None})]

    quiet.__exit__(None, None, None)
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        md = fetcher.fetch_market_data("2023-01-01", "2024-01-01", markets=["USA"])
    out["market_summary"] = {k: [s["symbol"] for s in v] for k, v in md.items()}
    out["fetch_stdout"] = buf.getvalue()

    filt = bs.StockFilters()
    prices = stock["prices"]
    vols = stock["volumes"]
    out["darvas"] = filt.darvas_box(prices, vols)
    out["darvas_short"] = filt.darvas_box(prices.iloc[:100], vols)
    good = {"net_income": 1, "operating_cash_flow": 1, "roe": 0.2, "debt_to_equity": 0.5,
            "current_ratio": 2.0, "revenue": 1, "profit_margin": 0.1, "roa": 0.1,
            "free_cash_flow": 1, "pe_ratio": 20}
    bad = {"net_income": -1, "operating_cash_flow": -1, "revenue": 0, "free_cash_flow": -1,
           "pe_ratio": 80, "debt_to_equity": 3.0}
    out["piotroski"] = [filt.piotroski_score(good), filt.piotroski_score(bad), filt.piotroski_score(None)]
    out["coffee"] = [filt.coffee_can_check(good), filt.coffee_can_check(bad), filt.coffee_can_check({})]
    out["cmf"] = [filt.chaikin_money_flow(vols), filt.chaikin_money_flow(None),
                  filt.chaikin_money_flow({"close": [1.0] * 3, "high": [1.0] * 3,
                                           "low": [1.0] * 3, "volume": [0.0] * 3}, period=3)]

    screener = bs.BatchScreener()
    out["screen_stock_invalid"] = screener.screen_stock(
        {"symbol": "X", "prices": None, "volumes": None, "fundamentals": None})
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        hits = screener.screen_market({"USA": [stock]})
    out["screen_market_hits"] = hits
    out["screen_market_stdout"] = buf.getvalue()
    out["results_df_empty"] = screener.get_results_dataframe()

    out["stage_cases"] = _stage_cases(bs)

    csv_path = Path(repo_dir) / "examples" / "screener_test_data.csv"
    stocks = sr.load_csv_to_stocks(str(csv_path))
    results = sr.screen_market(stocks)
    out["runner"] = [[r.symbol, r.strategy, r.passed, r.score, r.metrics, r.note] for r in results]
    out["runner_rank"] = {s: [r.symbol for r in sr.rank_results(results, s)]
                          for s in ("darvas", "piotroski", "coffee_can", "magic_formula", "golden_crossover")}
    return _jsonable(out)


if __name__ == "__main__":
    print(json.dumps(snapshot(Path(sys.argv[1])), indent=1, sort_keys=True))
