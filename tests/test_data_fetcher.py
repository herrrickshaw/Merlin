"""data_fetcher.py with yfinance faked (no network): fetchers, cache, validation, CSV export."""
import numpy as np
import pandas as pd
import pytest

import data_fetcher as df_


def ohlcv(n=3, adj=True, start="2024-01-01"):
    idx = pd.date_range(start, periods=n)
    d = {"Open": np.arange(n) + 1.0, "High": np.arange(n) + 2.0, "Low": np.arange(n) + 0.5,
         "Close": np.arange(n) + 1.5, "Volume": np.arange(n) * 10 + 100}
    if adj:
        d["Adj Close"] = np.arange(n) + 1.4
    return pd.DataFrame(d, index=idx)


@pytest.fixture
def dl(monkeypatch):
    calls = []

    def fake(symbol, start=None, end=None, progress=None):
        calls.append((symbol, start, end, progress))
        return fake.result

    fake.result = ohlcv()
    monkeypatch.setattr(df_.yf, "download", fake)
    fake.calls = calls
    return fake


# ------------------------------- symbol lists -------------------------------

def test_symbol_lists():
    nse = df_.NSEDataFetcher().get_nse_symbols()
    assert len(nse) == 25 and all(s.endswith(".NS") for s in nse)
    bse = df_.BSEDataFetcher().get_bse_symbols()
    assert len(bse) == 5 and all(s.endswith(".BO") for s in bse)
    us = df_.USStockFetcher().get_us_symbols()
    assert len(us) == 25 and "AAPL" in us and not any("." in s for s in us)
    assert df_.NSEDataFetcher().headers["User-Agent"].startswith("Mozilla")


# ------------------------------- simple download wrappers -------------------------------

def test_nse_fetch_symbol_mapping_current_behaviour(dl):
    """NOTE: .NS symbols are downloaded as .BO (BSE listing) -- pinned as-is, see PR notes."""
    f = df_.NSEDataFetcher()
    out = f.fetch_nse_data("TCS.NS", "2024-01-01", "2024-02-01")
    assert out is dl.result
    assert dl.calls[-1] == ("TCS.BO", "2024-01-01", "2024-02-01", False)
    f.fetch_nse_data("INFY", "a", "b")
    assert dl.calls[-1][0] == "INFY.BO"


@pytest.mark.parametrize("cls,meth,arg", [
    (df_.NSEDataFetcher, "fetch_nse_data", "TCS.NS"),
    (df_.BSEDataFetcher, "fetch_bse_data", "AFTL.BO"),
    (df_.USStockFetcher, "fetch_us_data", "AAPL"),
])
def test_fetch_wrappers_return_none_and_print_on_error(monkeypatch, capsys, cls, meth, arg):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(df_.yf, "download", boom)
    assert getattr(cls(), meth)(arg, "a", "b") is None
    assert "Error fetching" in capsys.readouterr().out


def test_bse_and_us_pass_symbol_unchanged(dl):
    df_.BSEDataFetcher().fetch_bse_data("AFTL.BO", "s", "e")
    df_.USStockFetcher().fetch_us_data("AAPL", "s", "e")
    assert [c[0] for c in dl.calls] == ["AFTL.BO", "AAPL"]


# ------------------------------- fundamentals -------------------------------

class FakeTicker:
    def __init__(self, info):
        self.info = info


def test_fundamentals_maps_fields_and_defaults(monkeypatch):
    info = {"marketCap": 5, "trailingPE": 12.5, "returnOnEquity": 0.2, "profitMargins": 0.1}
    monkeypatch.setattr(df_.yf, "Ticker", lambda s: FakeTicker(info))
    out = df_.FundamentalDataFetcher().fetch_fundamentals("X")
    assert out["symbol"] == "X" and out["market_cap"] == 5 and out["pe_ratio"] == 12.5
    assert out["roe"] == 0.2 and out["profit_margin"] == 0.1
    assert out["peg_ratio"] == 0 and out["free_cash_flow"] == 0 and out["roa"] == 0   # defaults
    assert len(out) == 13


def test_fundamentals_error_returns_none(monkeypatch, capsys):
    def boom(s):
        raise ValueError("x")
    monkeypatch.setattr(df_.yf, "Ticker", boom)
    assert df_.FundamentalDataFetcher().fetch_fundamentals("X") is None
    assert "Error fetching fundamentals for X" in capsys.readouterr().out


# ------------------------------- volume -------------------------------

def test_volume_data_shape(dl):
    v = df_.VolumeDataFetcher().fetch_volume_data("X", "s", "e")
    assert v["symbol"] == "X"
    assert list(v["dates"]) == ["2024-01-01", "2024-01-02", "2024-01-03"]
    assert list(v["volume"]) == [100, 110, 120]
    assert list(v["close"]) == [1.5, 2.5, 3.5]
    assert set(v) == {"symbol", "open", "high", "low", "close", "volume", "dates"}


def test_volume_data_empty_or_none_and_error(dl, monkeypatch, capsys):
    dl.result = ohlcv(0)
    assert df_.VolumeDataFetcher().fetch_volume_data("X", "s", "e") is None
    dl.result = None
    assert df_.VolumeDataFetcher().fetch_volume_data("X", "s", "e") is None
    dl.result = pd.DataFrame({"Open": [1]})                    # missing columns -> KeyError caught
    assert df_.VolumeDataFetcher().fetch_volume_data("X", "s", "e") is None
    assert "Error fetching volume data" in capsys.readouterr().out


# ------------------------------- historical + cache -------------------------------

def test_historical_prices_dataframe_and_cache(dl):
    h = df_.HistoricalPriceFetcher()
    p = h.fetch_historical_prices("X", "s", "e")
    assert list(p.columns) == ["date", "open", "high", "low", "close", "volume", "adjusted_close"]
    assert len(p) == 3 and p["adjusted_close"].tolist() == [1.4, 2.4, 3.4]
    again = h.fetch_historical_prices("X", "s", "e")
    assert again is p and len(dl.calls) == 1                 # served from cache
    h.fetch_historical_prices("X", "s", "e2")                # different key -> new call
    h.fetch_historical_prices("Y", "s", "e")
    assert len(dl.calls) == 3
    assert set(h.cache) == {"X_s_e", "X_s_e2", "Y_s_e"}


def test_historical_prices_none_for_empty_and_not_cached(dl):
    h = df_.HistoricalPriceFetcher()
    dl.result = ohlcv(0)
    assert h.fetch_historical_prices("X", "s", "e") is None
    dl.result = None
    assert h.fetch_historical_prices("X", "s", "e") is None
    assert h.cache == {} and len(dl.calls) == 2              # misses are retried, never cached


def test_historical_prices_without_adj_close_returns_none(dl, capsys):
    """yfinance >= 0.2.51 drops 'Adj Close' (auto_adjust=True default): fetch silently yields None."""
    dl.result = ohlcv(adj=False)
    assert df_.HistoricalPriceFetcher().fetch_historical_prices("X", "s", "e") is None
    assert "Error fetching historical prices for X" in capsys.readouterr().out


# ------------------------------- MarketDataFetcher -------------------------------

def test_get_all_symbols_by_market():
    m = df_.MarketDataFetcher()
    s = m.get_all_symbols()
    assert set(s) == {"NSE", "BSE", "USA"}
    assert set(m.get_all_symbols(["India"])) == {"NSE", "BSE"}
    assert set(m.get_all_symbols(["USA"])) == {"USA"}
    assert m.get_all_symbols(["Mars"]) == {}


def test_fetch_stock_data_combines_three_sources(monkeypatch):
    m = df_.MarketDataFetcher()
    monkeypatch.setattr(m.historical, "fetch_historical_prices", lambda s, a, b: ("P", s, a, b))
    monkeypatch.setattr(m.volume, "fetch_volume_data", lambda s, a, b: ("V", s, a, b))
    monkeypatch.setattr(m.fundamentals, "fetch_fundamentals", lambda s: ("F", s))
    assert m.fetch_stock_data("X", "a", "b") == {
        "symbol": "X", "prices": ("P", "X", "a", "b"), "volumes": ("V", "X", "a", "b"),
        "fundamentals": ("F", "X")}


def test_fetch_market_data_keeps_only_symbols_with_prices(monkeypatch, capsys):
    m = df_.MarketDataFetcher()
    monkeypatch.setattr(m, "get_all_symbols", lambda mk: {"USA": ["A", "B", "C"], "BSE": ["D"]})
    sleeps = []
    monkeypatch.setattr(df_.time, "sleep", sleeps.append)

    def fsd(sym, a, b):
        prices = {"A": pd.DataFrame({"close": [1]}), "B": None, "C": pd.DataFrame({"close": []}),
                  "D": pd.DataFrame({"close": [2]})}[sym]
        return {"symbol": sym, "prices": prices, "volumes": None, "fundamentals": None}

    monkeypatch.setattr(m, "fetch_stock_data", fsd)
    out = m.fetch_market_data("s", "e")
    assert [d["symbol"] for d in out["USA"]] == ["A"]
    assert [d["symbol"] for d in out["BSE"]] == ["D"]
    assert sleeps == [0.1] * 4
    text = capsys.readouterr().out
    assert "[1/4] A... ✓" in text and "[2/4] B... ✗ (no data)" in text
    assert "[4/4] D" in text


def test_get_current_price(monkeypatch):
    m = df_.MarketDataFetcher()
    monkeypatch.setattr(df_.yf, "Ticker", lambda s: FakeTicker({"currentPrice": 42.5}))
    assert m.get_current_price("X") == 42.5
    monkeypatch.setattr(df_.yf, "Ticker", lambda s: FakeTicker({}))
    assert m.get_current_price("X") is None

    def boom(s):
        raise RuntimeError
    monkeypatch.setattr(df_.yf, "Ticker", boom)
    assert m.get_current_price("X") is None


# ------------------------------- validate_data / export -------------------------------

def sd(n=252, nan=False, vol=True, prices=True):
    p = pd.DataFrame({"close": np.arange(n, dtype=float) + 1}) if prices else None
    if nan and p is not None:
        p.loc[0, "close"] = np.nan
    return {"prices": p, "volumes": {"volume": np.arange(5)} if vol else None}


def test_validate_data_branches():
    assert df_.validate_data(sd(prices=False)) == (False, "No price data")
    assert df_.validate_data(sd(0)) == (False, "No price data")
    assert df_.validate_data(sd(251)) == (False, "Insufficient data (251 days)")
    assert df_.validate_data(sd(252, vol=False)) == (False, "No volume data")
    s = sd(252)
    s["volumes"] = {"volume": np.array([])}
    assert df_.validate_data(s) == (False, "No volume data")
    assert df_.validate_data(sd(252, nan=True)) == (False, "Contains NaN values")
    assert df_.validate_data(sd(252)) == (True, "Valid")


def test_export_market_data_to_csv(tmp_path, capsys):
    out = tmp_path / "md"
    data = {"NSE": [{"symbol": "TCS.NS", "prices": pd.DataFrame({"close": [1, 2]})},
                    {"symbol": "NOPRICE.NS", "prices": None}], "USA": []}
    df_.export_market_data_to_csv(data, str(out))
    files = sorted(p.name for p in out.iterdir())
    assert files == ["NSE_TCS_NS_prices.csv"]
    assert pd.read_csv(out / files[0])["close"].tolist() == [1, 2]
    assert "Exported:" in capsys.readouterr().out
