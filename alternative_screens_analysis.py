#!/usr/bin/env python3
"""
Comprehensive Alternative Screening Strategies
Compare against Yen Carry Trade Strategy (40.3% CAGR baseline)
"""

import json
from datetime import datetime

import numpy as np

from screening_strategy_data import CATEGORY_BUILDERS, RECOMMENDATIONS_TEXT


class ScreeningStrategyDatabase:
    """Database of all known investment screening strategies"""

    def __init__(self):
        self.baseline_cagr = 0.403  # Your yen carry trade
        self.strategies = {}
        self.build_database()

    def build_database(self):
        """Build comprehensive screening database (one builder per category)"""
        for name, builder in CATEGORY_BUILDERS:
            self.strategies[name] = builder()

    def _ranked_strategies(self):
        """Flatten the database into a list of dicts sorted by CAGR (descending)."""
        # Rank all by CAGR
        all_strats = []
        for category, strats in self.strategies.items():
            for strat_name, details in strats.items():
                all_strats.append({
                    'category': category,
                    'name': strat_name,
                    'cagr': details['historical_cagr'],
                    'vs_baseline': details['vs_baseline'],
                    'outperforms': details['outperforms_yen_carry'],
                    'details': details,
                })

        # Sort by CAGR descending
        all_strats.sort(key=lambda x: x['cagr'], reverse=True)
        return all_strats

    @staticmethod
    def _print_ranking(all_strats):
        print("\n1️⃣  RANKED BY HISTORICAL CAGR")
        print("─" * 180)

        print(f"\n{'Rank':<5} {'Strategy':<40} {'Category':<25} {'CAGR':<10} {'vs Baseline':<15} {'Outperforms?':<15}")
        print("─" * 180)

        for i, strat in enumerate(all_strats, 1):
            outperforms_text = "✅ YES" if strat['outperforms'] else "❌ NO"
            vs = strat['vs_baseline']
            baseline_color = f"+{vs:.1f}pp" if vs > 0 else f"{vs:.1f}pp"
            print(f"{i:<5} {strat['name']:<40} {strat['category']:<25} "
                  f"{strat['cagr']*100:>8.1f}% {baseline_color:<15} {outperforms_text:<15}")

    @staticmethod
    def _print_outperformers(all_strats):
        # Strategies that outperform
        print("\n\n2️⃣  STRATEGIES THAT OUTPERFORM YOUR BASELINE (40.3% CAGR)")
        print("─" * 180)

        outperformers = [s for s in all_strats if s['outperforms']]

        if outperformers:
            for strat in outperformers:
                details = strat['details']
                print(f"\n🏆 {strat['name'].upper()}")
                print(f"   Category:           {strat['category']}")
                print(f"   Historical CAGR:    {strat['cagr']*100:.1f}% (Your baseline: 40.3%)")
                print(f"   Outperformance:     +{strat['vs_baseline']:.1f} percentage points")
                print(f"   Description:        {details['description']}")
                print(f"   Formula:            {details['formula']}")
                print(f"   Advantage:          {details['advantage']}")
                print(f"   Disadvantage:       {details['disadvantage']}")
                print(f"   Best for:           {details['best_for']}")
                print(f"   Currency Sensitive: {'Yes' if details['currency_sensitive'] else 'No'}")
                print(f"   Source:             {details['source']}")
        else:
            print("\n⚠️  No pure strategies outperform your baseline.")
            print("Your yen carry trade strategy is in top tier.")

    @staticmethod
    def _print_category_breakdown(all_strats):
        # Category breakdown
        print("\n\n3️⃣  PERFORMANCE BY CATEGORY")
        print("─" * 180)

        categories_ranked = {}
        for strat in all_strats:
            cat = strat['category']
            if cat not in categories_ranked:
                categories_ranked[cat] = []
            categories_ranked[cat].append(strat['cagr'])

        print(f"\n{'Category':<40} {'Avg CAGR':<15} {'Best in Category':<15} {'Count':<10}")
        print("─" * 180)

        for cat in sorted(categories_ranked.keys(), key=lambda x: np.mean(categories_ranked[x]), reverse=True):
            cagrs = categories_ranked[cat]
            print(f"{cat:<40} {np.mean(cagrs)*100:>13.1f}% "
                  f"{max(cagrs)*100:>13.1f}% {len(cagrs):>8}")

    @staticmethod
    def _print_top_strategies(all_strats):
        # Detailed view of top strategies
        print("\n\n4️⃣  TOP 5 STRATEGIES (Ranked by CAGR)")
        print("="*180)

        for i, strat in enumerate(all_strats[:5], 1):
            details = strat['details']
            print(f"\n#{i}: {strat['name'].upper()}")
            print(f"    Category: {strat['category']}")
            print(f"    CAGR: {strat['cagr']*100:.1f}%")
            print(f"    vs Your Baseline: {strat['vs_baseline']:+.1f}pp")
            print("\n    Criteria:")
            for j, criterion in enumerate(details['criteria'], 1):
                print(f"      {j}. {criterion}")
            print("\n    Pros:")
            print(f"      • {details['advantage']}")
            print("\n    Cons:")
            print(f"      • {details['disadvantage']}")
            print(f"\n    Best for: {details['best_for']}")
            print(f"    Source: {details['source']}")

    def print_comprehensive_analysis(self):
        """Print all strategies ranked"""

        print("\n" + "="*180)
        print("COMPREHENSIVE SCREENING STRATEGY DATABASE")
        print("Baseline Strategy: Yen Carry Trade (40.3% CAGR)")
        print("="*180)

        all_strats = self._ranked_strategies()
        self._print_ranking(all_strats)
        self._print_outperformers(all_strats)
        self._print_category_breakdown(all_strats)
        self._print_top_strategies(all_strats)

        # Recommendations
        print("\n\n5️⃣  RECOMMENDATIONS TO ENHANCE YOUR STRATEGY")
        print("="*180)
        print(RECOMMENDATIONS_TEXT)

        return all_strats

    def export_database(self):
        """Export to JSON"""
        export_data = {
            'timestamp': datetime.now().isoformat(),
            'baseline_cagr': self.baseline_cagr,
            'strategies': {},
        }

        for category, strats in self.strategies.items():
            export_data['strategies'][category] = {}
            for strat_name, details in strats.items():
                export_data['strategies'][category][strat_name] = {
                    'cagr': details['historical_cagr'],
                    'vs_baseline': details['vs_baseline'],
                    'outperforms': details['outperforms_yen_carry'],
                    'description': details['description'],
                }

        with open('screening_strategies_database.json', 'w') as f:
            json.dump(export_data, f, indent=2)

        print("\n✅ Database exported to screening_strategies_database.json")


# Main
if __name__ == "__main__":
    db = ScreeningStrategyDatabase()
    db.print_comprehensive_analysis()
    db.export_database()
