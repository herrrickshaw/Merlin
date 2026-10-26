"""Regressions found by the 2026-10-25 static sweep (ruff F821 / F841)."""
import historical_portfolio_backtester as hpb
import screener_runner as sr


def _bt(values, start=100.0):
    bt = hpb.HistoricalBacktester({"total_value": start, "stocks": []})
    bt.daily_values = [{"date": f"d{i}", "portfolio_value": v, "return_pct": (v - start) / start * 100}
                       for i, v in enumerate(values)]
    return bt


def test_backtest_summary_reports_sharpe_from_metrics():
    """get_backtest_summary referenced a bare `sharpe` name -> NameError on every run with data."""
    bt = _bt([100.0, 110.0, 105.0, 120.0])
    summary = bt.get_backtest_summary()
    sharpe = bt.calculate_metrics()["sharpe_ratio"]
    assert f"Sharpe Ratio: {sharpe:.2f}" in summary


def _canned_results():
    return [
        sr.Result("AAA", "darvas", True, 1.0),
        sr.Result("AAA", "piotroski", True, 7.0),
        sr.Result("BBB", "piotroski", True, 8.0),
        sr.Result("BBB", "coffee_can", True, 2.0),
    ]


def test_strategy_flag_restricts_output(monkeypatch, capsys, tmp_path):
    """`--strategy NAME` was parsed and then ignored: every strategy was still printed."""
    monkeypatch.setattr(sr, "load_csv_to_stocks", lambda _p: [])
    monkeypatch.setattr(sr, "screen_market", lambda _s: _canned_results())
    monkeypatch.setattr(sr.sys, "argv", ["screener_runner.py", str(tmp_path / "x.csv"), "--strategy", "piotroski"])
    sr.main()
    out = capsys.readouterr().out
    assert "PIOTROSKI Results" in out
    assert "DARVAS Results" not in out
    assert "COFFEE_CAN Results" not in out


def test_without_strategy_flag_all_strategies_print(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sr, "load_csv_to_stocks", lambda _p: [])
    monkeypatch.setattr(sr, "screen_market", lambda _s: _canned_results())
    monkeypatch.setattr(sr.sys, "argv", ["screener_runner.py", str(tmp_path / "x.csv"), "--top", "1"])
    sr.main()
    out = capsys.readouterr().out
    assert "Top 1 PIOTROSKI Results" in out and "DARVAS Results" in out and "COFFEE_CAN Results" in out
