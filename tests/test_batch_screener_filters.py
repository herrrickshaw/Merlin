"""StockFilters (batch_screener): CMF, Darvas proximity, simplified 'Piotroski' and Coffee Can gates."""
import numpy as np
import pandas as pd
import pytest

from batch_screener import StockFilters as F


def test_chaikin_money_flow_hand_computed():
    vd = {"close": [9.0, 10.0], "high": [10.0, 10.0], "low": [8.0, 8.0], "volume": [100.0, 300.0]}
    # day1 mult = ((9-8)-(10-9))/2 = 0; day2 mult = ((10-8)-0)/2 = 1 -> CMF = 300/400
    r = F.chaikin_money_flow(vd, period=2)
    assert r["cmf_20"] == pytest.approx(0.75) and r["status"] == "STRONG_ACCUMULATION" and r["passed"]


def test_cmf_flat_bars_and_short_history():
    vd = {"close": [5.0] * 20, "high": [5.0] * 20, "low": [5.0] * 20, "volume": [1.0] * 20}
    assert F.chaikin_money_flow(vd)["cmf_20"] == 0 and F.chaikin_money_flow({"close": [1.0]}) is None


def test_darvas_box_near_high_with_volume_surge_passes():
    close = np.linspace(50, 100, 260)
    vol = np.ones(260); vol[-1] = 2.0
    r = F.darvas_box(pd.DataFrame({"close": close}), {"volume": vol})
    assert r["passed"] and r["pct_off_high"] == 0 and r["vol_mult"] == pytest.approx(2.0 / (21 / 20))


def test_darvas_box_requires_a_year_of_history():
    assert F.darvas_box(pd.DataFrame({"close": np.ones(100)}), {"volume": np.ones(100)}) is None


def test_piotroski_simplified_counts_nine_static_checks():
    f = dict(net_income=1, operating_cash_flow=1, roe=0.1, debt_to_equity=0.5, current_ratio=2,
             revenue=10, profit_margin=0.1, roa=0.05, free_cash_flow=1)
    assert F.piotroski_score(f)["score"] == 9
    assert F.piotroski_score({**f, "debt_to_equity": 0})["score"] == 8   # zero debt scores as 'not < 1' (falsy)
    assert F.piotroski_score({}) is None


def test_coffee_can_rejections():
    ok = dict(revenue=1, net_income=1, free_cash_flow=1, pe_ratio=20, debt_to_equity=0.5)
    assert F.coffee_can_check(ok)["passed"]
    r = F.coffee_can_check({**ok, "pe_ratio": 60, "debt_to_equity": 3})
    assert not r["passed"] and r["reasons"] == ["Valuation concern", "High debt"]
