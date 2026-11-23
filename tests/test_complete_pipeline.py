"""complete_backtest_pipeline.py wired to fake fetcher/screener/yfinance."""
import json

import numpy as np
import pandas as pd
import pytest

import complete_backtest_pipeline as cp

HITS = [{"symbol": "A", "price": 10.0, "piotroski": {"score": 8}, "cmf": {"cmf_20": 0.2}},
        {"symbol": "B", "price": 20.0, "piotroski": {"score": 7}, "cmf": {"cmf_20": 0.1}}]


def frame(prices):
    return pd.DataFrame({"Adj Close": prices}, index=pd.bdate_range("2023-01-16", periods=len(prices)))


@pytest.fixture
def pipe(monkeypatch):
    p = cp.CompleteBacktestPipeline()
    calls = {}

    def fetch(start_date, end_date, markets):
        calls["fetch"] = (start_date, end_date, markets)
        return {"USA": []}

    monkeypatch.setattr(p.fetcher, "fetch_market_data", fetch)
    monkeypatch.setattr(p.screener, "screen_market", lambda md: HITS)
    p.calls = calls
    return p


def test_initial_state():
    p = cp.CompleteBacktestPipeline()
    assert p.results == {"config": {}, "market_data": {}, "triple_hits": [], "portfolio": None,
                         "backtest_results": None, "metrics": None}


def test_pipeline_success(pipe, monkeypatch, capsys):
    frames = {"A": frame(list(10 + np.arange(30) * 0.1)), "B": frame(list(20 + np.arange(30) * 0.2))}
    monkeypatch.setattr(cp.__dict__["HistoricalBacktester"].__init__.__globals__["yf"], "download",
                        lambda s, start=None, end=None, progress=None: frames[s])
    ok = pipe.run_pipeline("2023-01-15", "2023-03-15", ["USA"])
    assert ok is True
    assert pipe.calls["fetch"] == ("2021-08-29", "2023-01-15", ["USA"])      # 504 days of lookback
    r = pipe.results
    assert r["config"] == {"portfolio_date": "2023-01-15", "backtest_end_date": "2023-03-15", "markets": ["USA"]}
    assert r["triple_hits"] == HITS and r["portfolio"]["strategy"] == "quality_weighted"
    assert len(r["backtest_results"]) == 30 and r["metrics"]["days"] == 30
    assert r["metrics"]["total_return_pct"] > 0


def test_pipeline_no_hits_and_no_prices(pipe, monkeypatch):
    monkeypatch.setattr(pipe.screener, "screen_market", lambda md: [])
    assert pipe.run_pipeline("2023-01-15", "2023-03-15") is False
    assert pipe.results["portfolio"] is None
    monkeypatch.setattr(pipe.screener, "screen_market", lambda md: HITS)
    yf = cp.HistoricalBacktester.fetch_forward_prices.__globals__["yf"]
    monkeypatch.setattr(yf, "download", lambda *a, **k: pd.DataFrame())
    assert pipe.run_pipeline("2023-01-15", "2023-03-15") is False
    assert pipe.results["portfolio"] is not None and pipe.results["metrics"] is None


def test_default_end_date_is_today(pipe, monkeypatch):
    from datetime import datetime
    monkeypatch.setattr(pipe.screener, "screen_market", lambda md: [])
    pipe.run_pipeline("2023-01-15")
    assert pipe.results["config"]["backtest_end_date"] == datetime.now().strftime("%Y-%m-%d")
    assert pipe.results["config"]["markets"] == ["USA"]


def test_export_results(pipe, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    frames = {"A": frame(list(10 + np.arange(30) * 0.1)), "B": frame(list(20 + np.arange(30) * 0.2))}
    yf = cp.HistoricalBacktester.fetch_forward_prices.__globals__["yf"]
    monkeypatch.setattr(yf, "download", lambda s, start=None, end=None, progress=None: frames[s])
    pipe.run_pipeline("2023-01-15", "2023-03-15")
    pipe.export_results()
    comp = pd.read_csv(tmp_path / "portfolio_composition.csv")
    assert list(comp.columns) == ["symbol", "shares", "entry_price", "weight", "piotroski", "cmf"]
    assert len(pd.read_csv(tmp_path / "backtest_daily_values.csv")) == 30
    s = json.loads((tmp_path / "backtest_summary.json").read_text())
    assert s["triple_hits_count"] == 2 and s["config"]["portfolio_date"] == "2023-01-15"
    assert s["metrics"]["days"] == 30


def test_export_with_nothing_run_writes_only_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cp.CompleteBacktestPipeline().export_results()
    assert [p.name for p in tmp_path.iterdir()] == ["backtest_summary.json"]
    assert json.loads((tmp_path / "backtest_summary.json").read_text())["triple_hits_count"] == 0


def test_main(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls = []

    def fake_run(self, portfolio_date, backtest_end_date=None, markets=None):
        calls.append((portfolio_date, backtest_end_date, markets))
        return False

    monkeypatch.setattr(cp.CompleteBacktestPipeline, "run_pipeline", fake_run)
    p = cp.main()
    assert calls == [("2023-01-15", "2024-01-15", ["USA"])]
    assert not (tmp_path / "backtest_summary.json").exists() and isinstance(p, cp.CompleteBacktestPipeline)


def test_main_exports_on_success(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cp.CompleteBacktestPipeline, "run_pipeline", lambda self, **k: True)
    cp.main()
    assert (tmp_path / "backtest_summary.json").exists()


def test_print_results_without_metrics(capsys):
    cp.CompleteBacktestPipeline().print_results()
    assert "No results available" in capsys.readouterr().out


def test_print_results_truncates_to_ten_positions(capsys):
    p = cp.CompleteBacktestPipeline()
    stocks = [{"symbol": f"S{i:02d}", "weight": 0.01 * (i + 1), "piotroski": 8, "cmf": 0.1} for i in range(12)]
    p.results["portfolio"] = {"stocks": stocks}
    p.results["config"] = {"portfolio_date": "d1", "backtest_end_date": "d2"}
    p.results["metrics"] = {"days": 100, "starting_value": 1e6, "final_value": 1.1e6, "total_return_pct": 10.0,
                            "annual_return_pct": 25.0, "volatility_pct": 12.0, "max_drawdown_pct": -5.0,
                            "sharpe_ratio": 1.5}
    p.print_results()
    out = capsys.readouterr().out
    assert "... and 2 more stocks" in out and "S11" in out and "S01" not in out   # sorted by weight, top 10
    assert "Absolute Gain:" in out and "100,000" in out
