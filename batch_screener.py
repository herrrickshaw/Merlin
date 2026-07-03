#!/usr/bin/env python3
"""
Batch Market Screener
Applies all 4-stage filters to entire market and identifies triple hits
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from data_fetcher import MarketDataFetcher, validate_data

# ─── Filter Implementations ────────────────────────────────────────────────

class StockFilters:
    """Apply all 4-stage filters to stock data"""

    @staticmethod
    def darvas_box(prices_df, volume_data):
        """Stage 1: Darvas Box Detection"""
        if len(prices_df) < 252:
            return None

        close = prices_df['close'].values
        volume = volume_data['volume']

        # 52-week high
        hi_52w = max(close[-252:])
        current = close[-1]

        # Percentage off high
        pct_off = ((hi_52w - current) / hi_52w) * 100 if hi_52w > 0 else 100

        # Volume check
        avg_vol_20d = np.mean(volume[-20:])
        current_vol = volume[-1]
        vol_mult = current_vol / avg_vol_20d if avg_vol_20d > 0 else 0

        # 200-day MA
        sma_200 = np.mean(close[-200:]) if len(close) >= 200 else np.mean(close)
        above_200ma = current > sma_200

        # Signal
        near_high = pct_off <= 10.0
        vol_ok = vol_mult >= 1.5

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
            'passed': score >= 7,  # Need 7+ for strong
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
    def chaikin_money_flow(volume_data, period=20):
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
            'passed': cmf > 0.05,  # Accumulation threshold
            'cmf_20': cmf,
            'status': 'STRONG_ACCUMULATION' if cmf > 0.25 else ('ACCUMULATION' if cmf > 0.05 else 'NEUTRAL'),
            'confidence': 0.95 if cmf > 0.25 else (0.75 if cmf > 0.05 else 0.5),
        }

# ─── Batch Screening Engine ────────────────────────────────────────────────

class BatchScreener:
    """Apply filters to entire market"""

    def __init__(self):
        self.filters = StockFilters()
        self.results = []

    def screen_stock(self, stock_data):
        """Apply all 4 stages to a single stock"""
        symbol = stock_data['symbol']

        # Validate data
        valid, msg = validate_data(stock_data)
        if not valid:
            return None

        prices_df = stock_data['prices']
        volumes = stock_data['volumes']
        fundamentals = stock_data['fundamentals']

        # Stage 1: Darvas Box
        darvas = self.filters.darvas_box(prices_df, volumes)
        if not darvas or not darvas['passed']:
            return None

        # Stage 2: Piotroski
        piotroski = self.filters.piotroski_score(fundamentals)
        if not piotroski or not piotroski['passed']:
            return None

        # Stage 3: Coffee Can
        coffee_can = self.filters.coffee_can_check(fundamentals)
        if not coffee_can or not coffee_can['passed']:
            return None

        # Stage 4: CMF Accumulation
        cmf = self.chaikin_money_flow(volumes)
        if not cmf or not cmf['passed']:
            return None

        # All stages passed - Triple Hit!
        result = {
            'symbol': symbol,
            'price': prices_df['close'].iloc[-1],
            'date_identified': prices_df['date'].iloc[-1],
            'darvas': darvas,
            'piotroski': piotroski,
            'coffee_can': coffee_can,
            'cmf': cmf,
            'market_cap': fundamentals.get('market_cap', 0) if fundamentals else 0,
            'pe_ratio': fundamentals.get('pe_ratio', 0) if fundamentals else 0,
        }

        return result

    def screen_market(self, market_data):
        """Screen all stocks in market"""
        self.results = []
        triple_hits = []

        total_stocks = sum(len(stocks) for stocks in market_data.values())
        processed = 0
        passed_stage1 = 0
        passed_stage2 = 0
        passed_stage3 = 0
        passed_stage4 = 0

        print("\n" + "="*80)
        print("🔍 SCREENING ENTIRE MARKET")
        print("="*80 + "\n")

        for exchange, stocks in market_data.items():
            print(f"Screening {exchange} ({len(stocks)} stocks)...")

            for stock_data in stocks:
                processed += 1

                if processed % 10 == 0:
                    print(f"  [{processed}/{total_stocks}] Processed: {passed_stage1}/{passed_stage2}/{passed_stage3}/{passed_stage4}")

                result = self.screen_stock(stock_data)

                # Track stage progression
                if stock_data['prices'] is not None:
                    darvas = self.filters.darvas_box(stock_data['prices'], stock_data['volumes'])
                    if darvas and darvas['passed']:
                        passed_stage1 += 1

                        piotroski = self.filters.piotroski_score(stock_data['fundamentals'])
                        if piotroski and piotroski['passed']:
                            passed_stage2 += 1

                            coffee_can = self.filters.coffee_can_check(stock_data['fundamentals'])
                            if coffee_can and coffee_can['passed']:
                                passed_stage3 += 1

                                cmf = self.chaikin_money_flow(stock_data['volumes'])
                                if cmf and cmf['passed']:
                                    passed_stage4 += 1

                if result:
                    triple_hits.append(result)
                    self.results.append(result)

        print(f"\n✅ Screening complete!")
        print(f"   Total processed: {total_stocks}")
        print(f"   Stage 1 (Darvas): {passed_stage1} ({passed_stage1/total_stocks*100:.1f}%)")
        print(f"   Stage 2 (Piotroski): {passed_stage2} ({passed_stage2/total_stocks*100:.1f}%)")
        print(f"   Stage 3 (Coffee Can): {passed_stage3} ({passed_stage3/total_stocks*100:.1f}%)")
        print(f"   Stage 4 (CMF): {passed_stage4} ({passed_stage4/total_stocks*100:.1f}%)")
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
    start_date = end_date - timedelta(days=252*2)  # 2 years for faster testing

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
