"""alternative_screens_analysis, forward_5year_stock_picks and nbim_criteria_analysis: seeded report runs."""
import json

import numpy as np
import pytest

import alternative_screens_analysis as asa
import forward_5year_stock_picks as f5
import nbim_criteria_analysis as nb


# =============================== alternative_screens_analysis ===============================

def test_screening_database_content(capsys):
    db = asa.ScreeningStrategyDatabase()
    assert isinstance(db.strategies, dict) and len(db.strategies) >= 5
    for name, s in db.strategies.items():
        assert s, name
    capsys.readouterr()


def test_print_and_export_database(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    db = asa.ScreeningStrategyDatabase()
    db.print_comprehensive_analysis()
    assert capsys.readouterr().out.strip()
    db.export_database()
    data = json.loads((tmp_path / "screening_strategies_database.json").read_text())
    assert data
    assert "Database exported" in capsys.readouterr().out


# =============================== forward_5year_stock_picks ===============================

def test_forward_picks_generate_and_export(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    p = f5.Forward5YearStockPicks()
    out = p.generate_picks()
    assert isinstance(out, dict) and out
    p.export_results()
    data = json.loads((tmp_path / "forward_stock_picks_2025_2029.json").read_text())
    assert set(data) >= {"timestamp", "current_yen_usd_rate", "capital_jpy", "capital_usd",
                         "recommendations", "rate_scenarios"}
    assert data["capital_usd"] == pytest.approx(data["capital_jpy"] / data["current_yen_usd_rate"], rel=0.02)
    assert data["recommendations"]
    assert "exported" in capsys.readouterr().out


def test_fx_adjusted_returns_by_scenario():
    p = f5.Forward5YearStockPicks()
    t = next(iter(p.stock_universe))
    st = p.stock_universe[t]
    price = st["current_price"] * 1.5
    rate = p.current_rate
    for scen, target in (("conservative", 140), ("base_case", 152), ("bullish", 178)):
        r = p.calculate_fx_adjusted_returns(t, price, scen)
        fx = st["usd_exposure"] * (target - rate) / rate
        assert r["stock_return"] == pytest.approx(0.5) and r["fx_impact"] == pytest.approx(fx)
        assert r["total_return"] == pytest.approx(1.5 * (1 + fx) - 1)
    cons = p.calculate_fx_adjusted_returns(t, price, "conservative")["total_return"]
    bull = p.calculate_fx_adjusted_returns(t, price, "bullish")["total_return"]
    assert cons < bull
    other = p.calculate_fx_adjusted_returns(t, price, "anything-else")
    assert other["fx_impact"] == pytest.approx(st["usd_exposure"] * (178 - rate) / rate)


# =============================== nbim_criteria_analysis ===============================

def test_nbim_analyzer_flags_and_export(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    np.random.seed(0)
    a = nb.NBIMAnalyzer()
    df = a.analyze_holdings()
    assert len(df) == 19
    assert {"ticker", "name", "sector", "piotroski", "darvas", "piotroski_pass", "coffee_can"} <= set(df.columns)
    a.export_analysis(df)
    assert (tmp_path / "nbim_triple_hit_analysis.csv").exists()
    assert "exported" in capsys.readouterr().out


def test_nbim_triple_hit_criteria_boundaries():
    a = nb.NBIMAnalyzer()
    r = a.apply_triple_hit_criteria({"darvas_2024": True, "piotroski_est": 7})
    assert r == {"darvas": True, "piotroski": True, "coffee_can": True, "cmf": True, "triple_hit": True,
                 "stages_passed": 4}
    r = a.apply_triple_hit_criteria({"darvas_2024": True, "piotroski_est": 6})
    assert r["triple_hit"] is False and r["stages_passed"] == 2 and not r["piotroski"] and not r["coffee_can"]
    r = a.apply_triple_hit_criteria({"piotroski_est": 9})
    assert r["darvas"] is False and r["triple_hit"] is False and r["stages_passed"] == 3
    r = a.apply_triple_hit_criteria({})                       # default piotroski estimate is 5
    assert r["stages_passed"] == 1 and r["cmf"] is True
