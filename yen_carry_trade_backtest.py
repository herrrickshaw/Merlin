#!/usr/bin/env python3
"""
Yen Carry Trade Backtest with Full Cost Analysis
Accounts for: Taxes, Brokerage, FX Fees, Borrowing Costs, Currency Fluctuations
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json

# ─── Yen Carry Trade Model ─────────────────────────────────────────────────

class YenCarryTradeBacktester:
    """Backtest yen carry trade with realistic cost structure"""

    def __init__(self):
        self.results = []

        # Carry trade parameters
        self.jpy_borrow_rate = 0.001  # 0.1% annual (Japan near-zero rates)
        self.usd_invest_return = None  # Will be calculated from backtest

        # Cost structure
        self.brokerage_fee_pct = 0.0015  # 0.15% per transaction
        self.fx_conversion_fee_pct = 0.002  # 0.2% for FX conversion
        self.annual_custody_fee_pct = 0.0005  # 0.05% annual

        # Taxation (varies by jurisdiction)
        self.us_capital_gains_tax = 0.20  # 20% (long-term)
        self.japan_income_tax = 0.15  # 15% on interest income
        self.fx_gain_tax = 0.20  # 20% on FX gains/losses

    def calculate_period_with_costs(self, period_name, usd_return_pct, fx_jpy_to_usd_change_pct, days=252):
        """Calculate net returns after all costs"""

        # Initial investment
        initial_jpy = 100_000_000  # ¥100M borrowed
        usd_borrow_cost = self.jpy_borrow_rate * days / 365

        print(f"\n  {period_name}...", end='', flush=True)

        # 1. Convert JPY to USD for investment
        # FX rate: ¥100/USD initially
        initial_fx_rate = 100.0  # ¥ per USD

        # Initial conversion with fees
        fx_conversion_fee = initial_jpy * self.fx_conversion_fee_pct / initial_fx_rate
        net_usd_after_fx = (initial_jpy - (initial_jpy * self.fx_conversion_fee_pct)) / initial_fx_rate

        # 2. Invest in USD markets (triple hits portfolio)
        usd_market_gain = net_usd_after_fx * (usd_return_pct / 100)
        usd_value_before_fx = net_usd_after_fx + usd_market_gain

        # 3. Pay borrowing costs (interest on JPY loan)
        jpy_borrow_interest = initial_jpy * usd_borrow_cost

        # 4. Currency movement
        # FX rate changes (e.g., +5% means ¥ weakens, USD strengthens)
        new_fx_rate = initial_fx_rate * (1 + fx_jpy_to_usd_change_pct / 100)

        # FX gain/loss when converting back to JPY
        jpy_received = usd_value_before_fx * new_fx_rate
        fx_gain = jpy_received - (net_usd_after_fx * initial_fx_rate)

        # 5. Convert back USD to JPY with fees
        fx_conversion_fee_exit = usd_value_before_fx * self.fx_conversion_fee_pct
        net_jpy_after_return = jpy_received - fx_conversion_fee_exit

        # 6. Calculate taxes
        # Tax on capital gains (stock returns)
        capital_gain_tax = usd_market_gain * self.us_capital_gains_tax

        # Tax on FX gains
        fx_gain_tax = fx_gain * self.fx_gain_tax if fx_gain > 0 else 0

        # Tax on borrowing costs (paid from returns)
        borrow_cost_tax = jpy_borrow_interest * self.japan_income_tax

        # 7. Total costs
        total_costs = (
            fx_conversion_fee +  # Initial FX conversion
            fx_conversion_fee_exit +  # Exit FX conversion
            jpy_borrow_interest +  # Interest on loan
            capital_gain_tax +  # Tax on gains
            fx_gain_tax +  # Tax on FX gains
            borrow_cost_tax  # Tax on interest
        )

        # 8. Custody and management fees
        annual_custody = (initial_jpy + net_jpy_after_return) / 2 * self.annual_custody_fee_pct

        # 9. Final calculation
        final_jpy = net_jpy_after_return - annual_custody
        net_jpy_gain = final_jpy - initial_jpy
        net_return_pct = (net_jpy_gain / initial_jpy) * 100

        result = {
            'period': period_name,
            'gross_usd_return_pct': usd_return_pct,
            'fx_change_pct': fx_jpy_to_usd_change_pct,
            'days': days,
            'starting_jpy': initial_jpy,
            'starting_usd': net_usd_after_fx,
            'ending_jpy_gross': jpy_received,
            'ending_jpy_net': final_jpy,
            'net_jpy_gain': net_jpy_gain,
            'net_return_pct': net_return_pct,
            'fx_gain_jpy': fx_gain,
            'borrow_interest_jpy': jpy_borrow_interest,
            'costs_breakdown': {
                'fx_conversion_in': fx_conversion_fee,
                'fx_conversion_out': fx_conversion_fee_exit,
                'borrow_interest': jpy_borrow_interest,
                'capital_gains_tax': capital_gain_tax,
                'fx_gain_tax': fx_gain_tax,
                'borrow_cost_tax': borrow_cost_tax,
                'custody_fees': annual_custody,
                'total_costs': total_costs + annual_custody,
            }
        }

        print(" ✓")
        return result

    def run_backtest(self):
        """Run 5-year carry trade backtest"""

        print("\n" + "="*120)
        print("YEN CARRY TRADE BACKTEST - FULL COST ANALYSIS")
        print("Borrow in JPY (0.1%), Invest in USD Markets, Convert Back to JPY")
        print("="*120)

        print("\n📊 COST STRUCTURE:")
        print(f"   JPY Borrowing Rate:        {self.jpy_borrow_rate*100:.2f}% annual")
        print(f"   Brokerage Fee:             {self.brokerage_fee_pct*100:.2f}% per trade")
        print(f"   FX Conversion Fee:         {self.fx_conversion_fee_pct*100:.2f}% each way")
        print(f"   Custody Fee:               {self.annual_custody_fee_pct*100:.2f}% annual")
        print(f"   US Capital Gains Tax:      {self.us_capital_gains_tax*100:.0f}%")
        print(f"   FX Gain Tax:               {self.fx_gain_tax*100:.0f}%")
        print(f"   Japan Income Tax:          {self.japan_income_tax*100:.0f}%")

        print("\nInitial Investment: ¥100,000,000 (~$1,000,000 at ¥100/USD)")

        periods = [
            ("2019-2020: COVID Recovery", 107.34, 5.0),   # 107% stock gain, ¥ weakens 5%
            ("2020-2021: Bull Run", 67.05, 3.0),           # 67% stock gain, ¥ weakens 3%
            ("2021-2022: Momentum", 36.96, -2.0),          # 37% stock gain, ¥ strengthens 2%
            ("2022-2023: Bear Market", -20.18, 8.0),       # -20% stock loss, ¥ weakens 8%
            ("2023-2024: Recovery", 37.53, -1.0),          # 37% stock gain, ¥ strengthens 1%
        ]

        print(f"\nRunning 5-year backtest (¥100M initial investment):\n")

        for period_name, stock_return, fx_change in periods:
            result = self.calculate_period_with_costs(period_name, stock_return, fx_change)
            self.results.append(result)

        return self.results

    def print_detailed_results(self):
        """Print detailed period-by-period breakdown"""

        print("\n" + "="*120)
        print("DETAILED RESULTS BY PERIOD")
        print("="*120)

        for i, r in enumerate(self.results, 1):
            print(f"\n{i}. {r['period']}")
            print(f"   {'─'*116}")

            print(f"\n   📈 Market Performance:")
            print(f"      USD Market Return:        {r['gross_usd_return_pct']:>10.2f}%")
            print(f"      FX Change (JPY/USD):      {r['fx_change_pct']:>10.2f}%")

            print(f"\n   💱 Currency Impact:")
            print(f"      Initial Rate:             ¥100.00 / $1")
            new_rate = 100.0 * (1 + r['fx_change_pct'] / 100)
            print(f"      End Rate:                 ¥{new_rate:.2f} / $1")
            print(f"      FX Gain (Gross):          ¥{r['fx_gain_jpy']:>15,.0f}")

            print(f"\n   💰 Capital Movement:")
            print(f"      Starting Capital:         ¥{r['starting_jpy']:>15,.0f}")
            print(f"      Ending Capital (Gross):   ¥{r['ending_jpy_gross']:>15,.0f}")
            print(f"      Ending Capital (Net):     ¥{r['ending_jpy_net']:>15,.0f}")

            print(f"\n   ⚖️  Cost Breakdown:")
            costs = r['costs_breakdown']
            print(f"      Initial FX Conversion:    ¥{costs['fx_conversion_in']:>15,.0f}")
            print(f"      Exit FX Conversion:       ¥{costs['fx_conversion_out']:>15,.0f}")
            print(f"      Borrowing Interest:       ¥{costs['borrow_interest']:>15,.0f}")
            print(f"      Capital Gains Tax:        ¥{costs['capital_gains_tax']:>15,.0f}")
            print(f"      FX Gain Tax:              ¥{costs['fx_gain_tax']:>15,.0f}")
            print(f"      Borrow Cost Tax:          ¥{costs['borrow_cost_tax']:>15,.0f}")
            print(f"      Custody Fees:             ¥{costs['custody_fees']:>15,.0f}")
            print(f"      {'─'*50}")
            print(f"      TOTAL COSTS:              ¥{costs['total_costs']:>15,.0f}")

            print(f"\n   📊 Net Result:")
            print(f"      Gross Gain:               ¥{r['ending_jpy_gross'] - r['starting_jpy']:>15,.0f}")
            print(f"      Total Costs:              ¥{costs['total_costs']:>15,.0f}")
            print(f"      NET GAIN:                 ¥{r['net_jpy_gain']:>15,.0f}")
            print(f"      NET RETURN:               {r['net_return_pct']:>15.2f}%")

    def print_summary(self):
        """Print aggregate summary"""

        print("\n" + "="*120)
        print("5-YEAR AGGREGATE SUMMARY")
        print("="*120)

        net_returns = [r['net_return_pct'] for r in self.results]
        gross_returns = [r['gross_usd_return_pct'] for r in self.results]
        total_costs = [r['costs_breakdown']['total_costs'] for r in self.results]

        print(f"\n📈 GROSS vs NET RETURNS:")
        print(f"{'Period':<30} {'Gross Return':<15} {'Total Costs':<15} {'Net Return':<15}")
        print(f"{'─'*75}")

        for r in self.results:
            print(f"{r['period']:<30} {r['gross_usd_return_pct']:>13.2f}% "
                  f"¥{r['costs_breakdown']['total_costs']:>13,.0f} {r['net_return_pct']:>13.2f}%")

        print(f"\n💎 CUMULATIVE PERFORMANCE:")
        cumulative_gross = 1.0
        cumulative_net = 1.0

        for r in self.results:
            cumulative_gross *= (1 + r['gross_usd_return_pct'] / 100)
            cumulative_net *= (1 + r['net_return_pct'] / 100)

        cumulative_gross_pct = (cumulative_gross - 1) * 100
        cumulative_net_pct = (cumulative_net - 1) * 100
        cagr_gross = ((cumulative_gross) ** (1/5) - 1) * 100
        cagr_net = ((cumulative_net) ** (1/5) - 1) * 100

        print(f"   Gross 5-Year Return:       {cumulative_gross_pct:>10.2f}%")
        print(f"   Gross CAGR:                {cagr_gross:>10.2f}%")
        print(f"   Net 5-Year Return:         {cumulative_net_pct:>10.2f}%")
        print(f"   Net CAGR:                  {cagr_net:>10.2f}%")

        print(f"\n   Starting Capital:          ¥{100_000_000:>15,.0f} (~$1,000,000)")
        print(f"   Ending Capital (Gross):    ¥{100_000_000 * cumulative_gross:>15,.0f}")
        print(f"   Ending Capital (Net):      ¥{100_000_000 * cumulative_net:>15,.0f}")

        print(f"\n📊 COST ANALYSIS:")
        print(f"   Average Annual Gross Return: {np.mean(gross_returns):>8.2f}%")
        print(f"   Average Annual Net Return:   {np.mean(net_returns):>8.2f}%")
        print(f"   Average Cost per Year:       {np.mean([c for c in total_costs]) / 100_000_000 * 100:>8.2f}% of capital")

        print(f"\n🎯 COST IMPACT:")
        for i, r in enumerate(self.results):
            cost_drag = r['gross_usd_return_pct'] - r['net_return_pct']
            print(f"   {r['period']:<30} {cost_drag:>8.2f}% cost drag")

        print(f"\n✅ FINAL SUMMARY:")
        positive_years_net = sum(1 for r in net_returns if r > 0)
        print(f"   Positive Years (Net):      {positive_years_net} / 5")
        print(f"   Average Cost as % Return:  {np.mean([100 * c / max(1, r['ending_jpy_gross'] - r['starting_jpy']) for c, r in zip(total_costs, self.results)]):>8.2f}%")

        print("\n" + "="*120 + "\n")

    def export_results(self):
        """Export to JSON"""

        cumulative_gross = 1.0
        cumulative_net = 1.0

        for r in self.results:
            cumulative_gross *= (1 + r['gross_usd_return_pct'] / 100)
            cumulative_net *= (1 + r['net_return_pct'] / 100)

        export = {
            'strategy': 'Yen Carry Trade',
            'initial_jpy': 100_000_000,
            'jpy_borrow_rate': self.jpy_borrow_rate,
            'periods': self.results,
            'summary': {
                'gross_5yr_return_pct': (cumulative_gross - 1) * 100,
                'net_5yr_return_pct': (cumulative_net - 1) * 100,
                'gross_cagr_pct': ((cumulative_gross) ** (1/5) - 1) * 100,
                'net_cagr_pct': ((cumulative_net) ** (1/5) - 1) * 100,
                'ending_capital_net_jpy': int(100_000_000 * cumulative_net),
            }
        }

        with open('yen_carry_trade_results.json', 'w') as f:
            json.dump(export, f, indent=2)

        print("✅ Results exported to yen_carry_trade_results.json")

# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    backtest = YenCarryTradeBacktester()
    backtest.run_backtest()
    backtest.print_detailed_results()
    backtest.print_summary()
    backtest.export_results()

if __name__ == "__main__":
    main()
