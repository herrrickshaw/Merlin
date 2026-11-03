#!/usr/bin/env python3
"""
Forward-Looking 5-Year Stock Picks with Current ¥/USD Rate
Build live carry trade with current ¥161.29/USD rate (vs ¥100 historical)
"""

import copy
import json
from datetime import datetime

from forward_picks_data import (
    FX_TARGET_RATE, RATE_SCENARIOS, RECOMMENDATION_TEXT, SCENARIO_PRICE_KEY, STOCK_UNIVERSE,
)

STARTING_CAPITAL_USD = 620_556
UNHEDGED_SHARE = 0.75
HEDGED_SHARE = 0.25
TIER1_WEIGHTS = {'NVDA': 0.20, 'META': 0.18, 'MSFT': 0.17, 'GOOGL': 0.15, 'ASML': 0.13, 'AMZN': 0.10, 'NFLX': 0.07}
TIER2_WEIGHTS = {'TSM': 0.40, 'AAPL': 0.30, 'CRM': 0.30}
PRICE_TARGET_ORDER = ['NVDA', 'META', 'MSFT', 'GOOGL', 'ASML', 'AMZN', 'NFLX', 'TSM', 'AAPL', 'CRM']

class Forward5YearStockPicks:
    """Generate forward stock picks with current exchange rate"""

    def __init__(self):
        # CURRENT EXCHANGE RATE (as of today)
        self.current_rate = 161.29  # ¥ per USD
        self.historical_rate = 100.0  # Used in backtest
        self.rate_move = (self.current_rate - self.historical_rate) / self.historical_rate * 100

        print("\n⚠️  CRITICAL RATE CHANGE DETECTED")
        print("    Historical backtest rate:  ¥100.00 / USD")
        print(f"    CURRENT SPOT RATE:         ¥{self.current_rate:.2f} / USD")
        print(f"    Change:                    +{self.rate_move:.1f}% (yen WEAKER)")
        print("\n    → This is MASSIVE for carry trade! Yen is 61% weaker than backtest basis")

        self.rate_scenarios = copy.deepcopy(RATE_SCENARIOS)

        self.stock_universe = copy.deepcopy(STOCK_UNIVERSE)

    def calculate_fx_adjusted_returns(self, stock_ticker, price_2029, scenario):
        """Calculate returns with FX impact"""
        stock = self.stock_universe[stock_ticker]
        current_price = stock['current_price']
        stock_return = (price_2029 - current_price) / current_price

        # FX impact depends on scenario (unknown scenario names fall back to bullish)
        target = FX_TARGET_RATE.get(scenario, FX_TARGET_RATE['bullish'])
        fx_change = (target - self.current_rate) / self.current_rate
        fx_impact = stock['usd_exposure'] * fx_change

        total_return = (1 + stock_return) * (1 + fx_impact) - 1
        return {
            'stock_return': stock_return,
            'fx_impact': fx_impact,
            'total_return': total_return,
        }


    @staticmethod
    def _print_rate_analysis():
        """Section 1: print the current-rate analysis."""
        print("\n1️⃣  CURRENT RATE ANALYSIS")
        print("─" * 150)
        print("\nCurrent ¥/USD Rate:     ¥161.29 per USD")
        print("Backtest Basis Rate:    ¥100.00 per USD (historical)")
        print("Weaker by:              +61.29% (yen much weaker than historical)")
        print("\nImplication:")
        print("  ✓ Massive FX TAILWIND already baked in")
        print("  ✓ If yen stabilizes at ¥160 (base case): +$1.2M FX gain")
        print("  ✓ If yen strengthens to ¥140: -$2.6M FX loss (hedging needed!)")
        print("  ✓ If yen weakens to ¥178: +$4.2M FX gain (unhedged wins)")

    def _print_tier(self, allocation):
        """Print one allocation line per ticker; return the tier's total capital (USD)."""
        total = 0
        for ticker, alloc in allocation.items():
            stock = self.stock_universe[ticker]
            shares = alloc['capital'] / stock['current_price']
            print(f"{ticker:<6} ${alloc['capital']:>10,.0f}  "
                  f"({shares:>6.0f} shares @ ${stock['current_price']})  "
                  f"USD Exp: {stock['usd_exposure']:.0%}  "
                  f"Growth: {stock['growth_rate']:.0%}")
            total += alloc['capital']
        return total

    def _print_recommended_portfolio(self):
        """Section 2: print and return (tier1_allocation, tier2_allocation, total_tier1, total_tier2)."""
        print("\n\n2️⃣  RECOMMENDED PORTFOLIO (Current ¥161.29/USD)")
        print("─" * 150)

        print(f"\nCapital: ¥100,000,000 at ¥161.29/USD = ${100_000_000/161.29:,.0f} USD")
        print("Deployment: $620,556 USD equivalent\n")

        unhedged_capital = STARTING_CAPITAL_USD * UNHEDGED_SHARE
        hedged_capital = STARTING_CAPITAL_USD * HEDGED_SHARE

        print(f"TIER 1: UNHEDGED (75% = ${unhedged_capital:,.0f})")
        print("─" * 150)
        tier1_allocation = {t: {'pct': pct, 'capital': unhedged_capital * pct}
                            for t, pct in TIER1_WEIGHTS.items()}
        total_tier1 = self._print_tier(tier1_allocation)
        print(f"{'─' * 150}")
        print(f"Subtotal Unhedged: ${total_tier1:,.0f}")

        print(f"\n\nTIER 2: SWAPPED (25% = ${hedged_capital:,.0f})")
        print("─" * 150)
        tier2_allocation = {t: {'pct': pct, 'capital': hedged_capital * pct}
                            for t, pct in TIER2_WEIGHTS.items()}
        total_tier2 = self._print_tier(tier2_allocation)
        print(f"{'─' * 150}")
        print(f"Subtotal Swapped: ${total_tier2:,.0f}")
        return tier1_allocation, tier2_allocation, total_tier1, total_tier2

    def _print_price_targets(self):
        """Section 3: print 2029 price targets per scenario."""
        print("\n\n3️⃣  5-YEAR PRICE TARGETS (2025-2029)")
        print("─" * 150)

        print(f"\n{'Stock':<8} {'Current':<12} {'Conservative':<15} {'Base Case':<15} {'Bullish':<15}")
        print("─" * 150)

        for ticker in PRICE_TARGET_ORDER:
            stock = self.stock_universe[ticker]
            print(f"{ticker:<8} ${stock['current_price']:<11.2f} "
                  f"${stock['price_2029_conservative']:<14.2f} "
                  f"${stock['price_2029_base']:<14.2f} "
                  f"${stock['price_2029_bullish']:<14.2f}")

    def _scenario_returns(self, scenario, tier1_allocation, tier2_allocation):
        """Per-ticker FX-adjusted returns for one scenario; returns (scenario_returns, total_gain_usd)."""
        scenario_returns = {}
        total_portfolio_return = 0
        for _tier, positions in [('UNHEDGED', tier1_allocation), ('SWAPPED', tier2_allocation)]:
            for ticker, alloc in positions.items():
                stock = self.stock_universe[ticker]
                price_2029 = stock[SCENARIO_PRICE_KEY[scenario]]
                fx_analysis = self.calculate_fx_adjusted_returns(ticker, price_2029, scenario)
                scenario_returns[ticker] = {
                    'allocation': alloc['capital'],
                    'stock_return': fx_analysis['stock_return'] * 100,
                    'fx_impact': fx_analysis['fx_impact'] * 100,
                    'total_return': fx_analysis['total_return'] * 100,
                    'ending_value': alloc['capital'] * (1 + fx_analysis['total_return']),
                }
                total_portfolio_return += scenario_returns[ticker]['ending_value'] - alloc['capital']
        return scenario_returns, total_portfolio_return

    def _print_scenario(self, scenario, scenario_returns, total_portfolio_return, total_start):
        """Print the table and summary for one scenario."""
        ending_capital_usd = total_start + total_portfolio_return
        cagr = ((ending_capital_usd / STARTING_CAPITAL_USD) ** (1/5) - 1) * 100

        print(f"\n{'Stock':<8} {'Allocation':<12} {'Stock %':<10} {'FX %':<10} {'Total %':<10} {'Ending $':<15}")
        print("─" * 80)

        for ticker, returns in scenario_returns.items():
            print(f"{ticker:<8} ${returns['allocation']:>10,.0f} "
                  f"{returns['stock_return']:>8.1f}% {returns['fx_impact']:>8.1f}% "
                  f"{returns['total_return']:>8.1f}% ${returns['ending_value']:>13,.0f}")

        print(f"{'─' * 80}")
        print(f"Starting Capital (USD):        ${STARTING_CAPITAL_USD:,.0f}")
        print(f"Ending Capital (USD):          ${ending_capital_usd:,.0f}")
        print(f"Total Gain (USD):              ${total_portfolio_return:,.0f}")
        print(f"Total Return %:                {(total_portfolio_return/STARTING_CAPITAL_USD)*100:.1f}%")
        print(f"CAGR:                          {cagr:.2f}%")
        jpy = ending_capital_usd * self.rate_scenarios[scenario][2029]
        print(f"Ending Capital (JPY):          ¥{jpy:,.0f}")

    def _print_return_projections(self, tier1_allocation, tier2_allocation, total_start):
        """Section 4: return projections by FX scenario."""
        print("\n\n4️⃣  RETURN PROJECTIONS BY FX SCENARIO")
        print("─" * 150)
        for scenario in SCENARIO_PRICE_KEY:
            print(f"\n{scenario.upper().replace('_', ' ')} SCENARIO:")
            print("─" * 80)
            returns, gain = self._scenario_returns(scenario, tier1_allocation, tier2_allocation)
            self._print_scenario(scenario, returns, gain, total_start)

    def generate_picks(self):
        """Generate forward stock picks for next 5 years"""

        print("\n" + "="*150)
        print("FORWARD 5-YEAR STOCK PICKS (2025-2029)")
        print("Current Spot Rate: ¥161.29/USD | Carry Trade Optimized")
        print("="*150)

        self._print_rate_analysis()
        tier1_allocation, tier2_allocation, total_tier1, total_tier2 = self._print_recommended_portfolio()
        self._print_price_targets()
        self._print_return_projections(tier1_allocation, tier2_allocation, total_tier1 + total_tier2)

        print("\n\n5️⃣  RECOMMENDATION & EXECUTION PLAN")
        print("="*150)
        print(RECOMMENDATION_TEXT)

        return {
            'current_rate': self.current_rate,
            'tier1_allocation': tier1_allocation,
            'tier2_allocation': tier2_allocation,
            'rate_scenarios': self.rate_scenarios,
        }

    def export_results(self):
        """Export recommendations to files"""
        results = self.generate_picks()

        export_data = {
            'timestamp': datetime.now().isoformat(),
            'current_yen_usd_rate': self.current_rate,
            'capital_jpy': 100_000_000,
            'capital_usd': 100_000_000 / self.current_rate,
            'recommendations': {
                'tier1_unhedged': {k: {'allocation_usd': v['capital'], 'pct': v['pct']}
                                   for k, v in results['tier1_allocation'].items()},
                'tier2_swapped': {k: {'allocation_usd': v['capital'], 'pct': v['pct']}
                                  for k, v in results['tier2_allocation'].items()},
            },
            'rate_scenarios': results['rate_scenarios'],
        }

        with open('forward_stock_picks_2025_2029.json', 'w') as f:
            json.dump(export_data, f, indent=2)

        print("\n✅ Forward picks exported to forward_stock_picks_2025_2029.json")

# Main
if __name__ == "__main__":
    picker = Forward5YearStockPicks()
    picker.generate_picks()
    picker.export_results()
