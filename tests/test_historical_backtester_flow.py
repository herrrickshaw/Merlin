"""historical_portfolio_backtester.py: weights, portfolio text, forward-price replay and main() with fakes."""
import numpy as np
import pandas as pd
import pytest

import historical_portfolio_backtester as hpb

HITS = [{"symbol": "A", "price": 10.0, "piotroski": {"score": 8}, "cmf": {"cmf_20": 0.2}},
        {"symbol": "B", "price": 20.0, "piotroski": {"score": 7}, "cmf": {"cmf_20": 0.1}}]


def frame(prices, start="2023-01-16"):
    idx = pd.bdate_range(start, periods=len(prices))
    return pd.DataFrame({"Adj Close": prices, "Close": prices}, index=idx)


def test_calculate_weights_strategies():
    pc = hpb.PortfolioConstructor(HITS)
    assert pc.calculate_weights("equal_weight") == {"A": 0.5, "B": 0.5}
    assert pc.calculate_weights("risk_parity") == {"A": 0.5, "B": 0.5}
    qa, qb = 8 + 0.6, 7 + 0.3
    w = pc.calculate_weights()                                  # default quality_weighted
    assert w == pytest.approx({"A": qa / (qa + qb), "B": qb / (qa + qb)})
    assert sum(w.values()) == pytest.approx(1.0)


def test_unknown_strategy_raises():
    with pytest.raises(UnboundLocalError):
        hpb.PortfolioConstructor(HITS).calculate_weights("nonsense")


def test_build_portfolio_positions():
    pc = hpb.PortfolioConstructor(HITS)
    p = pc.build_portfolio("equal_weight", date="2023-01-15")
    assert p["date_created"] == "2023-01-15" and p["strategy"] == "equal_weight" and p["total_value"] == 1_000_000
    a, b = p["stocks"]
    assert a["shares"] == pytest.approx(500_000 / 10.0) and b["shares"] == pytest.approx(500_000 / 20.0)
    assert a["position_value"] == 500_000 and a["piotroski"] == 8 and a["cmf"] == 0.2
    assert pc.portfolio is p
    default_date = pc.build_portfolio()["date_created"]
    assert len(default_date) == 10 and default_date[4] == "-"


def test_portfolio_to_string():
    pc = hpb.PortfolioConstructor(HITS)
    assert pc.portfolio_to_string() == "No portfolio built"
    pc.build_portfolio("equal_weight", date="2023-01-15")
    s = pc.portfolio_to_string()
    assert s.startswith("Portfolio (EQUAL_WEIGHT)\nDate: 2023-01-15\nTotal Capital: $1,000,000\nStocks: 2\n")
    assert "50000" in s and "$10.00" in s and "50.0 " in s


def _bt():
    pc = hpb.PortfolioConstructor(HITS)
    return hpb.HistoricalBacktester(pc.build_portfolio("equal_weight", date="2023-01-15"))


def test_fetch_forward_prices(monkeypatch, capsys):
    def dl(symbol, start=None, end=None, progress=None):
        if symbol == "A":
            return frame([10.0, 11.0])
        if symbol == "B":
            return pd.DataFrame()
        raise RuntimeError("x")

    monkeypatch.setattr(hpb.yf, "download", dl)
    bt = _bt()
    bt.portfolio["stocks"].append({"symbol": "C", "shares": 1, "entry_price": 1, "position_value": 1,
                                   "weight": 0, "piotroski": 1, "cmf": 0})
    out = bt.fetch_forward_prices("2023-01-15", "2023-03-01")
    assert list(out) == ["A"]
    text = capsys.readouterr().out
    assert "Fetching A... ✓" in text and "B... ✗ (no data)" in text and "C... ✗ (x)" in text


def test_daily_returns_values_and_start_filter():
    bt = _bt()
    fp = {"A": frame([10.0, 11.0, 12.0], start="2023-01-13"), "B": frame([20.0, 20.0, 22.0], start="2023-01-13")}
    daily = bt.calculate_daily_returns(fp)
    # 2023-01-13 is before the portfolio date (01-15) and is skipped
    assert [d["date"] for d in daily] == ["2023-01-16", "2023-01-17"]
    assert daily[0]["portfolio_value"] == pytest.approx(11.0 * 50_000 + 20.0 * 25_000)
    assert daily[0]["return_pct"] == pytest.approx((daily[0]["portfolio_value"] - 1e6) / 1e6 * 100)
    assert bt.daily_values == daily


def test_daily_returns_nearest_date_and_missing_symbols():
    bt = _bt()
    a = frame([10.0, 12.0], start="2023-01-16")
    b = frame([20.0], start="2023-01-17")                 # B has no row on 01-16 -> nearest (01-17)
    daily = bt.calculate_daily_returns({"A": a, "B": b})
    assert daily[0]["portfolio_value"] == pytest.approx(10.0 * 50_000 + 20.0 * 25_000)
    only_a = bt.calculate_daily_returns({"A": a})
    assert only_a[0]["portfolio_value"] == pytest.approx(10.0 * 50_000)
    assert bt.calculate_daily_returns({}) == []


def test_daily_returns_swallows_bad_frames():
    bt = _bt()
    bad = pd.DataFrame({"Close": [1.0]}, index=pd.bdate_range("2023-01-16", periods=1))   # no 'Adj Close'
    assert bt.calculate_daily_returns({"A": bad}) == []


def test_summary_when_data_missing():
    assert _bt().get_backtest_summary() == "Insufficient data for backtest"


@pytest.mark.xfail(strict=True, raises=NameError,
                   reason="get_backtest_summary formats an undefined name `sharpe` instead of "
                          "metrics['sharpe_ratio'], so the text summary always raises NameError "
                          "(historical_portfolio_backtester.py:~254)")
def test_summary_text():
    bt = _bt()
    vals = [1_000_000.0 * (1.001 ** i) for i in range(30)]
    bt.daily_values = [{"date": f"d{i}", "portfolio_value": v, "return_pct": (v - 1e6) / 1e4}
                       for i, v in enumerate(vals)]
    s = bt.get_backtest_summary()
    assert "PORTFOLIO BACKTEST RESULTS" in s and "Sharpe Ratio:" in s


def test_main_early_exits(monkeypatch, tmp_path, capsys):
    class F:
        def fetch_market_data(self, **kw):
            return {"USA": []}

    monkeypatch.setattr(hpb, "MarketDataFetcher", F)
    monkeypatch.setattr(hpb.BatchScreener, "screen_market", lambda self, md: [])
    assert hpb.main() is None
    assert "No triple hits found" in capsys.readouterr().out
    monkeypatch.setattr(hpb.BatchScreener, "screen_market", lambda self, md: HITS)
    monkeypatch.setattr(hpb.yf, "download", lambda *a, **k: pd.DataFrame())
    assert hpb.main() is None
    assert "No forward price data available" in capsys.readouterr().out


def test_main_full_flow(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    class F:
        def fetch_market_data(self, **kw):
            assert kw["markets"] == ["USA"] and kw["end_date"] == "2023-01-15"
            return {"USA": []}

    monkeypatch.setattr(hpb, "MarketDataFetcher", F)
    monkeypatch.setattr(hpb.BatchScreener, "screen_market", lambda self, md: HITS)
    frames = {"A": frame(list(10.0 + np.arange(40) * 0.1)), "B": frame(list(20.0 + np.arange(40) * 0.05))}
    monkeypatch.setattr(hpb.yf, "download", lambda s, start=None, end=None, progress=None: frames[s])
    portfolio, daily, metrics = hpb.main()
    assert portfolio["strategy"] == "quality_weighted" and portfolio["date_created"] == "2023-01-15"
    assert len(daily) == 40 and metrics["days"] == 40 and metrics["total_return_pct"] > 0
    assert (tmp_path / "portfolio_daily_values.csv").exists()
    assert "Total Return:" in capsys.readouterr().out
