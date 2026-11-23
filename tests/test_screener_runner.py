"""screener_runner.py: indicator helpers, the five strategies, ranking, CSV loader and CLI."""
import sys

import pytest

import screener_runner as sr
from screener_runner import OHLCV, StockData


def bars(closes, highs=None, vols=None):
    return [OHLCV("d%d" % i, c, (highs[i] if highs else c), c, c, (vols[i] if vols else 100.0))
            for i, c in enumerate(closes)]


# ------------------------------- helpers -------------------------------

def test_pct_change():
    assert sr.pct_change(110, 100) == pytest.approx(10.0)
    assert sr.pct_change(90, -100) == pytest.approx(190.0)      # uses abs(old)
    assert sr.pct_change(None, 1) is None and sr.pct_change(1, None) is None
    assert sr.pct_change(5, 0) is None
    assert sr.pct_change(0, 10) == pytest.approx(-100.0)


def test_cagr():
    assert sr.cagr(200, 100, 1) == pytest.approx(100.0)
    assert sr.cagr(161.051, 100, 5) == pytest.approx(10.0, abs=1e-3)
    assert sr.cagr(100, 100, 5) == pytest.approx(0.0)
    assert sr.cagr(None, 100, 5) is None and sr.cagr(0, 100, 5) is None
    assert sr.cagr(100, 0, 5) is None and sr.cagr(100, -5, 5) is None
    assert sr.cagr(200, 100, 0.99) is None                      # years < 1


def test_sma():
    assert sr.sma([1, 2, 3, 4], 2) == 3.5
    assert sr.sma([1, 2, 3], 3) == 2.0
    assert sr.sma([1, 2], 3) is None


def test_high_52w_uses_last_252_bars():
    closes = [1.0] * 300
    highs = [1000.0] + [5.0] * 299                  # the spike is older than 252 bars
    s = StockData("X", ohlcv=bars(closes, highs))
    assert sr.high_52w(s) == 5.0
    short = StockData("X", ohlcv=bars([1.0] * 10, [9.0] + [2.0] * 9))
    assert sr.high_52w(short) == 9.0
    exactly = StockData("X", ohlcv=bars([1.0] * 252, [50.0] + [2.0] * 251))
    assert sr.high_52w(exactly) == 50.0                         # 252 bars -> the first one is included
    assert sr.high_52w(StockData("X")) is None


def test_ltp_and_avg_volume():
    s = StockData("X", ohlcv=bars([1, 2, 3]))
    assert sr.ltp(s) == 3 and sr.ltp(StockData("X")) is None
    v = StockData("X", ohlcv=bars([1] * 25, vols=[1000.0] * 5 + [10.0] * 20))
    assert sr.avg_volume_20d(v) == 10.0                         # only the last 20
    assert sr.avg_volume_20d(StockData("X", ohlcv=bars([1] * 19))) is None
    assert sr.avg_volume_20d(StockData("X", ohlcv=bars([1] * 20))) == 100.0


# ------------------------------- darvas -------------------------------

def darvas_stock(last_close, high, last_vol, n=30):
    closes = [100.0] * (n - 1) + [last_close]
    highs = [100.0] * (n - 1) + [last_close]
    highs[5] = high
    vols = [100.0] * (n - 1) + [last_vol]
    return StockData("D", ohlcv=bars(closes, highs, vols))


def test_darvas_breakout_and_metrics():
    r = sr.darvas_screen(darvas_stock(95.0, 100.0, 400.0))
    assert r.passed and r.note == "BREAKOUT" and r.strategy == "darvas"
    assert r.score == pytest.approx(-5.0)
    assert r.metrics["LTP"] == "95.00" and r.metrics["High_52w"] == "100.00"
    assert r.metrics["Off_High%"] == "5.0"
    avg = (19 * 100 + 400) / 20
    assert r.metrics["Vol_x20d"] == f"{400 / avg:.2f}"


def test_darvas_boundaries():
    # exactly 10% off the high passes the proximity test
    assert sr.darvas_screen(darvas_stock(90.0, 100.0, 1000.0)).passed
    assert sr.darvas_screen(darvas_stock(89.9, 100.0, 1000.0)).note == ""
    # near the high but volume too low
    r = sr.darvas_screen(darvas_stock(95.0, 100.0, 100.0))
    assert not r.passed and r.note == "near_high"
    # volume multiple exactly 1.5x of the 20d average (which includes today's bar)
    # avg=(19*100+v)/20 ; v/avg == 1.5 -> v = 1.5*(1900+v)/20 -> v = 1.5*1900/18.5
    v = 1.5 * 1900 / 18.5
    assert sr.darvas_screen(darvas_stock(95.0, 100.0, v)).passed


def test_darvas_volume_multiple_must_reach_1_5x():
    v = 1.45 * 1900 / 18.55                                    # 1.45x the 20d average
    assert not sr.darvas_screen(darvas_stock(95.0, 100.0, v)).passed
    assert sr.darvas_screen(darvas_stock(95.0, 100.0, 1.55 * 1900 / 18.45)).passed


def test_darvas_insufficient_data_and_no_volume_history():
    assert sr.darvas_screen(StockData("E")).note == "insufficient_data"
    z = StockData("Z", ohlcv=bars([0.0] * 5, [0.0] * 5))
    assert sr.darvas_screen(z).note == "insufficient_data"
    short = StockData("S", ohlcv=bars([95.0] * 5, [100.0] * 5))   # < 20 bars: avg_vol None -> vmult 0
    r = sr.darvas_screen(short)
    assert not r.passed and r.metrics["Vol_x20d"] == "0.00" and r.note == "near_high"


def test_darvas_at_high_has_no_score():
    r = sr.darvas_screen(darvas_stock(100.0, 100.0, 1000.0))
    assert r.passed and r.score is None


# ------------------------------- piotroski -------------------------------

GOOD = {"net_income": 1, "roa": 2, "roa_prev": 1, "cfo": 5, "debt_to_assets": 0.2,
        "debt_to_assets_prev": 0.3, "current_ratio": 2, "current_ratio_prev": 1.5, "shares": 10,
        "shares_prev": 10, "gross_margin": 0.4, "gross_margin_prev": 0.3, "asset_turnover": 1.1,
        "asset_turnover_prev": 1.0}


def test_piotroski_perfect_score():
    r = sr.piotroski_screen(StockData("P", fundamentals=dict(GOOD)))
    assert r.score == 9.0 and r.passed and r.note == "strong"
    assert r.metrics["F_Score"] == "9"
    assert [r.metrics[k] for k in ["ROA>0", "CFO>0", "dROA>0", "Accrual", "dLev<0", "dCR>0",
                                    "NoDilute", "dGM>0", "dAT>0"]] == ["1"] * 9


def test_piotroski_each_check_flips_individually():
    expect = {"roa": "ROA>0", "cfo": "CFO>0"}
    flips = [("roa", -1, "ROA>0"), ("cfo", -1, "CFO>0"), ("roa", 1, "dROA>0"),      # roa == roa_prev
             ("cfo", 1, "Accrual"),                                                  # cfo == net_income
             ("debt_to_assets", 0.3, "dLev<0"), ("current_ratio", 1.5, "dCR>0"),
             ("gross_margin", 0.3, "dGM>0"), ("asset_turnover", 1.0, "dAT>0")]
    for key, val, check in flips:
        f = dict(GOOD)
        f[key] = val
        r = sr.piotroski_screen(StockData("P", fundamentals=f))
        assert r.metrics[check] == "0", (key, val, check)
    f = dict(GOOD, shares=11)
    assert sr.piotroski_screen(StockData("P", fundamentals=f)).metrics["NoDilute"] == "0"
    assert sr.piotroski_screen(StockData("P", fundamentals=dict(GOOD, shares=10))).metrics["NoDilute"] == "1"
    assert expect


def test_piotroski_threshold_seven():
    f = dict(GOOD, shares=11, gross_margin=0.3)              # 7 of 9 pass
    r = sr.piotroski_screen(StockData("P", fundamentals=f))
    assert r.score == 7.0 and r.passed
    f = dict(f, asset_turnover=1.0)                            # 6 of 9
    r = sr.piotroski_screen(StockData("P", fundamentals=f))
    assert r.score == 6.0 and not r.passed and r.note == ""


def test_piotroski_missing_data_scores_zero():
    r = sr.piotroski_screen(StockData("P"))
    assert r.score == 0.0 and not r.passed and r.metrics["F_Score"] == "0"
    assert set(r.metrics.values()) == {"0"}


# ------------------------------- coffee can / magic formula -------------------------------

def test_coffee_can_pass_and_boundaries():
    f = {"roe": 15.0, "revenue": 161.051, "revenue_5y_ago": 100.0, "debt_to_equity": 1.0}
    r = sr.coffee_can_screen(StockData("C", fundamentals=f))
    assert r.passed and r.note == "quality_compounder" and r.score == 15.0
    assert r.metrics["ROE"] == "15.0" and r.metrics["DE"] == "1.00" and r.metrics["RevCAGR5y"] == "10.0"
    assert (r.metrics["ROE>=15"], r.metrics["RevCAGR>=10"], r.metrics["DE<=1"]) == ("1", "1", "1")
    for key, val, flag in [("roe", 14.9, "ROE>=15"), ("debt_to_equity", 1.01, "DE<=1"),
                           ("revenue", 150.0, "RevCAGR>=10")]:
        r = sr.coffee_can_screen(StockData("C", fundamentals=dict(f, **{key: val})))
        assert not r.passed and r.metrics[flag] == "0"


def test_coffee_can_missing_fields_show_na():
    r = sr.coffee_can_screen(StockData("C"))
    assert not r.passed and r.score is None
    assert (r.metrics["ROE"], r.metrics["RevCAGR5y"], r.metrics["DE"]) == ("N/A", "N/A", "N/A")


def test_magic_formula():
    r = sr.magic_formula_screen(StockData("M", fundamentals={"roe": 15.1, "earnings_yield": 0.5}))
    assert r.passed and r.note == "cheap_quality" and r.score == 0.5
    assert r.metrics["ROE"] == "15.1" and r.metrics["Earnings_Yield"] == "0.50%"
    assert not sr.magic_formula_screen(StockData("M", fundamentals={"roe": 15.0, "earnings_yield": 1})).passed
    assert not sr.magic_formula_screen(StockData("M", fundamentals={"roe": 20, "earnings_yield": 0})).passed
    r = sr.magic_formula_screen(StockData("M"))
    assert r.metrics["ROE"] == "N/A" and r.metrics["Earnings_Yield"] == "N/A" and not r.passed


# ------------------------------- golden crossover -------------------------------

def test_golden_crossover():
    up = StockData("G", ohlcv=bars([float(i + 1) for i in range(250)]))
    r = sr.golden_crossover_screen(up)
    assert r.passed and r.note == "bullish"
    assert r.metrics["SMA50"] == f"{sum(range(201, 251)) / 50:.2f}"
    assert r.metrics["SMA200"] == f"{sum(range(51, 251)) / 200:.2f}"
    assert r.score == pytest.approx((sum(range(201, 251)) / 50) / (sum(range(51, 251)) / 200))
    down = StockData("G", ohlcv=bars([float(250 - i) for i in range(250)]))
    r = sr.golden_crossover_screen(down)
    assert not r.passed and r.note == "bearish"
    flat = StockData("G", ohlcv=bars([10.0] * 250))
    assert not sr.golden_crossover_screen(flat).passed         # equal averages is not a crossover


def test_golden_crossover_needs_200_bars():
    assert sr.golden_crossover_screen(StockData("G", ohlcv=bars([1.0] * 199))).note == "insufficient_data"
    assert sr.golden_crossover_screen(StockData("G", ohlcv=bars([1.0] * 200))).note == "bearish"
    zeros = StockData("G", ohlcv=bars([0.0] * 200))
    assert sr.golden_crossover_screen(zeros).note == "insufficient_data"


# ------------------------------- orchestration -------------------------------

def test_screen_stock_and_market_and_rank():
    a = StockData("A", ohlcv=bars([float(i + 1) for i in range(250)]), fundamentals=dict(GOOD))
    b = StockData("B", fundamentals={"roe": 30.0, "earnings_yield": 5.0})
    c = StockData("C", fundamentals={"roe": 20.0, "earnings_yield": 9.0})
    assert [r.strategy for r in sr.screen_stock(a)] == ["darvas", "piotroski", "coffee_can",
                                                         "magic_formula", "golden_crossover"]
    res = sr.screen_market([a, b, c])
    assert len(res) == 15
    ranked = sr.rank_results(res, "magic_formula")
    assert [r.symbol for r in ranked] == ["C", "B"]               # by earnings yield desc
    assert all(r.passed for r in ranked)
    assert sr.rank_results(res, "nope") == []
    assert sr.rank_results(res, "piotroski")[0].symbol == "A"


def test_rank_results_treats_missing_score_as_zero():
    R = sr.Result
    res = [R("A", "s", True, score=None), R("B", "s", True, score=-3.0), R("C", "s", True, score=2.0),
           R("D", "s", False, score=99.0)]
    assert [r.symbol for r in sr.rank_results(res, "s")] == ["C", "A", "B"]


# ------------------------------- CSV loader -------------------------------

def test_load_csv_to_stocks(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text(
        "symbol,date,open,high,low,close,volume,roe,net_income,revenue\n"
        "AAA,2024-01-01,1,2,0.5,1.5,100,18.5,,50\n"
        "AAA,2024-01-02,2,3,1,2.5,200,19.0,7,60\n"
        "BBB,2024-01-01,5,6,4,5.5,300,notanumber,,\n"
        ",2024-01-01,9,9,9,9,9,1,1,1\n")
    stocks = {s.symbol: s for s in sr.load_csv_to_stocks(str(p))}
    assert set(stocks) == {"AAA", "BBB"}                         # blank symbol row skipped
    a = stocks["AAA"]
    assert [b.close for b in a.ohlcv] == [1.5, 2.5] and a.ohlcv[1].volume == 200.0
    assert a.fundamentals == {"roe": 19.0, "net_income": 7.0, "revenue": 60.0}   # later rows overwrite
    assert stocks["BBB"].fundamentals == {}                      # unparseable / empty ignored


def test_load_csv_defaults_for_missing_columns(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("symbol\nAAA\n")
    s = sr.load_csv_to_stocks(str(p))[0]
    assert s.ohlcv[0].close == 0.0 and s.ohlcv[0].date == ""


# ------------------------------- CLI -------------------------------

def _csv(tmp_path):
    rows = ["symbol,date,open,high,low,close,volume,roe,earnings_yield"]
    for i in range(250):
        rows.append(f"UP,d{i},1,{i + 2},1,{i + 1},100,30,5")
    rows.append("LOW,d0,1,1,1,1,1,1,-1")
    p = tmp_path / "m.csv"
    p.write_text("\n".join(rows))
    return str(p)


def test_main_usage_exit(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["screener_runner.py"])
    with pytest.raises(SystemExit) as e:
        sr.main()
    assert e.value.code == 1 and "Usage" in capsys.readouterr().out


def test_main_full_run_and_options(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["screener_runner.py", _csv(tmp_path), "--top", "1"])
    sr.main()
    out = capsys.readouterr().out
    assert "Loaded 2 stocks" in out and "Generated 10 results" in out
    assert "Strategies: golden_crossover, magic_formula" in out
    assert "Top 1 MAGIC_FORMULA Results" in out and "UP" in out
    assert "magic_formula" in out and "avg score:   5.00" in out
    assert "Multi-Pass Effectiveness" in out and "UP          : 2 strategies" in out


def test_main_parses_strategy_and_top_pairs(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["screener_runner.py", _csv(tmp_path), "--strategy", "darvas",
                                      "--top", "3"])
    sr.main()
    assert "Top 1 MAGIC_FORMULA Results" in capsys.readouterr().out


def test_main_dangling_top_flag_is_ignored(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["screener_runner.py", _csv(tmp_path), "--top"])
    sr.main()                                   # no value after --top: default top_n (10) is kept
    assert "Top 1 MAGIC_FORMULA Results" in capsys.readouterr().out
