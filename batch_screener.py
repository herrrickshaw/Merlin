#!/usr/bin/env python3
"""
Batch Market Screener
Applies all 4-stage filters to entire market and identifies triple hits
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from data_fetcher import MarketDataFetcher, validate_data

# ─── Thresholds ────────────────────────────────────────────────────────────

YEAR_DAYS = 252                 # trading days in a year (52-week window)
SMA_LONG_DAYS = 200
VOLUME_AVG_DAYS = 20
NEAR_HIGH_PCT = 10.0            # Darvas: within 10% of the 52-week high
VOLUME_MULT_MIN = 1.5           # Darvas: today's volume vs 20-day average
PIOTROSKI_STRONG = 7            # Piotroski: points needed to pass
CMF_PERIOD = 20
CMF_ACCUMULATION = 0.05         # CMF above this = accumulation
CMF_STRONG = 0.25
LOOKBACK_DAYS_QUICK = YEAR_DAYS * 2   # history window used by main()

# ─── Filter Implementations ────────────────────────────────────────────────

class StockFilters:
    """Apply all 4-stage filters to stock data"""

    @staticmethod
    def darvas_box(prices_df, volume_data):
        """Stage 1: Darvas Box Detection"""
        if len(prices_df) < YEAR_DAYS:
            return None

        close = prices_df['close'].values
        volume = volume_data['volume']

        # 52-week high
        hi_52w = max(close[-YEAR_DAYS:])
        current = close[-1]

        # Percentage off high
        pct_off = ((hi_52w - current) / hi_52w) * 100 if hi_52w > 0 else 100

        # Volume check
        avg_vol_20d = np.mean(volume[-VOLUME_AVG_DAYS:])
        current_vol = volume[-1]
        vol_mult = current_vol / avg_vol_20d if avg_vol_20d > 0 else 0

        # 200-day MA
        sma_200 = np.mean(close[-SMA_LONG_DAYS:]) if len(close) >= SMA_LONG_DAYS else np.mean(close)
        above_200ma = current > sma_200

        # Signal
        near_high = pct_off <= NEAR_HIGH_PCT
        vol_ok = vol_mult >= VOLUME_MULT_MIN

        passed = near_high and vol_ok and above_200ma

        return {
            'passed': passed,
            'pct_off_high': pct_off,
            'current_price': current,
            '52w_high': hi_52w,
            'vol_mult': vol_mult,
            'above_200ma': above_200ma,
            'score': max(0, 10 - pct_off) if passed else 0,  # Score 0-10
        }

    @staticmethod
    def piotroski_score(fundamentals):
        """Stage 2: Piotroski F-Score (0-9)"""
        if not fundamentals:
            return None

        score = 0

        # Profitability metrics (3 points)
        if fundamentals.get('net_income', 0) > 0:
            score += 1
        if fundamentals.get('operating_cash_flow', 0) > 0:
            score += 1
        if fundamentals.get('roe', 0) and fundamentals.get('roe') > 0:
            score += 1

        # Leverage/Liquidity (3 points)
        if fundamentals.get('debt_to_equity', 0) and fundamentals.get('debt_to_equity') < 1.0:
            score += 1
        if fundamentals.get('current_ratio', 0) and fundamentals.get('current_ratio') > 1.5:
            score += 1
        if fundamentals.get('revenue', 0) > 0:
            score += 1

        # Efficiency (3 points)
        if fundamentals.get('profit_margin', 0) and fundamentals.get('profit_margin') > 0.05:
            score += 1
        if fundamentals.get('roa', 0) and fundamentals.get('roa') > 0:
            score += 1
        if fundamentals.get('free_cash_flow', 0) and fundamentals.get('free_cash_flow') > 0:
            score += 1

        return {
            'passed': score >= PIOTROSKI_STRONG,  # Need 7+ for strong
            'score': score,
            'profitability': score >= 1,
            'leverage_ok': score >= 4,
            'efficiency': score >= 7,
        }

    @staticmethod
    def coffee_can_check(fundamentals):
        """Stage 3: Coffee Can Portfolio Quality"""
        if not fundamentals:
            return None

        passed = True
        reasons = []

        # Revenue growth (need positive)
        if fundamentals.get('revenue', 0) <= 0:
            passed = False
            reasons.append("No revenue")

        # Profitability (positive net income)
        if fundamentals.get('net_income', 0) <= 0:
            passed = False
            reasons.append("Not profitable")

        # FCF positive
        if fundamentals.get('free_cash_flow', 0) <= 0:
            passed = False
            reasons.append("Negative FCF")

        # Reasonable valuation
        pe = fundamentals.get('pe_ratio', 0)
        if pe and (pe <= 0 or pe > 50):
            passed = False
            reasons.append("Valuation concern")

        # Debt reasonable
        if fundamentals.get('debt_to_equity', 0) and fundamentals.get('debt_to_equity') > 2.0:
            passed = False
            reasons.append("High debt")

        return {
            'passed': passed,
            'reasons': reasons,
            'profitability': fundamentals.get('net_income', 0) > 0,
            'cash_generation': fundamentals.get('free_cash_flow', 0) > 0,
            'reasonable_valuation': pe and 0 < pe <= 50,
        }

    @staticmethod
    def chaikin_money_flow(volume_data, period=CMF_PERIOD):
        """Stage 4: Chaikin Money Flow (Accumulation Detection)"""
        if not volume_data or len(volume_data['close']) < period:
            return None

        close = volume_data['close'][-period:]
        high = volume_data['high'][-period:]
        low = volume_data['low'][-period:]
        volume = volume_data['volume'][-period:]

        mf_values = []
        for i in range(len(close)):
            hl_diff = high[i] - low[i]
            if hl_diff == 0:
                mf_mult = 0
            else:
                mf_mult = ((close[i] - low[i]) - (high[i] - close[i])) / hl_diff

            mf_values.append(mf_mult * volume[i])

        total_mf = sum(mf_values)
        total_vol = sum(volume)

        if total_vol == 0:
            return None

        cmf = total_mf / total_vol

        return {
            'passed': cmf > CMF_ACCUMULATION,  # Accumulation threshold
            'cmf_20': cmf,
            'status': ('STRONG_ACCUMULATION' if cmf > CMF_STRONG
                       else 'ACCUMULATION' if cmf > CMF_ACCUMULATION else 'NEUTRAL'),
            'confidence': 0.95 if cmf > CMF_STRONG else (0.75 if cmf > CMF_ACCUMULATION else 0.5),
        }

# ─── Batch Screening Engine ────────────────────────────────────────────────

class BatchScreener:
    """Apply filters to entire market"""

    def __init__(self):
        self.filters = StockFilters()
        self.results = []

    def _run_stages(self, stock_data):
        """Run the four stages in order, stopping at the first failure.

        Returns (stages_passed, details) where details maps stage name to its
        result dict; ``stages_passed == 4`` means a triple hit.
        """
        if stock_data['prices'] is None:
            return 0, {}

        details = {}
        steps = (
            ('darvas', lambda: self.filters.darvas_box(stock_data['prices'], stock_data['volumes'])),
            ('piotroski', lambda: self.filters.piotroski_score(stock_data['fundamentals'])),
            ('coffee_can', lambda: self.filters.coffee_can_check(stock_data['fundamentals'])),
            ('cmf', lambda: self.filters.chaikin_money_flow(stock_data['volumes'])),
        )
        for name, run in steps:
            outcome = run()
            if not outcome or not outcome['passed']:
                break
            details[name] = outcome
        return len(details), details

    @staticmethod
    def _build_result(stock_data, details):
        """Assemble the triple-hit record from the four stage outputs."""
        prices_df = stock_data['prices']
        fundamentals = stock_data['fundamentals']
        return {
            'symbol': stock_data['symbol'],
            'price': prices_df['close'].iloc[-1],
            'date_identified': prices_df['date'].iloc[-1],
            'darvas': details['darvas'],
            'piotroski': details['piotroski'],
            'coffee_can': details['coffee_can'],
            'cmf': details['cmf'],
            'market_cap': fundamentals.get('market_cap', 0) if fundamentals else 0,
            'pe_ratio': fundamentals.get('pe_ratio', 0) if fundamentals else 0,
        }

    def screen_stock(self, stock_data):
        """Apply all 4 stages to a single stock; the result dict, or None if any stage fails"""
        valid, _msg = validate_data(stock_data)
        if not valid:
            return None

        stages_passed, details = self._run_stages(stock_data)
        if stages_passed < 4:
            return None
        return self._build_result(stock_data, details)

    def screen_market(self, market_data):
        """Screen all stocks in market"""
        self.results = []
        triple_hits = []

        total_stocks = sum(len(stocks) for stocks in market_data.values())
        processed = 0
        stage_counts = [0, 0, 0, 0]   # stocks passing stage 1..4

        print("\n" + "="*80)
        print("🔍 SCREENING ENTIRE MARKET")
        print("="*80 + "\n")

        for exchange, stocks in market_data.items():
            print(f"Screening {exchange} ({len(stocks)} stocks)...")

            for stock_data in stocks:
                processed += 1

                if processed % 10 == 0:
                    print(f"  [{processed}/{total_stocks}] Processed: "
                          f"{stage_counts[0]}/{stage_counts[1]}/{stage_counts[2]}/{stage_counts[3]}")

                stages_passed, details = self._run_stages(stock_data)
                for i in range(stages_passed):
                    stage_counts[i] += 1

                valid, _msg = validate_data(stock_data)
                if valid and stages_passed == 4:
                    result = self._build_result(stock_data, details)
                    triple_hits.append(result)
                    self.results.append(result)

        labels = ("Darvas", "Piotroski", "Coffee Can", "CMF")
        print("\n✅ Screening complete!")
        print(f"   Total processed: {total_stocks}")
        for n, (label, count) in enumerate(zip(labels, stage_counts), 1):
            print(f"   Stage {n} ({label}): {count} ({count/total_stocks*100:.1f}%)")
        print(f"\n🎯 TRIPLE HITS FOUND: {len(triple_hits)}")

        return triple_hits

    def get_results_dataframe(self):
        """Convert results to DataFrame for analysis"""
        if not self.results:
            return None

        data = []
        for result in self.results:
            data.append({
                'Symbol': result['symbol'],
                'Price': result['price'],
                'Date': result['date_identified'],
                'Piotroski': result['piotroski']['score'],
                'CMF': result['cmf']['cmf_20'],
                'CMF_Status': result['cmf']['status'],
                'P/E': result['pe_ratio'],
                'Market_Cap': result['market_cap'],
            })

        return pd.DataFrame(data)

# ─── Main Test ────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*80)
    print("BATCH MARKET SCREENER - Real Data Analysis")
    print("="*80)

    # Fetch market data
    fetcher = MarketDataFetcher()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS_QUICK)  # 2 years for faster testing

    print(f"\nFetching data from {start_date.date()} to {end_date.date()}")

    market_data = fetcher.fetch_market_data(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        markets=['USA']  # Start with USA for faster testing
    )

    # Screen market
    screener = BatchScreener()
    triple_hits = screener.screen_market(market_data)

    # Export results
    print("\n" + "="*80)
    print("📊 RESULTS")
    print("="*80 + "\n")

    if triple_hits:
        # Sort by Piotroski score
        triple_hits_sorted = sorted(triple_hits, key=lambda x: x['piotroski']['score'], reverse=True)

        print("Top 10 Triple Hits (sorted by Piotroski score):\n")
        print(f"{'Symbol':<10} {'Price':<10} {'Piotroski':<12} {'CMF':<10} {'Status':<20}")
        print("-" * 70)

        for hit in triple_hits_sorted[:10]:
            print(f"{hit['symbol']:<10} ${hit['price']:<9.2f} {hit['piotroski']['score']:<12} "
                  f"{hit['cmf']['cmf_20']:<10.4f} {hit['cmf']['status']:<20}")

        # Export to CSV
        df = screener.get_results_dataframe()
        if df is not None:
            csv_file = 'triple_hits_results.csv'
            df.to_csv(csv_file, index=False)
            print(f"\n✅ Results exported to {csv_file}")

    return triple_hits

if __name__ == "__main__":
    main()
