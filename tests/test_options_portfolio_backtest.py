"""options_portfolio_backtest.py: Black-Scholes, Greeks, portfolio construction and the synthetic backtest."""
import math
import random

import pytest

import options_portfolio_backtest as op

S, K, T, R, Q, V = 100.0, 100.0, 0.5, 0.04, 0.02, 0.2


def test_norm_functions():
    assert op.norm_cdf(0) == 0.5
    assert op.norm_cdf(1.96) == pytest.approx(0.975, abs=1e-4)
    assert op.norm_cdf(-1.0) == pytest.approx(1 - op.norm_cdf(1.0))
    assert op.norm_pdf(0) == pytest.approx(1 / math.sqrt(2 * math.pi))
    assert op.norm_pdf(1.0) == op.norm_pdf(-1.0)


def test_black_scholes_known_value():
    # S=K=100, T=1, r=5%, q=0, vol=20% -> textbook call 10.4506, put 5.5735
    assert op.black_scholes_call(100, 100, 1.0, 0.05, 0.0, 0.2) == pytest.approx(10.4506, abs=1e-3)
    assert op.black_scholes_put(100, 100, 1.0, 0.05, 0.0, 0.2) == pytest.approx(5.5735, abs=1e-3)


def test_put_call_parity_with_dividends():
    for spot, strike in [(100, 90), (100, 100), (80, 120)]:
        c = op.black_scholes_call(spot, strike, T, R, Q, V)
        p = op.black_scholes_put(spot, strike, T, R, Q, V)
        assert c - p == pytest.approx(spot * math.exp(-Q * T) - strike * math.exp(-R * T), abs=1e-9)


def test_prices_monotone_in_spot_strike_and_vol():
    assert op.black_scholes_call(110, K, T, R, Q, V) > op.black_scholes_call(100, K, T, R, Q, V)
    assert op.black_scholes_call(S, 110, T, R, Q, V) < op.black_scholes_call(S, 100, T, R, Q, V)
    assert op.black_scholes_call(S, K, T, R, Q, 0.4) > op.black_scholes_call(S, K, T, R, Q, 0.2)
    assert op.black_scholes_put(S, 110, T, R, Q, V) > op.black_scholes_put(S, 100, T, R, Q, V)


def test_greeks_delta_gamma_vega_rho_match_finite_differences():
    g = op.calculate_greeks(S, K, T, R, Q, V)
    h = 1e-3
    c = lambda s=S, t=T, r=R, v=V: op.black_scholes_call(s, K, t, r, Q, v)
    assert g["delta"] == pytest.approx((c(S + h) - c(S - h)) / (2 * h), abs=1e-5)
    assert g["gamma"] == pytest.approx((c(S + h) - 2 * c() + c(S - h)) / h ** 2, abs=1e-4)
    assert g["vega"] == pytest.approx((c(v=V + 1e-4) - c(v=V - 1e-4)) / 2e-4 / 100, abs=1e-4)
    assert g["rho"] == pytest.approx((c(r=R + 1e-4) - c(r=R - 1e-4)) / 2e-4 / 100, abs=1e-4)
    assert 0 < g["delta"] < 1 and g["gamma"] > 0 and g["vega"] > 0 and g["rho"] > 0


@pytest.mark.xfail(strict=True, reason="calculate_greeks divides the theta expression by 365 twice (the first "
                   "term already carries /365, then the whole sum is divided again) and gets the wrong sign "
                   "for an ATM call: it returns +0.0023/day where the finite-difference decay is -0.0175/day "
                   "(options_portfolio_backtest.py:~50)")
def test_theta_matches_one_day_of_decay():
    g = op.calculate_greeks(S, K, T, R, Q, V)
    decay = op.black_scholes_call(S, K, T - 1 / 365, R, Q, V) - op.black_scholes_call(S, K, T, R, Q, V)
    assert g["theta"] == pytest.approx(decay, rel=0.1)


def test_analyze_options_structure_and_expected_move():
    r = op.analyze_options(100.0, 100.0, 90, 0.25)
    t = 90 / 365.0
    assert r["expected_move"] == pytest.approx(100 * 0.25 * math.sqrt(t))
    assert r["upside_target"] == pytest.approx(100 + r["expected_move"])
    assert r["downside_target"] == pytest.approx(100 - r["expected_move"])
    assert r["call_price"] == pytest.approx(op.black_scholes_call(100, 100, t, 0.04, 0.02, 0.25))
    assert r["put_price"] == pytest.approx(op.black_scholes_put(100, 100, t, 0.04, 0.02, 0.25))
    assert set(r["greeks"]) == {"delta", "gamma", "vega", "theta", "rho"}


@pytest.mark.xfail(strict=True, reason="'probability_profit_call' is norm_cdf(delta): a CDF applied to a "
                   "probability-like number (ATM call: N(0.55)=0.71), not the risk-neutral exercise "
                   "probability N(d2) (~0.52 here) (options_portfolio_backtest.py:~79)")
def test_probability_profit_call_is_n_d2():
    r = op.analyze_options(100.0, 100.0, 182, 0.2)
    t = 182 / 365.0
    d2 = (math.log(1.0) + (0.04 - 0.02 - 0.2 ** 2 / 2) * t) / (0.2 * math.sqrt(t))
    assert r["probability_profit_call"] == pytest.approx(op.norm_cdf(d2), abs=0.02)


# ------------------------------- portfolio -------------------------------

A = {"symbol": "A", "expected_return": 0.20, "volatility": 0.25, "dividend": 0.02, "piotroski": 9, "cmf": 0.35}
B = {"symbol": "B", "expected_return": 0.10, "volatility": 0.10, "dividend": 0.01, "piotroski": 5, "cmf": 0.05}


def test_estimate_correlation():
    assert op.estimate_correlation(A, A) == 0.95                       # (1 + 1)/2 = 1 is capped at 0.95
    c = op.estimate_correlation(A, B)
    assert c == pytest.approx((math.exp(-4 / 3) + math.exp(-0.3 / 0.3)) / 2)
    assert op.estimate_correlation(A, B) == op.estimate_correlation(B, A)
    near = dict(A, piotroski=8, cmf=0.30)
    assert op.estimate_correlation(A, near) > c


def test_covariance_matrix():
    cov = op.build_covariance_matrix([A, B])
    assert cov[0][0] == pytest.approx(0.0625) and cov[1][1] == pytest.approx(0.01)
    assert cov[0][1] == cov[1][0] == pytest.approx(op.estimate_correlation(A, B) * 0.25 * 0.10)


def test_portfolio_return_and_volatility():
    assert op.portfolio_return([A, B], [0.5, 0.5]) == pytest.approx(0.15)
    assert op.portfolio_return([A, B], [1, 0]) == pytest.approx(0.20)
    assert op.portfolio_volatility([A, B], [1, 0]) == pytest.approx(0.25)
    assert op.portfolio_volatility([A, B], [0, 1]) == pytest.approx(0.10)
    mix = op.portfolio_volatility([A, B], [0.5, 0.5])
    assert 0.10 < mix < 0.175                                          # diversification: below the weighted mean


def test_create_portfolios_weights():
    p = op.create_portfolios([A, B])
    assert set(p) == {"equal_weight", "quality_weighted", "risk_parity"}
    assert p["equal_weight"]["weights"] == [0.5, 0.5]
    qa, qb = 9 + 0.35 * 3, 5 + 0.05 * 3
    assert p["quality_weighted"]["weights"] == pytest.approx([qa / (qa + qb), qb / (qa + qb)])
    assert p["risk_parity"]["weights"] == pytest.approx([(1 / 0.25) / (1 / 0.25 + 1 / 0.10),
                                                         (1 / 0.10) / (1 / 0.25 + 1 / 0.10)])
    for v in p.values():
        assert sum(v["weights"]) == pytest.approx(1.0)
        assert v["sharpe_ratio"] == pytest.approx(v["return"] / v["volatility"])
    assert p["equal_weight"]["dividend_yield"] == pytest.approx(0.015)
    assert p["equal_weight"]["allocation"] == {"A": "50.0%", "B": "50.0%"}


def test_create_portfolios_zero_total_volatility_has_zero_sharpe(monkeypatch):
    monkeypatch.setattr(op, "portfolio_volatility", lambda stocks, weights: 0.0)
    p = op.create_portfolios([A, B])
    assert all(v["sharpe_ratio"] == 0 for v in p.values())


def test_create_portfolios_zero_volatility_stock():
    z = dict(B, volatility=0.0)
    p = op.create_portfolios([A, z])
    assert p["risk_parity"]["weights"] == pytest.approx([1.0, 0.0])        # zero vol -> weight 0, not a crash


# ------------------------------- backtest -------------------------------

def test_generate_historical_prices_structure_and_determinism():
    random.seed(1)
    a = op.generate_historical_prices("X", 100, 30, 0.1, 0.2, start_date="2020-01-01")
    random.seed(1)
    b = op.generate_historical_prices("X", 100, 30, 0.1, 0.2, start_date="2020-01-01")
    assert a == b and len(a) == 30
    assert a[0]["date"] == "2020-01-01" and a[-1]["date"] == "2020-01-30"
    for r in a:
        assert r["high"] >= max(r["open"], r["close"]) and r["low"] <= min(r["open"], r["close"])
        assert r["adjusted_close"] == r["close"] and 1_000_000 <= r["volume"] <= 5_000_000


def test_generate_historical_prices_trend_drift(monkeypatch):
    monkeypatch.setattr(op.random, "gauss", lambda m, s: 0.0)
    end = {}
    for trend in ("bullish", "bearish", "neutral"):
        random.seed(0)
        end[trend] = op.generate_historical_prices("X", 100, 252, 0.2, 0.2, trend=trend,
                                                   start_date="2020-01-01")[-1]["close"]
    assert end["bullish"] > end["neutral"] > end["bearish"] > 100 * 0.9
    random.seed(0)
    default = op.generate_historical_prices("X", 100, 5, 0.2, 0.2)
    assert len(default) == 5


def series(closes, start="2020-01-01"):
    from datetime import datetime, timedelta
    d = datetime.strptime(start, "%Y-%m-%d")
    return [{"date": (d + timedelta(days=i)).strftime("%Y-%m-%d"), "adjusted_close": c}
            for i, c in enumerate(closes)]


def test_backtest_entry_exit_and_returns():
    prices = series([100.0 + i for i in range(400)])
    res = op.backtest_triple_hits([{"symbol": "X", "prices": prices}], "2020-01-10", 252)
    assert len(res) == 1
    r = res[0]
    assert r["entry_price"] == 109.0 and r["exit_price"] == 109.0 + 252 and r["days_held"] == 252
    assert r["return_pct"] == pytest.approx(252 / 109 * 100)
    assert r["annual_return"] == pytest.approx(r["return_pct"] * 365 / 252)


def test_backtest_holding_period_boundary_and_missing_data():
    prices = series([100.0] * 300)
    assert op.backtest_triple_hits([{"symbol": "X", "prices": prices}], "2020-01-01", 299)[0]["days_held"] == 299
    assert op.backtest_triple_hits([{"symbol": "X", "prices": prices}], "2020-01-01", 300) == []   # not enough data
    assert op.backtest_triple_hits([{"symbol": "X", "prices": prices}], "1999-01-01", 10) == []     # no such entry date
    assert op.backtest_triple_hits([], "2020-01-01") == []


def test_backtest_zero_holding_period_has_zero_annual_return():
    r = op.backtest_triple_hits([{"symbol": "X", "prices": series([100.0, 110.0])}], "2020-01-01", 0)[0]
    assert r["days_held"] == 0 and r["annual_return"] == 0 and r["return_pct"] == 0


def cohort(*rets):
    return [{"symbol": f"S{i}", "return_pct": r, "annual_return": r * 2} for i, r in enumerate(rets)]


def test_analyze_cohort():
    a = op.analyze_backtest_cohort(cohort(10, -5, 20, -15, 0))
    assert a["num_stocks"] == 5 and a["avg_return"] == pytest.approx(2.0)
    assert a["median_return"] == 0 and a["win_rate"] == pytest.approx(0.4)
    assert a["avg_win"] == pytest.approx(15) and a["avg_loss"] == pytest.approx(-10)
    assert a["profit_factor"] == pytest.approx(30 / 20) and a["avg_annual_return"] == pytest.approx(4.0)
    assert a["best_performer"]["symbol"] == "S2" and a["worst_performer"]["symbol"] == "S3"
    assert a["std_return"] == pytest.approx(__import__("statistics").stdev([10, -5, 20, -15, 0]))


def test_analyze_cohort_edge_cases():
    assert op.analyze_backtest_cohort([]) is None
    a = op.analyze_backtest_cohort(cohort(5))
    assert a["std_return"] == 0 and a["avg_loss"] == 0 and a["profit_factor"] == 0   # no losses -> factor 0
    assert op.analyze_backtest_cohort(cohort(-5, -3))["avg_win"] == 0


def test_main_runs_end_to_end(capsys):
    random.seed(42)
    op.main()
    out = capsys.readouterr().out
    assert "OPTIONS + PORTFOLIO OPTIMIZATION" in out and "TH_001" in out
    assert "Cohort Entry 2020-01-15" in out and "5-YEAR PERFORMANCE SUMMARY" in out
    assert "ANALYSIS COMPLETE" in out
