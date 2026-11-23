"""currency_adjusted_backtest, cmf_accumulation_test and benchmark: pure calculations + seeded runs."""
import csv
import json
import random

import pytest

import benchmark as bm
import cmf_accumulation_test as cmf
import currency_adjusted_backtest as fx


# =============================== CMF ===============================

def candle(h, l, c, v):
    return {"high": h, "low": l, "close": c, "volume": v, "open": c, "date": "d"}


def test_cmf_basic_and_window():
    cs = [candle(10, 0, 10, 100)] * 3                       # multiplier +1 -> CMF 1
    assert cmf.chaikin_money_flow(cs, 3) == 1.0
    cs2 = [candle(10, 0, 0, 1000)] + [candle(10, 0, 10, 100)] * 2
    assert cmf.chaikin_money_flow(cs2, 2) == 1.0            # oldest candle excluded from the window
    assert cmf.chaikin_money_flow(cs2, 3) == pytest.approx((-1000 + 200) / 1200)
    assert cmf.chaikin_money_flow(cs2, 4) is None           # fewer candles than the period


def test_cmf_zero_range_and_zero_volume():
    assert cmf.chaikin_money_flow([candle(5, 5, 5, 100)] * 2, 2) == 0
    assert cmf.chaikin_money_flow([candle(10, 0, 10, 0)] * 2, 2) is None


@pytest.mark.parametrize("v,status", [
    (None, "INSUFFICIENT_DATA"), (0.26, "STRONG_ACCUMULATION"), (0.25, "ACCUMULATION"),
    (0.06, "ACCUMULATION"), (0.05, "NEUTRAL"), (0.0, "NEUTRAL"), (-0.05, "DISTRIBUTION"),
    (-0.06, "DISTRIBUTION"), (-0.25, "STRONG_DISTRIBUTION"), (-0.26, "STRONG_DISTRIBUTION"),
])
def test_cmf_signal_bands(v, status):
    assert cmf.cmf_signal(v) == status


def test_is_accumulation_phase_boundary():
    assert not cmf.is_accumulation_phase(None)
    assert not cmf.is_accumulation_phase(0.05) and cmf.is_accumulation_phase(0.0501)
    assert not cmf.is_accumulation_phase(-1)


@pytest.mark.parametrize("v,conf", [(None, 0.0), (0.3, 0.95), (0.25, 0.75), (0.06, 0.75), (0.05, 0.5),
                                    (0.0, 0.5), (-0.0499, 0.5), (-0.05, 0.25)])
def test_analyze_accumulation_confidence(monkeypatch, v, conf):
    monkeypatch.setattr(cmf, "chaikin_money_flow", lambda c, p: v if p == 20 else 0.1)
    r = cmf.analyze_accumulation("X", [])
    assert r["confidence"] == conf and r["cmf_20"] == v and r["cmf_50"] == 0.1
    assert r["status"] == cmf.cmf_signal(v) and r["in_accumulation"] == cmf.is_accumulation_phase(v)
    assert r["symbol"] == "X"


def test_generate_candles_shape_and_invariants():
    random.seed(7)
    cs = cmf.generate_candles("X", num_candles=60, trend="neutral")
    assert len(cs) == 60
    for c in cs:
        assert c["high"] >= max(c["open"], c["close"]) and c["low"] <= min(c["open"], c["close"])
        assert isinstance(c["volume"], int) and 800_000 <= c["volume"] <= 1_200_000
    dates = [c["date"] for c in cs]
    assert dates == sorted(dates) and len(set(dates)) == 60


def test_generate_candles_volume_regimes():
    random.seed(1)
    acc = cmf.generate_candles("X", 400, trend="accumulation")
    up_vol = [c["volume"] for c in acc if c["close"] > c["open"]]
    assert max(up_vol) > 1_200_000 and min(up_vol) >= 800_000
    dist = cmf.generate_candles("X", 400, trend="distribution")
    assert max(c["volume"] for c in dist if c["close"] < c["open"]) > 1_200_000
    assert all(c["volume"] <= 1_200_000 for c in dist if c["close"] >= c["open"])


def test_accumulation_trend_scores_higher_cmf_than_distribution():
    random.seed(3)
    a = [cmf.chaikin_money_flow(cmf.generate_candles("X", 120, trend="accumulation")) for _ in range(5)]
    d = [cmf.chaikin_money_flow(cmf.generate_candles("X", 120, trend="distribution")) for _ in range(5)]
    assert sum(a) / 5 > sum(d) / 5


def test_cmf_main_runs(capsys):
    random.seed(5)
    cmf.main()
    out = capsys.readouterr().out
    assert "ACCUMULATION PHASE" in out and "ACCUM_01" in out


# =============================== benchmark ===============================

def test_generate_test_data_csv(tmp_path, capsys):
    f = tmp_path / "d.csv"
    random.seed(0)
    bm.generate_test_data(str(f), num_stocks=3, num_days=4)
    rows = list(csv.DictReader(open(f)))
    assert len(rows) == 12 and {r["symbol"] for r in rows} == {"STOCK0000", "STOCK0001", "STOCK0002"}
    assert len(rows[0]) == 26
    assert [r["date"] for r in rows[:4]] == sorted(r["date"] for r in rows[:4])
    assert all(float(r["high"]) > 0 for r in rows)
    assert "Generated" in capsys.readouterr().out


def test_estimate_ocaml_performance():
    r = bm.estimate_ocaml_performance(3.0)
    assert r == {"avg": 0.1, "min": pytest.approx(0.095), "max": pytest.approx(0.105), "speedup": 30.0}
    assert bm.estimate_ocaml_performance(3.0, 10.0)["avg"] == pytest.approx(0.3)


def test_print_benchmark_results_math(capsys):
    py = {"avg": 2.0, "min": 1.9, "max": 2.1}
    oc = {"avg": 0.5, "min": 0.4, "max": 0.6}
    speedup, saved, pct = bm.print_benchmark_results(py, oc, 100)
    assert (speedup, saved, pct) == (4.0, 1.5, 75.0)
    out = capsys.readouterr().out
    assert "Total bars analyzed: 25,200" in out and "Speedup Factor: 4.0x" in out
    assert "Time Saved Per 1000 Runs: 25.0 minutes" in out
    assert "Time Saved Per Day (2880 runs): 1.2 hours" in out


def test_calculate_real_world_savings_scenarios(capsys):
    bm.calculate_real_world_savings(10.0, 2.0)
    out = capsys.readouterr().out
    assert "Daily screening (3000 stocks)" in out and "Quarterly backtest" in out
    # daily: runs 3000 -> total_py = 2*3000/100 = 60s => 1.0 minutes; ocaml 0.1; saved 0.9 (90%)
    assert "Total bars: 3,000" in out and "Python: 1.0 minutes" in out and "Savings: 0.9 minutes (90%)" in out


def test_benchmark_python_with_real_screener(tmp_path, capsys):
    f = tmp_path / "d.csv"
    random.seed(0)
    bm.generate_test_data(str(f), num_stocks=2, num_days=30)
    r = bm.benchmark_python(str(f), num_runs=2)
    assert set(r) >= {"avg", "min", "max"} and r["min"] <= r["avg"] <= r["max"]


def test_compare_with_global_screener_prints_table(capsys):
    bm.compare_with_global_screener()
    out = capsys.readouterr().out
    assert "Strategies" in out and "5 (core)" in out and "30-50x faster" in out


def test_benchmark_main_uses_three_dataset_sizes(monkeypatch, capsys):
    gen_calls = []
    monkeypatch.setattr(bm, "generate_test_data", lambda f, n, d: gen_calls.append((f, n, d)))
    monkeypatch.setattr(bm, "benchmark_python", lambda f, num_runs: {"avg": 3.0, "min": 2.9, "max": 3.1})
    bm.main()
    assert gen_calls == [("/tmp/benchmark_small.csv", 50, 100), ("/tmp/benchmark_medium.csv", 100, 252),
                         ("/tmp/benchmark_large.csv", 500, 252)]
    out = capsys.readouterr().out
    assert "SMALL: 50 stocks" in out and "LARGE: 500 stocks" in out and "Speedup:    30.0x" in out


# =============================== currency adjusted ===============================

@pytest.fixture
def an():
    return fx.CurrencyAdjustedCarryTrade()


@pytest.mark.parametrize("e,cat", [(0.50, "HIGH_USD_SENSITIVE"), (0.499, "MEDIUM_USD_SENSITIVE"),
                                   (0.35, "MEDIUM_USD_SENSITIVE"), (0.349, "MILD_USD_SENSITIVE"),
                                   (0.20, "MILD_USD_SENSITIVE"), (0.199, "NEUTRAL_OR_JPY_EXPOSED"),
                                   (-1, "NEUTRAL_OR_JPY_EXPOSED")])
def test_fx_categories(an, e, cat):
    assert an._categorize_fx_exposure(e) == cat


def test_fx_sensitivity_net_exposure(an):
    r = an.calculate_fx_sensitivity("AAPL", an.stocks["AAPL"])
    assert r["net_usd_exposure"] == pytest.approx(0.45) and r["fx_category"] == "MEDIUM_USD_SENSITIVE"
    assert r["stock"] == "AAPL" and r["sector"] == "Tech" and r["beta_to_usd"] == 0.85
    n = an.calculate_fx_sensitivity("NVDA", an.stocks["NVDA"])
    assert n["net_usd_exposure"] == pytest.approx(0.62) and n["fx_category"] == "HIGH_USD_SENSITIVE"


def test_swap_ratio_bands(an, monkeypatch):
    def with_exposure(x):
        monkeypatch.setattr(an, "calculate_fx_sensitivity",
                            lambda s, d: {"net_usd_exposure": x})
        return an.calculate_currency_swap_ratio(["AAPL"], {})

    assert with_exposure(0.45)["optimal_swap_ratio"] == 0.25
    assert with_exposure(0.449)["optimal_swap_ratio"] == 0.45
    assert with_exposure(0.35)["optimal_swap_ratio"] == 0.45
    assert with_exposure(0.349)["optimal_swap_ratio"] == 0.65
    r = with_exposure(0.45)
    assert r["avg_usd_exposure"] == pytest.approx(0.45) and "25% of USD position" in r["interpretation"]


def test_swap_ratio_averages_over_portfolio(an):
    r = an.calculate_currency_swap_ratio(["AAPL", "TSLA"], {})
    assert r["avg_usd_exposure"] == pytest.approx((0.45 + 0.20) / 2)
    assert r["optimal_swap_ratio"] == 0.65


def test_model_fx_impact(an):
    out = an.model_fx_impact_on_stocks({"2020": 10.0, "2021": -5.0})
    assert list(out) == ["2020", "2021"] and len(out["2020"]) == 10
    aapl = [x for x in out["2020"] if x["stock"] == "AAPL"][0]
    assert aapl["fx_impact_on_return"] == pytest.approx(0.45 * 10.0 * 0.8)
    assert aapl["fx_change_pct"] == 10.0 and aapl["year"] == "2020"
    assert [x for x in out["2021"] if x["stock"] == "AAPL"][0]["fx_impact_on_return"] == pytest.approx(-1.8)


def test_hedged_vs_unhedged(an):
    res = an.calculate_hedged_vs_unhedged([10.0, 20.0], {"y1": 10.0, "y2": -10.0}, 0.4)
    a, b = res
    assert a["return_unhedged"] == pytest.approx(15.0)
    assert a["return_hedged"] == pytest.approx(10.0 + 0.6 * 10.0 * 0.5 - 0.015)
    assert a["benefit_of_hedge"] == pytest.approx(a["return_hedged"] - a["return_unhedged"])
    assert b["return_unhedged"] == pytest.approx(15.0) and b["swap_ratio"] == 0.4
    assert b["benefit_of_hedge"] == pytest.approx((1 - 0.4) * -5.0 + 20.0 - 0.015 - 15.0)
    full = an.calculate_hedged_vs_unhedged([5.0], {"y": 8.0}, 1.0)[0]
    assert full["return_hedged"] == pytest.approx(5.0 - 0.015)


def test_portfolio_composition(an):
    r = an.analyze_portfolio_composition(["NVDA", "TSLA", "GOOGL"])
    assert r["portfolio_weighted_usd_exposure"] == pytest.approx((0.62 + 0.20 + 0.58) / 3)
    assert r["high_usd_exposure_count"] == 2
    assert r["neutral_count"] == 1     # TSLA: 0.35 - 0.15 == 0.19999999999999998 in floats, just under the 0.20 band
    assert len(r["stocks"]) == 3
    assert an.analyze_portfolio_composition(["TSLA"])["high_usd_exposure_count"] == 0


def test_run_analysis_and_export(an, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    an.run_analysis()
    assert an.results
    an.export_results()
    assert json.loads((tmp_path / "currency_adjusted_analysis.json").read_text()) == json.loads(
        json.dumps(an.results, default=str))
    assert "Exported to currency_adjusted_analysis.json" in capsys.readouterr().out
