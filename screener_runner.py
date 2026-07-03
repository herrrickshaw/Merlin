#!/usr/bin/env python3
"""
Stock Screener Runner - OCaml-style strategies in Python
Demonstrates the OCaml screener logic by running it on test data
"""

import csv
import sys
from collections import defaultdict
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

@dataclass
class OHLCV:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class StockData:
    symbol: str
    market: str = ""
    ohlcv: List[OHLCV] = field(default_factory=list)
    fundamentals: Dict[str, Optional[float]] = field(default_factory=dict)

@dataclass
class Result:
    symbol: str
    strategy: str
    passed: bool
    score: Optional[float] = None
    metrics: Dict[str, str] = field(default_factory=dict)
    note: str = ""

def pct_change(new_val: Optional[float], old_val: Optional[float]) -> Optional[float]:
    """Calculate percentage change"""
    if new_val is None or old_val is None or old_val == 0:
        return None
    return ((new_val - old_val) / abs(old_val)) * 100

def cagr(latest: Optional[float], earliest: Optional[float], years: float) -> Optional[float]:
    """Calculate CAGR"""
    if not latest or not earliest or earliest <= 0 or years < 1:
        return None
    return (((latest / earliest) ** (1 / years)) - 1) * 100

def sma(closes: List[float], n: int) -> Optional[float]:
    """Simple moving average"""
    if len(closes) < n:
        return None
    return sum(closes[-n:]) / n

def high_52w(stock: StockData) -> Optional[float]:
    """52-week high"""
    if not stock.ohlcv:
        return None
    last_252 = stock.ohlcv[-252:] if len(stock.ohlcv) >= 252 else stock.ohlcv
    highs = [bar.high for bar in last_252]
    return max(highs) if highs else None

def ltp(stock: StockData) -> Optional[float]:
    """Last traded price"""
    return stock.ohlcv[-1].close if stock.ohlcv else None

def avg_volume_20d(stock: StockData) -> Optional[float]:
    """Average volume over 20 days"""
    if len(stock.ohlcv) < 20:
        return None
    vols = [bar.volume for bar in stock.ohlcv[-20:]]
    return sum(vols) / len(vols) if vols else None

# ────────────────────────────────────────────────────────────────────────────
# STRATEGIES
# ────────────────────────────────────────────────────────────────────────────

def darvas_screen(stock: StockData) -> Result:
    """Darvas Box: Price-volume breakout"""
    NEAR_HIGH_PCT = 10.0
    VOL_MULT = 1.5

    h52w = high_52w(stock)
    ltp_val = ltp(stock)
    avg_vol = avg_volume_20d(stock)

    if not h52w or not ltp_val or h52w <= 0:
        return Result(stock.symbol, "darvas", False, note="insufficient_data")

    off_high = ((h52w - ltp_val) / h52w) * 100
    near_high = off_high <= NEAR_HIGH_PCT

    vtoday = stock.ohlcv[-1].volume if stock.ohlcv else 0
    vmult = (vtoday / avg_vol) if avg_vol and avg_vol > 0 else 0
    vol_ok = vmult >= VOL_MULT

    passed = near_high and vol_ok

    return Result(
        stock.symbol,
        "darvas",
        passed,
        score=-off_high if off_high else None,
        metrics={
            "LTP": f"{ltp_val:.2f}",
            "High_52w": f"{h52w:.2f}",
            "Off_High%": f"{off_high:.1f}",
            "Vol_x20d": f"{vmult:.2f}",
        },
        note="BREAKOUT" if passed else ("near_high" if near_high else ""),
    )

def piotroski_screen(stock: StockData) -> Result:
    """Piotroski F-Score (9-point quality check)"""
    f = stock.fundamentals
    pts = 0
    checks = {}

    def add(name: str, cond: bool):
        nonlocal pts
        checks[name] = "1" if cond else "0"
        pts += 1 if cond else 0

    ni = f.get("net_income")
    roa = f.get("roa")
    roa_prev = f.get("roa_prev")
    cfo = f.get("cfo")
    lev = f.get("debt_to_assets")
    lev_prev = f.get("debt_to_assets_prev")
    cr = f.get("current_ratio")
    cr_prev = f.get("current_ratio_prev")
    sh = f.get("shares")
    sh_prev = f.get("shares_prev")
    gm = f.get("gross_margin")
    gm_prev = f.get("gross_margin_prev")
    at = f.get("asset_turnover")
    at_prev = f.get("asset_turnover_prev")

    add("ROA>0", roa is not None and roa > 0)
    add("CFO>0", cfo is not None and cfo > 0)
    add("dROA>0", roa is not None and roa_prev is not None and roa > roa_prev)
    add("Accrual", cfo is not None and ni is not None and cfo > ni)
    add("dLev<0", lev is not None and lev_prev is not None and lev < lev_prev)
    add("dCR>0", cr is not None and cr_prev is not None and cr > cr_prev)
    add("NoDilute", sh is not None and sh_prev is not None and sh <= sh_prev)
    add("dGM>0", gm is not None and gm_prev is not None and gm > gm_prev)
    add("dAT>0", at is not None and at_prev is not None and at > at_prev)

    passed = pts >= 7

    return Result(
        stock.symbol,
        "piotroski",
        passed,
        score=float(pts),
        metrics={**checks, "F_Score": str(pts)},
        note="strong" if passed else "",
    )

def coffee_can_screen(stock: StockData) -> Result:
    """Coffee Can Portfolio: High ROE + Revenue growth + Low debt"""
    f = stock.fundamentals

    roe = f.get("roe")
    revenue = f.get("revenue")
    revenue_5y = f.get("revenue_5y_ago")
    de = f.get("debt_to_equity")

    ROE_MIN = 15.0
    REV_GROWTH_MIN = 10.0
    DE_MAX = 1.0

    roe_ok = roe is not None and roe >= ROE_MIN
    rev_cagr = cagr(revenue, revenue_5y, 5)
    rev_ok = rev_cagr is not None and rev_cagr >= REV_GROWTH_MIN
    de_ok = de is not None and de <= DE_MAX

    passed = roe_ok and rev_ok and de_ok

    return Result(
        stock.symbol,
        "coffee_can",
        passed,
        score=roe,
        metrics={
            "ROE": f"{roe:.1f}" if roe else "N/A",
            "RevCAGR5y": f"{rev_cagr:.1f}" if rev_cagr else "N/A",
            "DE": f"{de:.2f}" if de else "N/A",
            "ROE>=15": "1" if roe_ok else "0",
            "RevCAGR>=10": "1" if rev_ok else "0",
            "DE<=1": "1" if de_ok else "0",
        },
        note="quality_compounder" if passed else "",
    )

def magic_formula_screen(stock: StockData) -> Result:
    """Magic Formula: High ROE + Positive Earnings Yield"""
    f = stock.fundamentals
    roe = f.get("roe")
    ey = f.get("earnings_yield")

    roe_ok = roe is not None and roe > 15.0
    ey_ok = ey is not None and ey > 0.0
    passed = roe_ok and ey_ok

    return Result(
        stock.symbol,
        "magic_formula",
        passed,
        score=ey,
        metrics={
            "ROE": f"{roe:.1f}" if roe else "N/A",
            "Earnings_Yield": f"{ey:.2f}%" if ey else "N/A",
            "ROE>15": "1" if roe_ok else "0",
            "EY>0": "1" if ey_ok else "0",
        },
        note="cheap_quality" if passed else "",
    )

def golden_crossover_screen(stock: StockData) -> Result:
    """Golden Crossover: 50-day MA > 200-day MA"""
    if len(stock.ohlcv) < 200:
        return Result(stock.symbol, "golden_crossover", False, note="insufficient_data")

    closes = [bar.close for bar in stock.ohlcv]
    sma_50 = sma(closes, 50)
    sma_200 = sma(closes, 200)

    if not sma_50 or not sma_200:
        return Result(stock.symbol, "golden_crossover", False, note="insufficient_data")

    passed = sma_50 > sma_200
    ratio = sma_50 / sma_200 if sma_200 > 0 else 0

    return Result(
        stock.symbol,
        "golden_crossover",
        passed,
        score=ratio,
        metrics={
            "SMA50": f"{sma_50:.2f}",
            "SMA200": f"{sma_200:.2f}",
            "Ratio": f"{ratio:.4f}",
        },
        note="bullish" if passed else "bearish",
    )

def screen_stock(stock: StockData) -> List[Result]:
    """Run all strategies on a stock"""
    return [
        darvas_screen(stock),
        piotroski_screen(stock),
        coffee_can_screen(stock),
        magic_formula_screen(stock),
        golden_crossover_screen(stock),
    ]

def screen_market(stocks: List[StockData]) -> List[Result]:
    """Screen entire market"""
    results = []
    for stock in stocks:
        results.extend(screen_stock(stock))
    return results

def rank_results(results: List[Result], strategy: str) -> List[Result]:
    """Rank results by strategy and score"""
    filtered = [r for r in results if r.strategy == strategy and r.passed]
    return sorted(filtered, key=lambda r: r.score if r.score else 0, reverse=True)

def load_csv_to_stocks(csv_file: str) -> List[StockData]:
    """Load CSV data into stock objects"""
    stocks_dict: Dict[str, StockData] = {}

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row.get('symbol')
            if not symbol:
                continue

            bar = OHLCV(
                date=row.get('date', ''),
                open=float(row.get('open', 0)),
                high=float(row.get('high', 0)),
                low=float(row.get('low', 0)),
                close=float(row.get('close', 0)),
                volume=float(row.get('volume', 0)),
            )

            if symbol not in stocks_dict:
                stocks_dict[symbol] = StockData(symbol=symbol)

            stocks_dict[symbol].ohlcv.append(bar)

            # Load fundamentals
            for key in ['roe', 'net_income', 'roa', 'roa_prev', 'cfo', 'debt_to_assets',
                       'debt_to_assets_prev', 'current_ratio', 'current_ratio_prev', 'shares',
                       'shares_prev', 'gross_margin', 'gross_margin_prev', 'asset_turnover',
                       'asset_turnover_prev', 'revenue', 'revenue_5y_ago', 'debt_to_equity',
                       'earnings_yield']:
                if key in row and row[key]:
                    try:
                        stocks_dict[symbol].fundamentals[key] = float(row[key])
                    except ValueError:
                        pass

    return list(stocks_dict.values())

def main():
    if len(sys.argv) < 2:
        print("Usage: python screener_runner.py <csv_file> [--strategy NAME] [--top N]")
        sys.exit(1)

    csv_file = sys.argv[1]
    strategy = None
    top_n = 10

    for i, arg in enumerate(sys.argv[2:]):
        if arg == "--strategy" and i + 3 < len(sys.argv):
            strategy = sys.argv[i + 3]
        elif arg == "--top" and i + 3 < len(sys.argv):
            top_n = int(sys.argv[i + 3])

    print(f"\n📊 Stock Screener — OCaml-style analysis in Python")
    print(f"   Loading: {csv_file}")

    stocks = load_csv_to_stocks(csv_file)
    print(f"   ✓ Loaded {len(stocks)} stocks")

    print(f"\n🔍 Running screening...")
    results = screen_market(stocks)
    print(f"   ✓ Generated {len(results)} results")

    strategies_found = set(r.strategy for r in results if r.passed)
    print(f"   ✓ Strategies: {', '.join(sorted(strategies_found))}")

    for strat in sorted(strategies_found):
        ranked = rank_results(results, strat)
        if ranked:
            print(f"\n{'='*70}")
            print(f"🏆 Top {min(top_n, len(ranked))} {strat.upper()} Results")
            print(f"{'='*70}")
            for i, r in enumerate(ranked[:top_n], 1):
                score_str = f"{r.score:.2f}" if r.score else "N/A"
                print(f"{i:2d}. {r.symbol:12s} | Score: {score_str:8s} | {r.note}")
                for k, v in list(r.metrics.items())[:4]:
                    print(f"    └─ {k:18s}: {v}")

    # Summary statistics
    print(f"\n{'='*70}")
    print("📈 Summary Statistics")
    print(f"{'='*70}")
    for strat in sorted(strategies_found):
        ranked = rank_results(results, strat)
        if ranked:
            avg_score = sum(r.score for r in ranked if r.score) / len([r for r in ranked if r.score])
            print(f"{strat:20s}: {len(ranked):3d} passes | avg score: {avg_score:6.2f}")

    # Multi-pass analysis
    print(f"\n{'='*70}")
    print("⚡ Multi-Pass Effectiveness (stocks passing multiple strategies)")
    print(f"{'='*70}")
    pass_counts = defaultdict(int)
    for result in results:
        if result.passed:
            pass_counts[result.symbol] += 1

    multi_pass = sorted(pass_counts.items(), key=lambda x: x[1], reverse=True)
    for symbol, count in multi_pass[:10]:
        strategies_passed = [r.strategy for r in results if r.symbol == symbol and r.passed]
        print(f"{symbol:12s}: {count} strategies | {', '.join(strategies_passed)}")

if __name__ == "__main__":
    main()
