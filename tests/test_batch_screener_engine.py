"""batch_screener.py: filter boundaries and the BatchScreener pipeline (synthetic stock dicts)."""
import numpy as np
import pandas as pd
import pytest

import batch_screener as bs
from batch_screener import BatchScreener, StockFilters as F

GOOD_F = dict(net_income=1, operating_cash_flow=1, roe=0.1, debt_to_equity=0.5, current_ratio=2,
              revenue=10, profit_margin=0.1, roa=0.05, free_cash_flow=1, pe_ratio=20,
              market_cap=1e9)


def prices(n=260, last=100.0, high=100.0, start=50.0):
    close = np.linspace(start, high, n)
    close[-2] = high
    close[-1] = last
    return pd.DataFrame({"close": close, "date": pd.date_range("2023-01-01", periods=n)})


def vols(n=260, last=2.0):
    v = np.ones(n)
    v[-1] = last
    return {"volume": v, "close": np.full(n, 10.0), "high": np.full(n, 10.0),
            "low": np.full(n, 8.0), "open": np.full(n, 9.0)}


# ------------------------------- darvas_box -------------------------------

def test_darvas_252_bar_minimum():
    assert F.darvas_box(prices(251), vols(251)) is None
    assert F.darvas_box(prices(252), vols(252)) is not None


def test_darvas_pct_off_high_boundary_is_ten_percent():
    r = F.darvas_box(prices(last=90.0), vols())
    assert r["pct_off_high"] == pytest.approx(10.0) and r["passed"]
    assert r["score"] == pytest.approx(0.0) and r["52w_high"] == 100.0
    r = F.darvas_box(prices(last=89.0), vols())
    assert not r["passed"] and r["score"] == 0


def test_darvas_volume_multiple_boundary():
    # avg20 includes today's bar: (19 + v)/20 ; need v/avg >= 1.5  ->  v = 1.5*19/18.5
    v = 1.5 * 19 / 18.5
    assert F.darvas_box(prices(), vols(last=v + 1e-9))["passed"]
    assert not F.darvas_box(prices(), vols(last=v - 0.05))["passed"]


def test_darvas_requires_price_above_200_day_average():
    close = np.concatenate([np.full(100, 200.0), np.full(160, 100.0)])    # still within 10% of... no
    close[:] = np.concatenate([np.full(200, 100.0), np.full(60, 50.0)])
    close[0] = 1000.0                                            # 52w high far away
    r = F.darvas_box(pd.DataFrame({"close": close}), vols())
    assert r["above_200ma"] is np.False_ or r["above_200ma"] is False
    assert not r["passed"]


def test_darvas_score_scales_with_proximity():
    r = F.darvas_box(prices(last=96.0), vols())
    assert r["passed"] and r["score"] == pytest.approx(10 - 4.0)


def test_darvas_zero_average_volume_and_zero_high():
    v = vols()
    v["volume"] = np.zeros(260)
    r = F.darvas_box(prices(), v)
    assert r["vol_mult"] == 0 and not r["passed"]
    z = pd.DataFrame({"close": np.zeros(260)})
    assert F.darvas_box(z, vols())["pct_off_high"] == 100


# ------------------------------- piotroski / coffee can / cmf -------------------------------

def test_piotroski_threshold_and_flags():
    f = dict(GOOD_F)
    assert F.piotroski_score(f)["passed"]
    s7 = dict(f, roa=0, free_cash_flow=0)
    r = F.piotroski_score(s7)
    assert r["score"] == 7 and r["passed"] and r["efficiency"]
    r = F.piotroski_score(dict(s7, profit_margin=0.05))      # margin must be strictly > 0.05
    assert r["score"] == 6 and not r["passed"] and not r["efficiency"]
    assert r["leverage_ok"] and r["profitability"]
    r = F.piotroski_score({"net_income": 1})
    assert r["score"] == 1 and r["profitability"] and not r["leverage_ok"]
    r = F.piotroski_score({"x": 1})
    assert r["score"] == 0 and not r["profitability"]


def test_piotroski_individual_thresholds():
    base = dict(GOOD_F)
    for key, bad in [("net_income", 0), ("operating_cash_flow", 0), ("roe", 0), ("debt_to_equity", 1.0),
                     ("current_ratio", 1.5), ("revenue", 0), ("profit_margin", 0.05), ("roa", 0),
                     ("free_cash_flow", 0)]:
        assert F.piotroski_score(dict(base, **{key: bad}))["score"] == 8, key


def test_coffee_can_each_reason_and_boundaries():
    ok = dict(revenue=1, net_income=1, free_cash_flow=1, pe_ratio=20, debt_to_equity=2.0)
    r = F.coffee_can_check(ok)
    assert r["passed"] and r["reasons"] == [] and r["reasonable_valuation"]
    assert r["profitability"] and r["cash_generation"]
    assert F.coffee_can_check(dict(ok, debt_to_equity=2.01))["reasons"] == ["High debt"]
    assert F.coffee_can_check(dict(ok, pe_ratio=50))["passed"]
    assert F.coffee_can_check(dict(ok, pe_ratio=50.1))["reasons"] == ["Valuation concern"]
    assert F.coffee_can_check(dict(ok, pe_ratio=-3))["reasons"] == ["Valuation concern"]
    r = F.coffee_can_check(dict(revenue=0, net_income=0, free_cash_flow=0))
    assert r["reasons"] == ["No revenue", "Not profitable", "Negative FCF"] and not r["passed"]
    assert F.coffee_can_check(None) is None and F.coffee_can_check({}) is None


def test_cmf_status_bands_and_zero_volume():
    def vd(mult):       # one bar with money-flow multiplier `mult` for volume 100
        hi, lo = 10.0, 0.0
        close = lo + (mult + 1) / 2 * (hi - lo)
        return {"close": [close], "high": [hi], "low": [lo], "volume": [100.0]}

    assert F.chaikin_money_flow(vd(0.26), 1)["status"] == "STRONG_ACCUMULATION"
    assert F.chaikin_money_flow(vd(0.26), 1)["confidence"] == 0.95
    r = F.chaikin_money_flow(vd(0.25), 1)
    assert r["status"] == "ACCUMULATION" and r["confidence"] == 0.75 and r["passed"]
    r = F.chaikin_money_flow(vd(0.05), 1)
    assert r["status"] == "NEUTRAL" and r["confidence"] == 0.5 and not r["passed"]
    assert not F.chaikin_money_flow(vd(-0.5), 1)["passed"]
    assert F.chaikin_money_flow({"close": [1.0], "high": [2.0], "low": [0.0], "volume": [0.0]}, 1) is None
    assert F.chaikin_money_flow(None) is None


def test_cmf_uses_only_last_period_bars():
    vd = {"close": [0.0, 10.0], "high": [10.0, 10.0], "low": [0.0, 0.0], "volume": [1000.0, 10.0]}
    assert F.chaikin_money_flow(vd, 1)["cmf_20"] == pytest.approx(1.0)
    assert F.chaikin_money_flow(vd, 2)["cmf_20"] == pytest.approx((-1000 + 10) / 1010)


# ------------------------------- BatchScreener -------------------------------

def stock(symbol="AAA", p=None, v=None, f=None, n=260):
    p = prices(n) if p is None else p
    return {"symbol": symbol, "prices": p, "volumes": vols(n) if v is None else v,
            "fundamentals": dict(GOOD_F) if f is None else f}


def bullish_volumes(n=260):
    v = vols(n)
    v["close"] = np.full(n, 9.5)
    v["high"] = np.full(n, 10.0)
    v["low"] = np.full(n, 8.0)
    return v


@pytest.fixture
def patched(monkeypatch):
    """Work around the missing BatchScreener.chaikin_money_flow so later stages can be exercised."""
    monkeypatch.setattr(BatchScreener, "chaikin_money_flow", staticmethod(F.chaikin_money_flow), raising=False)


def test_screen_stock_rejects_invalid_data():
    s = BatchScreener()
    assert s.screen_stock(stock(n=100)) is None
    assert s.screen_stock(dict(stock(), prices=None)) is None


def test_screen_stock_stage_gates(patched):
    s = BatchScreener()
    assert s.screen_stock(stock(p=prices(last=50.0))) is None                      # stage 1 fails
    assert s.screen_stock(stock(f={"net_income": 1})) is None                      # stage 2 fails
    assert s.screen_stock(stock(f=dict(GOOD_F, pe_ratio=80))) is None              # stage 3 fails
    bear = vols()
    bear["close"] = np.full(260, 8.5)
    bear["close"][:] = 8.1
    assert s.screen_stock(stock(v=bear)) is None                                   # stage 4 fails


def test_screen_stock_triple_hit(patched):
    r = BatchScreener().screen_stock(stock(v=bullish_volumes()))
    assert r["symbol"] == "AAA" and r["price"] == 100.0
    assert r["date_identified"] == pd.Timestamp("2023-01-01") + pd.Timedelta(days=259)
    assert r["market_cap"] == 1e9 and r["pe_ratio"] == 20
    assert r["darvas"]["passed"] and r["piotroski"]["score"] == 9 and r["cmf"]["passed"]


def test_screen_stock_missing_stage_one_with_empty_fundamentals_dict(patched):
    # a falsy fundamentals dict reaches stage 2 and is rejected there (piotroski_score -> None)
    assert BatchScreener().screen_stock(stock(f={})) is None


@pytest.mark.xfail(strict=True, raises=AttributeError,
                   reason="BatchScreener.screen_stock calls self.chaikin_money_flow(...) but the method "
                          "lives on StockFilters, so any stock that passes stages 1-3 crashes with "
                          "AttributeError instead of reaching stage 4 (batch_screener.py:~189)")
def test_screen_stock_reaches_stage_four_without_patching():
    assert BatchScreener().screen_stock(stock(v=bullish_volumes())) is not None


def test_screen_market_counts_stages_and_returns_hits(patched, capsys):
    market = {"USA": [stock("A", v=bullish_volumes()), stock("B", p=prices(last=50.0)),
                      stock("C", f={"net_income": 1}), stock("D", f=dict(GOOD_F, pe_ratio=80))],
              "BSE": [dict(stock("E"), prices=None)]}
    s = BatchScreener()
    hits = s.screen_market(market)
    assert [h["symbol"] for h in hits] == ["A"] and s.results == hits
    out = capsys.readouterr().out
    assert "Total processed: 5" in out
    assert "Stage 1 (Darvas): 3 (60.0%)" in out        # A, C, D pass the Darvas stage; B and E do not
    assert "Stage 2 (Piotroski): 2 (40.0%)" in out
    assert "Stage 3 (Coffee Can): 1 (20.0%)" in out
    assert "Stage 4 (CMF): 1 (20.0%)" in out
    assert "TRIPLE HITS FOUND: 1" in out and "Screening USA (4 stocks)" in out


def test_screen_market_progress_line_every_ten(patched, capsys):
    market = {"USA": [stock(f"S{i}", p=prices(last=50.0)) for i in range(10)]}
    BatchScreener().screen_market(market)
    assert "[10/10] Processed: 0/0/0/0" in capsys.readouterr().out


def test_screen_market_resets_results(patched):
    s = BatchScreener()
    s.results = ["stale"]
    assert s.screen_market({"USA": [stock("A", v=bullish_volumes())]})[0]["symbol"] == "A"
    s.screen_market({"USA": [stock("B", p=prices(last=50.0))]})
    assert s.results == []


def test_results_dataframe(patched):
    s = BatchScreener()
    assert s.get_results_dataframe() is None
    s.screen_market({"USA": [stock("A", v=bullish_volumes())]})
    df = s.get_results_dataframe()
    assert list(df.columns) == ["Symbol", "Price", "Date", "Piotroski", "CMF", "CMF_Status", "P/E", "Market_Cap"]
    assert df.iloc[0]["Symbol"] == "A" and df.iloc[0]["Piotroski"] == 9 and df.iloc[0]["P/E"] == 20


def test_main_exports_csv(patched, tmp_path, monkeypatch, capsys):
    hits_market = {"USA": [stock("A", v=bullish_volumes())]}

    class FakeFetcher:
        def fetch_market_data(self, start_date, end_date, markets):
            assert markets == ["USA"]
            return hits_market

    monkeypatch.setattr(bs, "MarketDataFetcher", FakeFetcher)
    monkeypatch.chdir(tmp_path)
    hits = bs.main()
    assert len(hits) == 1
    assert (tmp_path / "triple_hits_results.csv").exists()
    out = capsys.readouterr().out
    assert "Top 10 Triple Hits" in out and "Results exported to triple_hits_results.csv" in out


def test_main_without_hits_writes_nothing(patched, tmp_path, monkeypatch):
    class FakeFetcher:
        def fetch_market_data(self, start_date, end_date, markets):
            return {"USA": [stock("A", p=prices(last=50.0))]}

    monkeypatch.setattr(bs, "MarketDataFetcher", FakeFetcher)
    monkeypatch.chdir(tmp_path)
    assert bs.main() == []
    assert not (tmp_path / "triple_hits_results.csv").exists()


@pytest.mark.xfail(strict=True, raises=ZeroDivisionError,
                   reason="screen_market divides by total_stocks for its percentage summary, so an empty "
                          "market (e.g. every fetch failed) crashes instead of reporting 0 hits "
                          "(batch_screener.py:~286)")
def test_screen_market_with_no_stocks_returns_empty():
    assert BatchScreener().screen_market({"USA": []}) == []
