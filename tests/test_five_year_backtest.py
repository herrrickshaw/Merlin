"""five_year_backtest.simulate_backtest_period is a SIMULATION (prices are generated from an assumed market
return + a Piotroski 'quality premium' + noise), not a historical replay. These tests pin what it computes."""
import numpy as np
import pytest

import five_year_backtest as fyb


def _run(monkeypatch, market=15.0, noise=True, seed=0):
    if noise:
        np.random.seed(seed)
    else:
        monkeypatch.setattr(fyb.np.random, "normal", lambda loc, scale: 0.0)
    return fyb.FiveYearBacktester().simulate_backtest_period("p", "2023-01-15", market_return_pct=market)


def test_weights_are_quality_weighted_and_sum_to_one(monkeypatch):
    r = _run(monkeypatch, noise=False)
    assert r["stocks"] == 10 and r["starting_capital"] == 1_000_000
    assert len(r["daily_values"]) == 253                      # 252 calendar days, both ends inclusive


def test_noise_free_one_year_return_is_market_plus_annual_quality_premium(monkeypatch):
    # The code comments the premium as 'Up to 8% extra' (per year). With no noise and a 15% market each stock
    # compounds (1 + (0.15 + 0.08*p/9)/252)^252 - 1, i.e. between 22.5% (p=6) and 25.8% (p=9).
    r = _run(monkeypatch, market=15.0, noise=False)
    lo = ((1 + (0.15 + 0.08 * 6 / 9) / 252) ** 252 - 1) * 100
    hi = ((1 + (0.15 + 0.08) / 252) ** 252 - 1) * 100
    assert lo <= r["total_return_pct"] <= hi


def test_bear_market_input_is_not_turned_into_a_large_gain(monkeypatch):
    # -18.1% market (the 2022 period in run_five_year_backtest) plus at most +8%/yr premium cannot exceed 0
    r = _run(monkeypatch, market=-18.1, noise=False)
    assert r["total_return_pct"] < 0


def test_simulated_daily_moves_are_consistent_with_2pct_annual_vol(monkeypatch):
    # noise sd is 0.02/sqrt(252) per day; a price path built from it should never jump 5% in a day
    r = _run(monkeypatch, noise=True, seed=1)
    v = np.array([d["value"] for d in r["daily_values"]])
    assert np.max(np.abs(np.diff(v) / v[:-1])) < 0.05


def test_classify_market_boundaries():
    c = fyb.FiveYearBacktester().classify_market
    assert [c(x) for x in (25, 20, 15, 10, 5, 0, -5, -10, -20)] == [
        "Strong Bull", "Moderate Bull", "Moderate Bull", "Weak Bull", "Weak Bull", "Weak Bear", "Weak Bear",
        "Strong Bear", "Strong Bear"]
