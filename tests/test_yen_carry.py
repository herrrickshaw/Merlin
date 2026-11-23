"""yen_carry_trade_backtest.py: the cost model, the 5-period run and the JSON export."""
import json

import pytest

import yen_carry_trade_backtest as yc


@pytest.fixture
def bt():
    return yc.YenCarryTradeBacktester()


def test_default_parameters(bt):
    assert (bt.jpy_borrow_rate, bt.brokerage_fee_pct, bt.fx_conversion_fee_pct) == (0.001, 0.0015, 0.002)
    assert (bt.annual_custody_fee_pct, bt.us_capital_gains_tax, bt.japan_income_tax, bt.fx_gain_tax) == (
        0.0005, 0.20, 0.15, 0.20)
    assert bt.results == []


def test_period_no_move_hand_computed(bt):
    r = bt.calculate_period_with_costs("flat", 0.0, 0.0)
    usd = (1e8 - 1e8 * 0.002) / 100                       # 998,000 USD after the entry FX fee
    assert r["starting_usd"] == pytest.approx(usd) and r["starting_jpy"] == 1e8
    assert r["ending_jpy_gross"] == pytest.approx(usd * 100)
    assert r["fx_gain_jpy"] == pytest.approx(0.0)
    interest = 1e8 * 0.001 * 252 / 365
    assert r["borrow_interest_jpy"] == pytest.approx(interest)
    c = r["costs_breakdown"]
    assert c["fx_conversion_in"] == pytest.approx(1e8 * 0.002 / 100)
    assert c["fx_conversion_out"] == pytest.approx(usd * 0.002)
    assert c["capital_gains_tax"] == 0 and c["fx_gain_tax"] == 0
    assert c["borrow_cost_tax"] == pytest.approx(interest * 0.15)
    custody = (1e8 + r["ending_jpy_net"] + c["fx_conversion_out"]) / 2 * 0.0005
    assert c["custody_fees"] == pytest.approx((1e8 + (usd * 100 - c["fx_conversion_out"])) / 2 * 0.0005)
    assert r["ending_jpy_net"] == pytest.approx(usd * 100 - c["fx_conversion_out"] - c["custody_fees"])
    assert r["net_jpy_gain"] == pytest.approx(r["ending_jpy_net"] - 1e8)
    assert r["net_return_pct"] == pytest.approx(r["net_jpy_gain"] / 1e8 * 100)
    assert c["total_costs"] == pytest.approx(
        c["fx_conversion_in"] + c["fx_conversion_out"] + c["borrow_interest"] + c["capital_gains_tax"]
        + c["fx_gain_tax"] + c["borrow_cost_tax"] + c["custody_fees"])
    assert custody


def test_period_gain_and_fx_taxes(bt):
    r = bt.calculate_period_with_costs("up", 10.0, 5.0, days=365)
    usd = 998000.0
    gain = usd * 0.10
    assert r["days"] == 365 and r["costs_breakdown"]["capital_gains_tax"] == pytest.approx(gain * 0.20)
    new_rate = 105.0
    expected_fx_gain = (usd + gain) * new_rate - usd * 100
    assert r["fx_gain_jpy"] == pytest.approx(expected_fx_gain)
    assert r["costs_breakdown"]["fx_gain_tax"] == pytest.approx(expected_fx_gain * 0.20)
    assert r["borrow_interest_jpy"] == pytest.approx(1e8 * 0.001)         # a full year of interest


def test_fx_loss_is_not_tax_deductible(bt):
    r = bt.calculate_period_with_costs("fxloss", 0.0, -5.0)
    assert r["fx_gain_jpy"] < 0 and r["costs_breakdown"]["fx_gain_tax"] == 0


def test_monotone_in_returns(bt):
    lo = bt.calculate_period_with_costs("a", 5.0, 0.0)["net_return_pct"]
    hi = bt.calculate_period_with_costs("b", 15.0, 0.0)["net_return_pct"]
    weak_yen = bt.calculate_period_with_costs("c", 5.0, 5.0)["net_return_pct"]
    assert hi > lo and weak_yen > lo


@pytest.mark.xfail(strict=True, reason="calculate_period_with_costs computes borrow interest and the three taxes "
                   "but never subtracts them (final_jpy = jpy_received - exit fee - custody), and it adds USD "
                   "fee amounts to JPY amounts in total_costs, so 'net' returns exclude interest/taxes "
                   "(yen_carry_trade_backtest.py:~96)")
def test_net_return_deducts_interest_and_both_fees(bt):
    r = bt.calculate_period_with_costs("flat", 0.0, 0.0)
    entry_fee_jpy = 1e8 * 0.002
    exit_fee_jpy = 998000 * 100 * 0.002
    interest = 1e8 * 0.001 * 252 / 365
    assert r["net_jpy_gain"] <= -(entry_fee_jpy + exit_fee_jpy + interest)


def test_run_backtest_five_periods(bt, capsys):
    res = bt.run_backtest()
    assert res is bt.results and len(res) == 5
    assert [r["gross_usd_return_pct"] for r in res] == [107.34, 67.05, 36.96, -20.18, 37.53]
    assert [r["fx_change_pct"] for r in res] == [5.0, 3.0, -2.0, 8.0, -1.0]
    assert "YEN CARRY TRADE BACKTEST" in capsys.readouterr().out


def test_print_methods_and_export(bt, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bt.run_backtest()
    bt.print_detailed_results()
    bt.print_summary()
    out = capsys.readouterr().out
    assert "2022-2023: Bear Market" in out
    bt.export_results()
    data = json.loads((tmp_path / "yen_carry_trade_results.json").read_text())
    cum_net = 1.0
    cum_gross = 1.0
    for r in bt.results:
        cum_net *= 1 + r["net_return_pct"] / 100
        cum_gross *= 1 + r["gross_usd_return_pct"] / 100
    s = data["summary"]
    assert s["net_5yr_return_pct"] == pytest.approx((cum_net - 1) * 100)
    assert s["gross_5yr_return_pct"] == pytest.approx((cum_gross - 1) * 100)
    assert s["net_cagr_pct"] == pytest.approx((cum_net ** 0.2 - 1) * 100)
    assert s["ending_capital_net_jpy"] == int(1e8 * cum_net)
    assert data["initial_jpy"] == 100_000_000 and len(data["periods"]) == 5
    assert data["jpy_borrow_rate"] == 0.001


def test_main_returns(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    yc.main()
    assert (tmp_path / "yen_carry_trade_results.json").exists()
