#!/usr/bin/env python3
"""
Historical Portfolio Constructor and Backtester
Builds a portfolio on a historical date and tracks returns going forward
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
from batch_screener import BatchScreener
from data_fetcher import MarketDataFetcher

# ─── Portfolio Constructor ────────────────────────────────────────────────

class PortfolioConstructor:
    """Build optimal portfolio from triple hits on a historical date"""

    def __init__(self, triple_hits):
        self.triple_hits = triple_hits
        self.portfolio = None

    def calculate_weights(self, strategy='quality_weighted'):
        """Calculate portfolio weights using different strategies"""

        if strategy == 'equal_weight':
            n = len(self.triple_hits)
            weights = {hit['symbol']: 1.0 / n for hit in self.triple_hits}

        elif strategy == 'quality_weighted':
            # Weight by Piotroski + CMF
            scores = []
            for hit in self.triple_hits:
                score = hit['piotroski']['score'] + (hit['cmf']['cmf_20'] * 3)
                scores.append(max(0, score))

            total_score = sum(scores)
            weights = {hit['symbol']: score / total_score
                      for hit, score in zip(self.triple_hits, scores)}

        elif strategy == 'risk_parity':
            # Weight inversely to volatility
            # Would need volatility calculation, simplified here
            weights = {hit['symbol']: 1.0 / len(self.triple_hits)
                      for hit in self.triple_hits}

        return weights

    def build_portfolio(self, strategy='quality_weighted', date=None):
        """Build portfolio on a specific date"""

        weights = self.calculate_weights(strategy)

        portfolio = {
            'date_created': date if date else datetime.now().strftime('%Y-%m-%d'),
            'strategy': strategy,
            'stocks': [],
            'weights': weights,
            'total_value': 1000000,  # $1M starting capital
        }

        for hit in self.triple_hits:
            symbol = hit['symbol']
            weight = weights[symbol]
            position_value = portfolio['total_value'] * weight
            shares = position_value / hit['price']

            portfolio['stocks'].append({
                'symbol': symbol,
                'shares': shares,
                'entry_price': hit['price'],
                'position_value': position_value,
                'weight': weight,
                'piotroski': hit['piotroski']['score'],
                'cmf': hit['cmf']['cmf_20'],
            })

        self.portfolio = portfolio
        return portfolio

    def portfolio_to_string(self):
        """Format portfolio for display"""
        if not self.portfolio:
            return "No portfolio built"

        output = f"Portfolio ({self.portfolio['strategy'].upper()})\n"
        output += f"Date: {self.portfolio['date_created']}\n"
        output += f"Total Capital: ${self.portfolio['total_value']:,.0f}\n"
        output += f"Stocks: {len(self.portfolio['stocks'])}\n\n"

        output += f"{'Symbol':<10} {'Shares':<12} {'Entry$':<10} {'Weight':<10} {'Piotroski':<12}\n"
        output += "-" * 60 + "\n"

        for pos in self.portfolio['stocks']:
            output += f"{pos['symbol']:<10} {pos['shares']:<12.0f} ${pos['entry_price']:<9.2f} "
            output += f"{pos['weight']*100:<9.1f}% {pos['piotroski']:<12}\n"

        return output

# ─── Historical Backtester ───────────────────────────────────────────────

class HistoricalBacktester:
    """Test portfolio performance from historical date into the future"""

    def __init__(self, portfolio):
        self.portfolio = portfolio
        self.daily_values = []
        self.trades = []

    def fetch_forward_prices(self, start_date, end_date):
        """Fetch prices from portfolio date forward"""

        prices_dict = {}

        for pos in self.portfolio['stocks']:
            symbol = pos['symbol']
            print(f"Fetching {symbol}...", end='', flush=True)

            try:
                data = yf.download(symbol, start=start_date, end=end_date, progress=False)

                if data is not None and len(data) > 0:
                    prices_dict[symbol] = data
                    print(" ✓")
                else:
                    print(" ✗ (no data)")
            except Exception as e:
                print(f" ✗ ({e})")

        return prices_dict

    def calculate_daily_returns(self, forward_prices):
        """Calculate daily portfolio value and returns"""

        # Get all dates
        all_dates = set()
        for symbol, data in forward_prices.items():
            all_dates.update(data.index.strftime('%Y-%m-%d'))

        all_dates = sorted(list(all_dates))

        if not all_dates:
            print("No price data available")
            return []

        portfolio_date = datetime.strptime(self.portfolio['date_created'], '%Y-%m-%d')
        daily_values = []

        print("\nCalculating daily returns...")

        for date_str in all_dates:
            date = datetime.strptime(date_str, '%Y-%m-%d')

            if date < portfolio_date:
                continue

            portfolio_value = 0

            for pos in self.portfolio['stocks']:
                symbol = pos['symbol']

                if symbol not in forward_prices:
                    continue

                try:
                    # Get price on this date
                    price_data = forward_prices[symbol]
                    if date in price_data.index:
                        price = price_data.loc[date, 'Adj Close']
                        position_value = price * pos['shares']
                        portfolio_value += position_value
                    else:
                        # Use nearest date
                        idx = price_data.index.get_indexer([date], method='nearest')[0]
                        if idx >= 0 and idx < len(price_data):
                            price = price_data.iloc[idx]['Adj Close']
                            position_value = price * pos['shares']
                            portfolio_value += position_value
                except:
                    pass

            if portfolio_value > 0:
                daily_values.append({
                    'date': date_str,
                    'portfolio_value': portfolio_value,
                    'return_pct': ((portfolio_value - self.portfolio['total_value']) /
                                  self.portfolio['total_value'] * 100),
                })

        self.daily_values = daily_values
        return daily_values

    def calculate_metrics(self):
        """Calculate performance metrics"""

        if not self.daily_values or len(self.daily_values) < 2:
            return None

        values = [dv['portfolio_value'] for dv in self.daily_values]
        returns_pct = [dv['return_pct'] for dv in self.daily_values]

        # Calculate metrics
        total_return = returns_pct[-1] if returns_pct else 0
        days = len(self.daily_values)
        years = days / 365.0

        annual_return = ((values[-1] / values[0]) ** (1 / years) - 1) * 100 if years > 0 else 0

        # Volatility
        daily_returns = np.diff(values) / np.array(values[:-1]) * 100
        volatility = np.std(daily_returns) * np.sqrt(252) if len(daily_returns) > 1 else 0

        # Max drawdown
        cummax = np.maximum.accumulate(values)
        drawdown = (values - cummax) / cummax * 100
        max_drawdown = np.min(drawdown)

        # Sharpe ratio
        excess_returns = np.array(daily_returns) - (0.04 / 252)  # Risk-free rate
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if len(excess_returns) > 0 else 0

        return {
            'total_return_pct': total_return,
            'annual_return_pct': annual_return,
            'volatility_pct': volatility,
            'max_drawdown_pct': max_drawdown,
            'sharpe_ratio': sharpe,
            'days': days,
            'final_value': values[-1] if values else 0,
            'starting_value': self.portfolio['total_value'],
        }

    def get_backtest_summary(self):
        """Generate backtest summary"""

        metrics = self.calculate_metrics()

        if not metrics:
            return "Insufficient data for backtest"

        summary = "PORTFOLIO BACKTEST RESULTS\n"
        summary += "=" * 60 + "\n"
        summary += f"Starting Capital: ${metrics['starting_value']:,.0f}\n"
        summary += f"Final Value: ${metrics['final_value']:,.0f}\n"
        summary += f"Total Return: {metrics['total_return_pct']:+.2f}%\n"
        summary += f"Annual Return: {metrics['annual_return_pct']:+.2f}%\n"
        summary += f"Holding Period: {metrics['days']} days ({metrics['days']/365:.1f} years)\n\n"

        summary += f"RISK METRICS:\n"
        summary += f"Volatility: {metrics['volatility_pct']:.2f}%\n"
        summary += f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}%\n"
        summary += f"Sharpe Ratio: {sharpe:.2f}\n"

        return summary

# ─── Main Backtesting Pipeline ────────────────────────────────────────────

def main():
    print("\n" + "="*80)
    print("HISTORICAL PORTFOLIO BACKTESTING SYSTEM")
    print("="*80)

    # Step 1: Fetch historical market data
    print("\n1️⃣  FETCHING HISTORICAL MARKET DATA...")
    fetcher = MarketDataFetcher()

    end_date = datetime(2023, 1, 15)  # Use specific historical date
    start_date = end_date - timedelta(days=252*2)

    print(f"   Period: {start_date.date()} to {end_date.date()}")

    market_data = fetcher.fetch_market_data(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        markets=['USA']
    )

    # Step 2: Screen market on that date
    print("\n2️⃣  SCREENING MARKET ON HISTORICAL DATE...")
    screener = BatchScreener()
    triple_hits = screener.screen_market(market_data)

    if not triple_hits:
        print("   ❌ No triple hits found")
        return

    print(f"   ✅ Found {len(triple_hits)} triple hits")

    # Step 3: Build portfolio
    print("\n3️⃣  BUILDING OPTIMIZED PORTFOLIO...")
    constructor = PortfolioConstructor(triple_hits)
    portfolio = constructor.build_portfolio(strategy='quality_weighted', date=end_date.strftime('%Y-%m-%d'))

    print(constructor.portfolio_to_string())

    # Step 4: Backtest forward
    print("\n4️⃣  BACKTESTING FORWARD FROM PORTFOLIO DATE...")
    backtest_start = end_date
    backtest_end = datetime.now()

    print(f"   Testing forward from {backtest_start.date()} to {backtest_end.date()}")

    backtester = HistoricalBacktester(portfolio)
    print("\n   Fetching forward prices...")
    forward_prices = backtester.fetch_forward_prices(
        backtest_start.strftime('%Y-%m-%d'),
        backtest_end.strftime('%Y-%m-%d')
    )

    if not forward_prices:
        print("   ❌ No forward price data available")
        return

    # Calculate returns
    daily_values = backtester.calculate_daily_returns(forward_prices)

    # Print results
    print("\n" + "="*80)
    print("📊 BACKTEST RESULTS")
    print("="*80 + "\n")

    if daily_values:
        metrics = backtester.calculate_metrics()

        print(f"Portfolio Value on {portfolio['date_created']}: ${portfolio['total_value']:,.0f}")
        print(f"Portfolio Value on {daily_values[-1]['date']}: ${metrics['final_value']:,.0f}")
        print(f"\nTotal Return: {metrics['total_return_pct']:+.2f}%")
        print(f"Annual Return: {metrics['annual_return_pct']:+.2f}%")
        print(f"Volatility: {metrics['volatility_pct']:.2f}%")
        print(f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")

        # Export daily values
        df_daily = pd.DataFrame(daily_values)
        df_daily.to_csv('portfolio_daily_values.csv', index=False)
        print(f"\n✅ Daily values exported to portfolio_daily_values.csv")

        return portfolio, daily_values, metrics
    else:
        print("No backtest results available")
        return None

if __name__ == "__main__":
    result = main()
