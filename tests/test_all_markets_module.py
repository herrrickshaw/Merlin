"""test_all_markets.py (a synthetic multi-market demo, imported here as a module)."""
import random

import pytest

import test_all_markets as tam


def flat(n, v):
    return [v] * n


def test_darvas_needs_60_prices():
    assert tam.darvas_screen([1.0] * 59) is None
    assert tam.darvas_screen([1.0] * 60) is not None


def test_darvas_signals_and_boundaries():
    up = [float(i + 1) for i in range(100)]
    r = tam.darvas_screen(up)
    assert r == {"signal": "BREAKOUT_BUY", "pct_off_high": 0.0}
    base = [100.0] * 99
    assert tam.darvas_screen(base + [90.0])["signal"] == "BREAKOUT_BUY"        # exactly 10% off, < 200 bars
    assert tam.darvas_screen(base + [89.9])["signal"] == "IN_BOX"
    assert tam.darvas_screen(base + [70.0])["signal"] == "IN_BOX"              # exactly 30% off is not a breakdown
    assert tam.darvas_screen(base + [69.9])["signal"] == "BREAKDOWN_SELL"
    assert tam.darvas_screen([0.0] * 100)["pct_off_high"] == 100               # zero high guard


def test_darvas_uses_only_last_252_prices_for_the_high():
    prices = [1000.0] + [100.0] * 260
    assert tam.darvas_screen(prices)["pct_off_high"] == 0.0


def test_darvas_above_200_day_average_gate():
    # 199 bars at 100 with one 105 spike, then the last price 100: 4.8% off the high (near it) and
    # equal to the 200-day mean-ish but not above it -> no breakout
    prices = [100.0] * 200
    prices[10] = 105.0
    assert prices[-1] < sum(prices[-200:]) / 200
    assert tam.darvas_screen(prices)["signal"] == "IN_BOX"
    # fewer than 200 bars: the gate is skipped (treated as above)
    short = [100.0] * 100
    short[10] = 105.0
    assert tam.darvas_screen(short)["signal"] == "BREAKOUT_BUY"
    # a price above the 200d mean and near the high is a breakout
    prices[-1] = 104.0
    assert tam.darvas_screen(prices)["signal"] == "BREAKOUT_BUY"


def test_mean_stddev_helpers():
    assert tam.mean([1, 2, 3]) == 2 and tam.mean([]) is None
    assert tam.stddev([1, 2, 3]) == 1 and tam.stddev([1]) is None
    assert tam.simple_returns([100, 110]) == pytest.approx([0.1])


def test_simulated_stage_helpers():
    random.seed(0)
    assert all(4 <= tam.piotroski_score() <= 9 for _ in range(200))
    assert {tam.piotroski_score() for _ in range(500)} == set(range(4, 10))
    random.seed(1)
    rate = sum(tam.coffee_can_check() for _ in range(4000)) / 4000
    assert 0.40 < rate < 0.50                             # score > 0.55 passes ~45% of the time


def test_generate_market_data():
    random.seed(2)
    s = tam.generate_market_data("SG")
    assert len(s) == 200 and s[0]["symbol"] == "SG_0000" and s[0]["market"] == "SG" and len(s[0]["prices"]) == 252
    small = tam.generate_market_data("IN", num_stocks=3)
    assert [x["symbol"] for x in small] == ["IN_0000", "IN_0001", "IN_0002"]
    assert all(0.98 <= b / a <= 1.02 for a, b in zip(small[0]["prices"], small[0]["prices"][1:]))
    assert len(tam.generate_market_data("SG", None)) == 200 and len(tam.MARKETS) == 6


def test_run_pipeline_counts(monkeypatch, capsys):
    up = {"symbol": "U", "prices": [float(i + 1) for i in range(100)]}
    dn = {"symbol": "D", "prices": [float(100 - i) for i in range(100)]}
    short = {"symbol": "S", "prices": [1.0] * 10}
    monkeypatch.setattr(tam, "piotroski_score", lambda: 9)
    monkeypatch.setattr(tam, "coffee_can_check", lambda: True)
    r = tam.run_pipeline("US", [up, dn, short, dict(up, symbol="U2")])
    assert r["market"] == "US" and r["total_symbols"] == 4 and r["breakouts"] == 2
    assert r["strong_financials"] == 2 and r["triple_hits"] == 2
    assert len(r["stage_times"]) == 3 and r["total_time"] == pytest.approx(sum(r["stage_times"]))


def test_run_pipeline_piotroski_cutoff_and_coffee_can(monkeypatch):
    stocks = [{"symbol": f"U{i}", "prices": [float(i + 1) for i in range(100)]} for i in range(3)]
    scores = iter([6, 7, 9])
    monkeypatch.setattr(tam, "piotroski_score", lambda: next(scores))
    flags = iter([True, False])
    monkeypatch.setattr(tam, "coffee_can_check", lambda: next(flags))
    r = tam.run_pipeline("IN", stocks)
    assert r["breakouts"] == 3 and r["strong_financials"] == 2     # 7 and 9 qualify, 6 does not
    assert r["triple_hits"] == 1                                    # coffee can passes only the first strong one
    assert [s.get("coffee_can") for s in stocks] == [None, True, None]


def test_main_runs_all_six_markets(monkeypatch, capsys):
    random.seed(42)
    seen = []
    real = tam.run_pipeline
    monkeypatch.setattr(tam, "run_pipeline", lambda m, s: seen.append((m, len(s))) or real(m, s))
    tam.main()
    assert seen == [("IN", 100), ("US", 100), ("EU", 100), ("JP", 100), ("KR", 100), ("SG", 100)]
    assert capsys.readouterr().out
