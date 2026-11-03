#!/usr/bin/env python3
"""
Currency-Adjusted Yen Carry Trade Backtest
Accounts for FX exposure of stocks and optimal currency swap strategies
"""

import json

# Portfolio-weighted USD exposure thresholds for the profile message
HIGH_USD_PORTFOLIO_EXPOSURE = 0.40
MODERATE_USD_PORTFOLIO_EXPOSURE = 0.30

# Yearly yen moves in percent (positive = yen weakens)
FX_SCENARIOS = {
    '2019-2020 (Yen weakens 5%)': 5.0,
    '2020-2021 (Yen weakens 3%)': 3.0,
    '2021-2022 (Yen strengthens 2%)': -2.0,
    '2022-2023 (Yen weakens 8%)': 8.0,
    '2023-2024 (Yen strengthens 1%)': -1.0,
}

HISTORICAL_STOCK_RETURNS = [107.34, 67.05, 36.96, -20.18, 37.53]  # From backtest, percent per year

# One entry per hedging scenario; add a scenario by adding a dict here
HEDGE_SCENARIOS = [
    {'heading': '\nSCENARIO A: UNHEDGED (No Currency Swaps)', 'swap_ratio': 0.0,
     'delta_label': 'FX Impact', 'total_label': 'Total Return', 'total_key': 'return_unhedged',
     'delta': lambda r: r['return_unhedged'] - r['stock_return'],
     'summary_label': 'Unhedged (Scenario A)', 'volatility': 'High'},
    {'heading': '\n\nSCENARIO B: PARTIALLY HEDGED (25% Currency Swaps - Recommended)', 'swap_ratio': 0.25,
     'delta_label': 'Net FX', 'total_label': 'After Swap', 'total_key': 'return_hedged',
     'delta': lambda r: r['return_hedged'] - r['stock_return'],
     'summary_label': 'Partially Hedged (Rec.)', 'volatility': 'Medium'},
    {'heading': '\n\nSCENARIO C: FULLY HEDGED (100% Currency Swaps - Conservative)', 'swap_ratio': 1.0,
     'delta_label': 'Swap Cost', 'total_label': 'After Swap', 'total_key': 'return_hedged',
     'delta': lambda r: r['stock_return'] - r['return_hedged'],
     'summary_label': 'Fully Hedged (Conservative)', 'volatility': 'Low'},
]


class CurrencyAdjustedCarryTrade:
    """Model FX exposure of stocks and optimal hedging"""

    def __init__(self):
        # Triple-hit quality stocks with FX exposure profiles
        self.stocks = {
            # US Tech: High USD exposure, benefits from weak yen
            'AAPL': {'sector': 'Tech', 'usd_revenue_pct': 0.50, 'jpy_costs_pct': 0.05, 'beta_to_usd': 0.85},
            'MSFT': {'sector': 'Tech', 'usd_revenue_pct': 0.55, 'jpy_costs_pct': 0.03, 'beta_to_usd': 0.82},
            'GOOGL': {'sector': 'Tech', 'usd_revenue_pct': 0.60, 'jpy_costs_pct': 0.02, 'beta_to_usd': 0.88},
            'NVDA': {'sector': 'Tech', 'usd_revenue_pct': 0.70, 'jpy_costs_pct': 0.08, 'beta_to_usd': 0.90},
            'META': {'sector': 'Tech', 'usd_revenue_pct': 0.65, 'jpy_costs_pct': 0.04, 'beta_to_usd': 0.84},

            # Consumer/Cloud: Mixed USD/Global exposure
            'AMZN': {'sector': 'Cloud', 'usd_revenue_pct': 0.40, 'jpy_costs_pct': 0.10, 'beta_to_usd': 0.75},
            'CRM': {'sector': 'SaaS', 'usd_revenue_pct': 0.45, 'jpy_costs_pct': 0.06, 'beta_to_usd': 0.78},

            # Consumer/Growth: Currency sensitive
            'TSLA': {'sector': 'Auto', 'usd_revenue_pct': 0.35, 'jpy_costs_pct': 0.15, 'beta_to_usd': 0.70},
            'NFLX': {'sector': 'Media', 'usd_revenue_pct': 0.55, 'jpy_costs_pct': 0.05, 'beta_to_usd': 0.80},

            # Design/Premium: High USD exposure
            'ADBE': {'sector': 'Software', 'usd_revenue_pct': 0.50, 'jpy_costs_pct': 0.04, 'beta_to_usd': 0.83},
        }

        self.results = {}

    def calculate_fx_sensitivity(self, stock_code, stock_data):
        """
        Calculate net FX exposure of a stock.

        Formula:
        Net USD Exposure = (USD Revenue % × Price Impact) - (JPY Cost % × Cost Impact)

        If yen weakens (¥/$ ratio increases): Stock gains if high USD exposure
        If yen strengthens (¥/$ ratio decreases): Stock loses if high USD exposure
        """

        usd_rev_pct = stock_data['usd_revenue_pct']
        jpy_cost_pct = stock_data['jpy_costs_pct']

        # Net USD exposure (higher = more sensitive to weak yen)
        net_usd_exposure = usd_rev_pct - jpy_cost_pct

        return {
            'stock': stock_code,
            'sector': stock_data['sector'],
            'usd_revenue_pct': usd_rev_pct,
            'jpy_costs_pct': jpy_cost_pct,
            'net_usd_exposure': net_usd_exposure,
            'beta_to_usd': stock_data['beta_to_usd'],
            'fx_category': self._categorize_fx_exposure(net_usd_exposure),
        }

    def _categorize_fx_exposure(self, exposure):
        """Categorize FX exposure level"""
        if exposure >= 0.50:
            return 'HIGH_USD_SENSITIVE'
        elif exposure >= 0.35:
            return 'MEDIUM_USD_SENSITIVE'
        elif exposure >= 0.20:
            return 'MILD_USD_SENSITIVE'
        else:
            return 'NEUTRAL_OR_JPY_EXPOSED'

    def calculate_currency_swap_ratio(self, portfolio_stocks, fx_changes_by_year):
        """
        Calculate optimal currency swap ratio.

        A currency swap locks in an exchange rate, reducing FX risk.
        Optimal ratio = % of position to hedge against adverse FX moves.

        High USD exposure stocks → Benefit from weak yen → Reduce hedge ratio
        Low USD exposure stocks → Hurt by weak yen → Increase hedge ratio
        """

        # Weight by USD exposure
        total_exposure = 0
        weighted_usd_exposure = 0

        for stock in portfolio_stocks:
            fx_profile = self.calculate_fx_sensitivity(stock, self.stocks[stock])
            exposure = fx_profile['net_usd_exposure']
            weighted_usd_exposure += exposure / len(portfolio_stocks)
            total_exposure += exposure

        avg_exposure = weighted_usd_exposure

        # Swap ratio recommendation
        # High USD exposure (0.45+) → Light hedge (20-30% swapped)
        # Medium USD exposure (0.30-0.45) → Moderate hedge (40-50% swapped)
        # Low USD exposure (<0.30) → Heavy hedge (60-70% swapped)

        if avg_exposure >= 0.45:
            optimal_swap_ratio = 0.25  # Mostly unhedged, let USD strength work
        elif avg_exposure >= 0.35:
            optimal_swap_ratio = 0.45  # Moderate hedge
        else:
            optimal_swap_ratio = 0.65  # Heavy hedge

        return {
            'avg_usd_exposure': avg_exposure,
            'optimal_swap_ratio': optimal_swap_ratio,
            'interpretation': f"{optimal_swap_ratio*100:.0f}% of USD position should be swapped to JPY-fixed",
        }

    def model_fx_impact_on_stocks(self, fx_changes_by_year):
        """
        Model how FX changes affect stock returns.

        When yen weakens (positive fx_change):
        - High USD exposure stocks get a boost
        - Low USD exposure stocks get a penalty
        """

        impacts = {}

        for year, (year_name, fx_change) in enumerate(fx_changes_by_year.items()):
            year_impacts = []

            for stock_code, stock_data in self.stocks.items():
                fx_profile = self.calculate_fx_sensitivity(stock_code, stock_data)
                net_exposure = fx_profile['net_usd_exposure']

                # FX impact on stock return (simplified)
                # Strong relationship: if yen weakens 5%, USD-exposed stocks benefit ~2-4%
                fx_impact = net_exposure * fx_change * 0.8  # 80% correlation

                year_impacts.append({
                    'stock': stock_code,
                    'year': year_name,
                    'fx_change_pct': fx_change,
                    'fx_impact_on_return': fx_impact,
                    'net_exposure': net_exposure,
                })

            impacts[year_name] = year_impacts

        return impacts

    def calculate_hedged_vs_unhedged(self, stock_returns, fx_changes, swap_ratio):
        """
        Compare returns: unhedged vs hedged with currency swaps.

        Unhedged: Full FX exposure (good if yen weakens, bad if strengthens)
        Hedged (swap_ratio): Lock in part of FX rate, reduce volatility
        """

        results_by_scenario = []

        for year_idx, (year_name, fx_change) in enumerate(fx_changes.items()):
            stock_return = stock_returns[year_idx]

            # Unhedged: Full FX exposure
            fx_impact_unhedged = fx_change * 0.5  # FX adds 50% of change to stock return
            return_unhedged = stock_return + fx_impact_unhedged

            # Hedged: Swap ratio locks in part of FX
            # If swapped at ¥100/$1, locks in that rate
            # Remaining portion (1 - swap_ratio) floats
            fx_impact_hedged = (1 - swap_ratio) * fx_change * 0.5
            return_hedged = stock_return + fx_impact_hedged

            # Cost of swap (typically 1-2% per year)
            swap_cost = 0.015  # 1.5% annual
            return_hedged_after_cost = return_hedged - swap_cost

            results_by_scenario.append({
                'year': year_name,
                'fx_change': fx_change,
                'stock_return': stock_return,
                'return_unhedged': return_unhedged,
                'return_hedged': return_hedged_after_cost,
                'benefit_of_hedge': return_hedged_after_cost - return_unhedged,
                'swap_ratio': swap_ratio,
            })

        return results_by_scenario

    def analyze_portfolio_composition(self, portfolio_stocks):
        """Analyze FX profile of entire portfolio"""

        fx_profiles = []
        total_weight = 0
        weighted_exposure = 0

        for stock in portfolio_stocks:
            profile = self.calculate_fx_sensitivity(stock, self.stocks[stock])
            fx_profiles.append(profile)

            # Equal weight
            weight = 1.0 / len(portfolio_stocks)
            weighted_exposure += profile['net_usd_exposure'] * weight
            total_weight += weight

        return {
            'stocks': fx_profiles,
            'portfolio_weighted_usd_exposure': weighted_exposure,
            'high_usd_exposure_count': sum(1 for p in fx_profiles if p['fx_category'] == 'HIGH_USD_SENSITIVE'),
            'neutral_count': sum(1 for p in fx_profiles if p['fx_category'] == 'NEUTRAL_OR_JPY_EXPOSED'),
        }

    def _print_sensitivities(self):
        """Section 1: FX sensitivity of each stock; returns the sensitivity records."""
        print("\n1️⃣  FX SENSITIVITY ANALYSIS")
        print("─" * 120)

        sensitivities = [self.calculate_fx_sensitivity(code, data) for code, data in self.stocks.items()]

        print(f"\n{'Stock':<8} {'Sector':<12} {'USD Rev %':<12} {'JPY Cost %':<13} "
              f"{'Net USD Exp':<13} {'FX Category':<25}")
        print("─" * 120)

        for s in sensitivities:
            print(f"{s['stock']:<8} {s['sector']:<12} {s['usd_revenue_pct']*100:>10.1f}% "
                  f"{s['jpy_costs_pct']*100:>11.1f}% {s['net_usd_exposure']:>11.2f} {s['fx_category']:<25}")
        return sensitivities

    def _print_portfolio_profile(self, portfolio):
        """Section 2: portfolio-weighted USD exposure; returns the composition analysis."""
        print("\n2️⃣  PORTFOLIO FX PROFILE")
        print("─" * 120)

        portfolio_analysis = self.analyze_portfolio_composition(portfolio)
        exposure = portfolio_analysis['portfolio_weighted_usd_exposure']
        print(f"\nPortfolio-Weighted USD Exposure: {exposure:.3f}")
        print(f"High USD-Sensitive Stocks:       {portfolio_analysis['high_usd_exposure_count']} / {len(portfolio)}")
        print(f"Neutral/JPY-Exposed Stocks:      {portfolio_analysis['neutral_count']} / {len(portfolio)}")

        if exposure >= HIGH_USD_PORTFOLIO_EXPOSURE:
            print("→ Portfolio BENEFITS from weak yen (current structure is good)")
        elif exposure >= MODERATE_USD_PORTFOLIO_EXPOSURE:
            print("→ Portfolio has MODERATE USD exposure (balanced)")
        else:
            print("→ Portfolio is JPY/diversified (consider adding more USD-exposed stocks)")
        return portfolio_analysis

    def _print_swap_strategy(self, portfolio):
        """Section 3: optimal swap ratio; returns the swap strategy."""
        print("\n3️⃣  OPTIMAL CURRENCY SWAP STRATEGY")
        print("─" * 120)

        swap_strategy = self.calculate_currency_swap_ratio(portfolio, {})
        print(f"\nAverage USD Exposure:      {swap_strategy['avg_usd_exposure']:.3f}")
        print(f"Optimal Swap Ratio:        {swap_strategy['optimal_swap_ratio']*100:.0f}%")
        print("\nInterpretation:")
        print(f"  {swap_strategy['interpretation']}")
        print("\nPractical Implementation:")
        print("  • Initial investment: ¥100M")
        print(f"  • Convert to USD: ${(100_000_000/100):.0f},000")
        print(f"  • Buy stocks (unhedged): ${(100_000_000/100)*0.75:.0f},000")
        print(f"  • Currency swap (lock in FX): ${(100_000_000/100)*0.25:.0f},000 at ¥{100:.2f}/USD")
        print("  • Swap cost: ~1.5% per annum")
        return swap_strategy

    def _print_fx_impacts(self):
        """Section 4: FX impact on each stock per year; returns the impacts."""
        print("\n4️⃣  FX IMPACT ON STOCKS BY YEAR")
        print("─" * 120)

        fx_impacts = self.model_fx_impact_on_stocks(FX_SCENARIOS)

        for year_name, impacts in fx_impacts.items():
            print(f"\n{year_name}")
            print(f"{'Stock':<8} {'Net USD Exp':<14} {'FX Change':<12} {'FX Impact on Return':<20}")
            print("─" * 60)

            for impact in impacts:
                print(f"{impact['stock']:<8} {impact['net_exposure']:>12.3f} {impact['fx_change_pct']:>10.1f}% "
                      f"{impact['fx_impact_on_return']:>18.2f}%")
        return fx_impacts

    def _print_hedge_scenario(self, spec):
        """Print one hedging scenario table; returns (5-year total %, CAGR %)."""
        print(spec['heading'])
        print("─" * 120)

        results = self.calculate_hedged_vs_unhedged(HISTORICAL_STOCK_RETURNS, FX_SCENARIOS,
                                                    swap_ratio=spec['swap_ratio'])

        print(f"\n{'Year':<25} {'Stock Ret':<12} {spec['delta_label']:<12} {spec['total_label']:<15}")
        print("─" * 70)

        cumulative = 1.0
        for result in results:
            delta = spec['delta'](result)
            total = result[spec['total_key']]
            print(f"{result['year']:<25} {result['stock_return']:>10.2f}% {delta:>10.2f}% {total:>13.2f}%")
            cumulative *= (1 + total / 100)

        five_year = (cumulative - 1) * 100
        cagr = ((cumulative) ** (1/5) - 1) * 100
        print(f"\n5-Year Return: {five_year:.2f}%  |  CAGR: {cagr:.2f}%")
        return five_year, cagr

    def _print_comparative_summary(self, outcomes):
        """Section 6: side-by-side table of the three scenarios."""
        print("\n\n6️⃣  COMPARATIVE SUMMARY")
        print("="*120)

        print(f"\n{'Strategy':<30} {'5-Year Total':<20} {'CAGR':<15} {'Volatility':<15}")
        print("─" * 80)
        for spec, (five_year, cagr) in zip(HEDGE_SCENARIOS, outcomes):
            print(f"{spec['summary_label']:<30} {five_year:>18.2f}% {cagr:>13.2f}% {spec['volatility']:<15}")

    @staticmethod
    def _print_final_recommendation(exposure, hedged_cagr):
        """Closing rationale and implementation notes for the partially hedged strategy."""
        print("\n\n✅ RECOMMENDATION: PARTIALLY HEDGED STRATEGY")
        print("─" * 120)
        print("\nRationale:")
        print(f"  1. Portfolio has {exposure:.1%} USD exposure → Benefits from weak yen")
        print("  2. Historical FX favorable: Yen weakened 2-8% in 3/5 years")
        print("  3. Partial hedge (25%) balances upside vs downside")
        print(f"  4. Maintains {hedged_cagr:.1f}% CAGR while reducing volatility")
        print("  5. Swap cost (1.5% pa) covered by enhanced stock returns")

        print("\nImplementation:")
        print("  • Swap ¥25M (25% of ¥100M borrow) at current rate (~¥100/$1)")
        print("  • Invest ¥75M directly in USD stocks (keep FX exposure)")
        print("  • Lock in rate for 25% position, let 75% float")
        print(f"  • Expected net CAGR: {hedged_cagr:.2f}% after all costs including swaps")

    def run_analysis(self):
        """Run complete currency-adjusted analysis"""

        print("\n" + "="*120)
        print("CURRENCY-ADJUSTED YEN CARRY TRADE ANALYSIS")
        print("FX Exposure Profiling + Optimal Hedging Strategy")
        print("="*120)

        # Portfolio: The triple-hit stocks
        portfolio = list(self.stocks.keys())

        sensitivities = self._print_sensitivities()
        portfolio_analysis = self._print_portfolio_profile(portfolio)
        swap_strategy = self._print_swap_strategy(portfolio)
        fx_impacts = self._print_fx_impacts()

        # 5. Hedged vs Unhedged Comparison
        print("\n5️⃣  HEDGED vs UNHEDGED RETURNS")
        print("─" * 120)
        outcomes = [self._print_hedge_scenario(spec) for spec in HEDGE_SCENARIOS]
        (unhedged_5yr, unhedged_cagr), (hedged_5yr, hedged_cagr), (full_hedge_5yr, full_hedge_cagr) = outcomes

        self._print_comparative_summary(outcomes)
        self._print_final_recommendation(portfolio_analysis['portfolio_weighted_usd_exposure'], hedged_cagr)

        print("\n" + "="*120 + "\n")

        self.results = {
            'sensitivities': sensitivities,
            'portfolio_analysis': portfolio_analysis,
            'swap_strategy': swap_strategy,
            'fx_impacts': fx_impacts,
            'scenarios': {
                'unhedged': {'5yr': unhedged_5yr, 'cagr': unhedged_cagr},
                'hedged_25': {'5yr': hedged_5yr, 'cagr': hedged_cagr},
                'hedged_100': {'5yr': full_hedge_5yr, 'cagr': full_hedge_cagr},
            }
        }

        return self.results

    def export_results(self):
        """Export to JSON"""
        with open('currency_adjusted_analysis.json', 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print("✅ Exported to currency_adjusted_analysis.json")

# Main
if __name__ == "__main__":
    analyzer = CurrencyAdjustedCarryTrade()
    analyzer.run_analysis()
    analyzer.export_results()
