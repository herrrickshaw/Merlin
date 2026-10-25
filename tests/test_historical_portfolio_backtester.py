"""Metrics in historical_portfolio_backtester on hand-built value series (no price download)."""
import numpy as np
import pytest

import historical_portfolio_backtester as hpb


def _bt(values, start=1_000_000.0):
    bt = hpb.HistoricalBacktester({"total_value": start, "stocks": []})
    bt.daily_values = [{"date": f"d{i}", "portfolio_value": v, "return_pct": (v - start) / start * 100}
                       for i, v in enumerate(values)]
    return bt


def test_annual_return_of_one_trading_year_equals_total_return():
    # 253 trading-day values (252 daily steps) compounding to +10%: one year of trading days.
    g = 1.10 ** (1 / 252)
    vals = [1_000_000 * g ** i for i in range(253)]
    m = _bt(vals).calculate_metrics()
    assert m["total_return_pct"] == pytest.approx(10.0, abs=1e-6)
    assert m["annual_return_pct"] == pytest.approx(10.0, abs=0.1)


def test_sharpe_is_zero_when_mean_daily_return_equals_risk_free():
    rf = 0.04 / 252
    rets = [rf + 0.01, rf - 0.01] * 100
    vals = [1_000_000.0]
    for r in rets:
        vals.append(vals[-1] * (1 + r))
    m = _bt(vals).calculate_metrics()
    assert abs(m["sharpe_ratio"]) < 0.05


def test_max_drawdown_hand_computed():
    m = _bt([100.0, 120.0, 90.0, 130.0, 117.0], start=100.0).calculate_metrics()
    assert m["max_drawdown_pct"] == pytest.approx(-25.0)
    assert m["final_value"] == 117.0 and m["total_return_pct"] == pytest.approx(17.0)


def test_metrics_need_two_points():
    assert _bt([100.0], start=100.0).calculate_metrics() is None


def test_quality_weighted_weights_sum_to_one_and_clip_negative_scores():
    hits = [{"symbol": "A", "price": 10.0, "piotroski": {"score": 8}, "cmf": {"cmf_20": 0.2}},
            {"symbol": "B", "price": 20.0, "piotroski": {"score": 0}, "cmf": {"cmf_20": -0.5}}]
    pc = hpb.PortfolioConstructor(hits)
    w = pc.calculate_weights("quality_weighted")
    assert w == {"A": 1.0, "B": 0.0}
    p = pc.build_portfolio("equal_weight", date="2024-01-02")
    assert p["stocks"][0]["shares"] == pytest.approx(500_000 / 10.0)
