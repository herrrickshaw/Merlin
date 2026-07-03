#!/usr/bin/env python3
"""
Complete Backtesting Pipeline
End-to-end: Data Fetch → Screening → Portfolio Construction → Forward Testing
"""

import pandas as pd
from datetime import datetime, timedelta
from data_fetcher import MarketDataFetcher
from batch_screener import BatchScreener
from historical_portfolio_backtester import PortfolioConstructor, HistoricalBacktester
import json

# ─── Complete Pipeline ────────────────────────────────────────────────────

class CompleteBacktestPipeline:
    """Run complete backtesting from start to finish"""

    def __init__(self):
        self.fetcher = MarketDataFetcher()
        self.screener = BatchScreener()
        self.results = {
            'config': {},
            'market_data': {},
            'triple_hits': [],
            'portfolio': None,
            'backtest_results': None,
            'metrics': None,
        }

    def run_pipeline(self, portfolio_date, backtest_end_date=None, markets=['USA']):
        """Execute complete pipeline"""

        print("\n" + "="*90)
        print("MERLIN - COMPLETE BACKTESTING PIPELINE")
        print("="*90)

        # Config
        self.results['config'] = {
            'portfolio_date': portfolio_date,
            'backtest_end_date': backtest_end_date or datetime.now().strftime('%Y-%m-%d'),
            'markets': markets,
        }

        # Step 1: Fetch historical data
        print("\n" + "─"*90)
        print("STEP 1: FETCH HISTORICAL MARKET DATA")
        print("─"*90)

        portfolio_dt = datetime.strptime(portfolio_date, '%Y-%m-%d')
        data_start = portfolio_dt - timedelta(days=252*2)

        print(f"Fetching data from {data_start.date()} to {portfolio_dt.date()}")
        print(f"Markets: {', '.join(markets)}\n")

        market_data = self.fetcher.fetch_market_data(
            start_date=data_start.strftime('%Y-%m-%d'),
            end_date=portfolio_dt.strftime('%Y-%m-%d'),
            markets=markets
        )

        self.results['market_data'] = market_data

        # Step 2: Screen market
        print("\n" + "─"*90)
        print("STEP 2: SCREEN ENTIRE MARKET")
        print("─"*90)

        triple_hits = self.screener.screen_market(market_data)
        self.results['triple_hits'] = triple_hits

        if not triple_hits:
            print("❌ No triple hits found. Backtesting cannot proceed.")
            return False

        print(f"\n✅ Found {len(triple_hits)} triple hits")

        # Step 3: Build portfolio
        print("\n" + "─"*90)
        print("STEP 3: BUILD OPTIMIZED PORTFOLIO")
        print("─"*90)

        constructor = PortfolioConstructor(triple_hits)
        portfolio = constructor.build_portfolio(strategy='quality_weighted', date=portfolio_date)
        self.results['portfolio'] = portfolio

        print(f"\nPortfolio created with {len(portfolio['stocks'])} stocks")
        print(f"Starting capital: ${portfolio['total_value']:,.0f}")
        print(f"\nTop allocations:")

        sorted_stocks = sorted(portfolio['stocks'], key=lambda x: x['weight'], reverse=True)
        for pos in sorted_stocks[:5]:
            print(f"  {pos['symbol']:<10} {pos['weight']*100:>6.2f}%  (Piotroski: {pos['piotroski']}/9)")

        # Step 4: Backtest forward
        print("\n" + "─"*90)
        print("STEP 4: BACKTEST FORWARD PERFORMANCE")
        print("─"*90)

        backtest_end = datetime.strptime(backtest_end_date, '%Y-%m-%d') if backtest_end_date else datetime.now()

        print(f"Testing period: {portfolio_date} → {backtest_end.strftime('%Y-%m-%d')}")
        print(f"Duration: {(backtest_end - portfolio_dt).days} days\n")

        backtester = HistoricalBacktester(portfolio)

        print("Fetching forward prices...")
        forward_prices = backtester.fetch_forward_prices(
            portfolio_date,
            backtest_end.strftime('%Y-%m-%d')
        )

        if not forward_prices:
            print("❌ No forward price data available")
            return False

        daily_values = backtester.calculate_daily_returns(forward_prices)
        metrics = backtester.calculate_metrics()

        self.results['backtest_results'] = daily_values
        self.results['metrics'] = metrics

        # Step 5: Report results
        print("\n" + "="*90)
        print("FINAL RESULTS")
        print("="*90 + "\n")

        self.print_results()

        return True

    def print_results(self):
        """Print formatted results"""

        if not self.results['metrics']:
            print("No results available")
            return

        m = self.results['metrics']
        p = self.results['portfolio']

        print(f"📊 PORTFOLIO PERFORMANCE")
        print("─" * 60)
        print(f"Portfolio Date:        {self.results['config']['portfolio_date']}")
        print(f"Backtest End Date:     {self.results['config']['backtest_end_date']}")
        print(f"Stocks in Portfolio:   {len(p['stocks'])}")
        print(f"Backtest Duration:     {m['days']} days ({m['days']/365:.2f} years)")
        print()

        print(f"💰 RETURNS")
        print("─" * 60)
        print(f"Starting Capital:      ${m['starting_value']:>15,.0f}")
        print(f"Ending Value:          ${m['final_value']:>15,.0f}")
        print(f"Absolute Gain:         ${m['final_value'] - m['starting_value']:>15,.0f}")
        print(f"Total Return:          {m['total_return_pct']:>15.2f}%")
        print(f"Annual Return:         {m['annual_return_pct']:>15.2f}%")
        print()

        print(f"📈 RISK METRICS")
        print("─" * 60)
        print(f"Volatility (Annual):   {m['volatility_pct']:>15.2f}%")
        print(f"Max Drawdown:          {m['max_drawdown_pct']:>15.2f}%")
        print(f"Sharpe Ratio:          {m['sharpe_ratio']:>15.2f}")
        print()

        print(f"🎯 PORTFOLIO COMPOSITION")
        print("─" * 60)
        sorted_stocks = sorted(p['stocks'], key=lambda x: x['weight'], reverse=True)
        for pos in sorted_stocks[:10]:
            print(f"{pos['symbol']:<10} {pos['weight']*100:>6.2f}%  Piotroski: {pos['piotroski']}/9  CMF: {pos['cmf']:>7.4f}")

        if len(sorted_stocks) > 10:
            print(f"... and {len(sorted_stocks) - 10} more stocks")

        print("\n" + "="*90)

    def export_results(self):
        """Export results to files"""

        # Export portfolio
        if self.results['portfolio']:
            portfolio_df = pd.DataFrame([
                {
                    'symbol': pos['symbol'],
                    'shares': pos['shares'],
                    'entry_price': pos['entry_price'],
                    'weight': pos['weight'],
                    'piotroski': pos['piotroski'],
                    'cmf': pos['cmf'],
                }
                for pos in self.results['portfolio']['stocks']
            ])
            portfolio_df.to_csv('portfolio_composition.csv', index=False)
            print("✅ Portfolio composition exported to portfolio_composition.csv")

        # Export backtest results
        if self.results['backtest_results']:
            df_backtest = pd.DataFrame(self.results['backtest_results'])
            df_backtest.to_csv('backtest_daily_values.csv', index=False)
            print("✅ Daily values exported to backtest_daily_values.csv")

        # Export config and metrics
        summary = {
            'config': self.results['config'],
            'metrics': self.results['metrics'],
            'triple_hits_count': len(self.results['triple_hits']),
        }

        with open('backtest_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        print("✅ Summary exported to backtest_summary.json")

# ─── Main Entry Point ────────────────────────────────────────────────────

def main():
    """Run complete backtesting pipeline"""

    pipeline = CompleteBacktestPipeline()

    # Define backtesting parameters
    portfolio_date = '2023-01-15'  # Date to build portfolio
    backtest_end = '2024-01-15'    # Test forward 1 year
    markets = ['USA']  # Start with US market

    # Run pipeline
    success = pipeline.run_pipeline(
        portfolio_date=portfolio_date,
        backtest_end_date=backtest_end,
        markets=markets
    )

    if success:
        pipeline.export_results()

        print("\n" + "="*90)
        print("✅ BACKTESTING COMPLETE")
        print("="*90)
        print("\nGenerated Files:")
        print("  • portfolio_composition.csv - Detailed portfolio allocation")
        print("  • backtest_daily_values.csv - Daily portfolio values")
        print("  • backtest_summary.json - Overall metrics and config")
        print()

    return pipeline

if __name__ == "__main__":
    pipeline = main()
