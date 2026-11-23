"""advanced_analysis_demo.py statistics helpers (hand-computed values) and the report generator."""
import csv
import math
import random

import pytest

import advanced_analysis_demo as aa


def test_mean_median_variance_stddev_and_empty_inputs():
    assert aa.mean([1, 2, 3, 4]) == 2.5 and aa.mean([]) is None
    assert aa.median([5, 1, 3]) == 3 and aa.median([]) is None
    assert aa.variance([1, 2, 3, 4]) == pytest.approx(1.25)          # population variance (divides by n)
    assert aa.variance([1]) is None
    assert aa.stddev([1, 2, 3, 4]) == pytest.approx(math.sqrt(5 / 3))  # sample stdev
    assert aa.stddev([1]) is None and aa.stddev([]) is None


def test_skewness_kurtosis_formulas_and_guards():
    v = [1.0, 2.0, 9.0]
    m, s = 4.0, statistics_stdev(v)
    expected = sum(((x - m) / s) ** 3 for x in v) / 3
    assert aa.skewness(v) == pytest.approx(expected) and aa.skewness(v) > 0
    assert aa.skewness([9.0, 2.0, 1.0]) == pytest.approx(expected)    # order independent
    assert aa.skewness([1, 2]) is None and aa.skewness([3, 3, 3]) is None
    k = [1.0, 2.0, 3.0, 10.0]
    s = statistics_stdev(k)
    assert aa.kurtosis(k) == pytest.approx(sum(((x - 4.0) / s) ** 4 for x in k) / 4 - 3)
    assert aa.kurtosis([1, 2, 3]) is None and aa.kurtosis([2, 2, 2, 2]) is None


def statistics_stdev(v):
    import statistics
    return statistics.stdev(v)


def test_quartiles_iqr():
    assert aa.quartiles([4, 1, 3, 2]) == (2, 3, 4)       # indices n//4, n//2, 3n//4 of the sorted list
    assert aa.quartiles(list(range(1, 9))) == (3, 5, 7)
    assert aa.quartiles([1, 2, 3]) is None
    assert aa.iqr([1, 2, 3, 4, 5, 6, 7, 8]) == 4
    assert aa.iqr([1]) is None


def test_returns():
    assert aa.simple_returns([100, 110, 99]) == pytest.approx([0.1, -0.1])
    assert aa.simple_returns([5]) == []
    assert aa.log_returns([1, math.e, math.e ** 3]) == pytest.approx([1.0, 2.0])


def test_sharpe_ratio():
    r = [0.01, 0.02, 0.03]
    expected = (0.02 - 0.02 / 252) / 0.01 * math.sqrt(252)
    assert aa.sharpe_ratio(r) == pytest.approx(expected)
    assert aa.sharpe_ratio(r, risk_free=0.0) == pytest.approx(0.02 / 0.01 * math.sqrt(252))
    assert aa.sharpe_ratio([0.01, 0.01]) is None and aa.sharpe_ratio([0.01]) is None
    assert aa.sharpe_ratio([]) is None


def test_sortino_guards_and_sign():
    assert aa.sortino_ratio([]) is None
    assert aa.sortino_ratio([0.01, 0.02]) is None                      # no downside observations
    assert aa.sortino_ratio([0.03, -0.01, 0.02]) > 0
    assert aa.sortino_ratio([-0.03, -0.01, -0.02]) < 0
    assert aa.sortino_ratio([0.05, -0.05], target=0.0) == pytest.approx(0.0)


@pytest.mark.xfail(strict=True, reason="sortino_ratio's downside deviation sums (target - x)^2 over ALL returns "
                   "including the above-target ones, instead of only the shortfalls (min(0, x - target)); "
                   "for [0.1, -0.1] the standard value is 0.0 / sqrt(0.01/2) = mean 0 -> use [0.3, -0.1]: "
                   "(advanced_analysis_demo.py:~89)")
def test_sortino_downside_deviation_ignores_gains():
    r = [0.3, -0.1]
    mean = 0.1
    downside = math.sqrt((0.1 ** 2) / 2)           # only the -0.1 shortfall counts
    assert aa.sortino_ratio(r) == pytest.approx(mean / downside * math.sqrt(252))


def test_max_drawdown_and_calmar():
    assert aa.max_drawdown([100, 120, 90, 110, 60]) == pytest.approx(-0.5)
    assert aa.max_drawdown([1, 2, 3]) == 0.0
    assert aa.max_drawdown([100, 80]) == pytest.approx(-0.2)
    prices = [100, 120, 90]
    r = aa.simple_returns(prices)
    assert aa.calmar_ratio(r, prices) == pytest.approx(aa.mean(r) * 252 / 0.25)
    assert aa.calmar_ratio(r, prices, annual_factor=12) == pytest.approx(aa.mean(r) * 12 / 0.25)
    assert aa.calmar_ratio([], prices) is None and aa.calmar_ratio(r, [1, 2, 3]) is None


def test_correlation_guards():
    assert aa.correlation([1, 2], [1, 2, 3]) is None and aa.correlation([1], [1]) is None
    assert aa.correlation([1, 1, 1], [1, 2, 3]) is None and aa.correlation([1, 2, 3], [4, 4, 4]) is None
    assert aa.correlation([1, 2, 3, 4], [4, 3, 2, 1]) < 0
    assert aa.correlation([1, 2, 3, 4], [2, 4, 6, 9]) > 0.7      # (biased low, see the xfail below)


@pytest.mark.xfail(strict=True, reason="correlation divides a population covariance (/n) by SAMPLE standard "
                   "deviations (n-1), so a series is not perfectly correlated with itself: "
                   "corr(x, x) == (n-1)/n instead of 1 (advanced_analysis_demo.py:~108)")
def test_correlation_of_series_with_itself_is_one():
    assert aa.correlation([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)


def test_rsi():
    up = list(range(100, 130))
    assert aa.rsi(up) == 100.0                                   # no losses
    assert aa.rsi(list(range(1, 11))) is None                       # fewer than `period` returns
    assert aa.rsi([100, 110] * 10) == pytest.approx(100 - 100 / (1 + 0.1 / (10 / 110)))
    down = list(range(130, 100, -1))
    assert aa.rsi(down) == pytest.approx(0.0)
    assert aa.rsi([100, 101, 100] + [100] * 20, period=14) is not None
    assert aa.rsi(list(range(100, 115)), period=14) == 100.0     # exactly 14 returns is enough
    assert aa.rsi(list(range(100, 114)), period=14) is None      # 13 returns is not


def test_momentum():
    assert aa.momentum([100, 110, 120], 2) == pytest.approx((120 - 110) / 110 * 100)
    assert aa.momentum([100, 110, 120], 3) == pytest.approx(20.0)
    assert aa.momentum([100, 110], 3) is None


def test_outlier_detectors():
    v = [10, 11, 9, 10, 10, 11, 9, 10, 100]
    assert aa.detect_outliers_zscore(v, 2.5) == [100]
    assert aa.detect_outliers_zscore(v, 3.0) == []
    assert aa.detect_outliers_zscore([5, 5, 5]) == []
    assert aa.detect_outliers_iqr(v) == [100]
    assert aa.detect_outliers_iqr([1, 2, 3]) == []
    assert aa.detect_outliers_iqr([1, 2, 3, 4, 5, 6, 7, 8]) == []


def test_generate_realistic_data(tmp_path):
    random.seed(1)
    f = tmp_path / "d.csv"
    aa.generate_realistic_data(str(f), num_stocks=3, num_days=10)
    rows = list(csv.DictReader(open(f)))
    assert len(rows) == 30 and [r["symbol"] for r in rows[::10]] == ["STOCK00", "STOCK01", "STOCK02"]
    assert list(rows[0]) == ["symbol", "date", "open", "high", "low", "close", "volume"]
    assert all(float(r["high"]) > float(r["low"]) for r in rows)
    assert all(100000 <= int(r["volume"]) <= 10000000 for r in rows)


def test_analyze_stock_data_report(tmp_path, capsys):
    random.seed(2)
    f = tmp_path / "d.csv"
    aa.generate_realistic_data(str(f), num_stocks=7, num_days=60)
    capsys.readouterr()
    aa.analyze_stock_data(str(f))
    out = capsys.readouterr().out
    assert out.count("PRICE ANALYSIS") == 5                      # only the first five stocks are detailed
    assert "STOCK04" in out and "📈 STOCK05" not in out
    assert "Total stocks analyzed: 7" in out and "Days of data: 60" in out
    assert "Sample correlation (STOCK00 vs STOCK01)" in out
    assert "Analysis complete" in out


def test_main(monkeypatch, tmp_path, capsys):
    random.seed(3)
    seen = {}
    real = aa.generate_realistic_data

    def gen(filename, num_stocks=10, num_days=252):
        seen["args"] = (filename, num_stocks, num_days)
        real(str(tmp_path / "x.csv"), 6, 40)

    monkeypatch.setattr(aa, "generate_realistic_data", gen)
    monkeypatch.setattr(aa, "analyze_stock_data", lambda f: None)
    aa.main()
    assert seen["args"] == ("/tmp/advanced_test_data.csv", 10, 252)
    assert "12+ statistical metrics" in capsys.readouterr().out
