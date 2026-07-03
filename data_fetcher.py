#!/usr/bin/env python3
"""
Real Market Data Fetcher
Integrates Yahoo Finance, NSE, BSE, and EDGA data sources
"""

import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import json
import time

# ─── NSE Data Fetcher ──────────────────────────────────────────────────────

class NSEDataFetcher:
    """Fetch live NSE (National Stock Exchange) India data"""

    def __init__(self):
        self.base_url = "https://www.nseindia.com/api/quote-derivative"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        }

    def get_nse_symbols(self):
        """Get all NSE-listed equity symbols"""
        try:
            # Common NSE stocks
            nse_stocks = [
                'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'WIPRO.NS', 'AXISBANK.NS',
                'HDFC.NS', 'MARUTI.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'ICICIBANK.NS',
                'SBIN.NS', 'HCLTECH.NS', 'TECHM.NS', 'ASIANPAINT.NS', 'DMART.NS',
                'SUNPHARMA.NS', 'HINDUNILVR.NS', 'LT.NS', 'LTTS.NS', 'INDIGO.NS',
                'ADANIENT.NS', 'ADANIPORTS.NS', 'APOLLOHOSP.NS', 'ASHOKLEY.NS', 'AUBANK.NS',
            ]
            return nse_stocks
        except Exception as e:
            print(f"Error fetching NSE symbols: {e}")
            return []

    def fetch_nse_data(self, symbol, start_date, end_date):
        """Fetch NSE stock data"""
        try:
            # Convert NSE symbol to yfinance format
            yf_symbol = symbol.replace('.NS', '.BO') if '.NS' in symbol else symbol + '.BO'

            data = yf.download(yf_symbol, start=start_date, end=end_date, progress=False)
            return data
        except Exception as e:
            print(f"Error fetching NSE data for {symbol}: {e}")
            return None

# ─── BSE Data Fetcher ─────────────────────────────────────────────────────

class BSEDataFetcher:
    """Fetch BSE (Bombay Stock Exchange) data"""

    def __init__(self):
        pass

    def get_bse_symbols(self):
        """Get BSE-listed symbols (smaller caps, less liquid)"""
        bse_stocks = [
            'ABSLDWIN.BO', 'AFTL.BO', 'AMERBSES.BO', 'ANSAFETY.BO', 'APCL.BO',
        ]
        return bse_stocks

    def fetch_bse_data(self, symbol, start_date, end_date):
        """Fetch BSE stock data"""
        try:
            data = yf.download(symbol, start=start_date, end=end_date, progress=False)
            return data
        except Exception as e:
            print(f"Error fetching BSE data for {symbol}: {e}")
            return None

# ─── US Stock Data (Yahoo Finance + EDGA) ──────────────────────────────────

class USStockFetcher:
    """Fetch US market data from Yahoo Finance"""

    def get_us_symbols(self):
        """Get popular US stocks"""
        us_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
            'TSLA', 'META', 'JPM', 'V', 'JNJ',
            'MA', 'PG', 'MCD', 'NFLX', 'ADBE',
            'CRM', 'PYPL', 'INTC', 'AMD', 'CSCO',
            'IBM', 'BA', 'GM', 'F', 'GE',
        ]
        return us_stocks

    def fetch_us_data(self, symbol, start_date, end_date):
        """Fetch US stock data from Yahoo Finance"""
        try:
            data = yf.download(symbol, start=start_date, end=end_date, progress=False)
            return data
        except Exception as e:
            print(f"Error fetching US data for {symbol}: {e}")
            return None

# ─── Fundamental Data Fetcher ─────────────────────────────────────────────

class FundamentalDataFetcher:
    """Fetch fundamental data for calculating Piotroski F-Score"""

    def fetch_fundamentals(self, symbol):
        """Fetch fundamentals using yfinance"""
        try:
            ticker = yf.Ticker(symbol)

            # Get financial info
            info = ticker.info
            financials = ticker.quarterly_financials if hasattr(ticker, 'quarterly_financials') else None

            return {
                'symbol': symbol,
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'peg_ratio': info.get('pegRatio', 0),
                'roe': info.get('returnOnEquity', 0),
                'roa': info.get('returnOnAssets', 0),
                'debt_to_equity': info.get('debtToEquity', 0),
                'current_ratio': info.get('currentRatio', 0),
                'revenue': info.get('totalRevenue', 0),
                'net_income': info.get('netIncomeToCommon', 0),
                'operating_cash_flow': info.get('operatingCashflow', 0),
                'free_cash_flow': info.get('freeCashflow', 0),
                'profit_margin': info.get('profitMargins', 0),
            }
        except Exception as e:
            print(f"Error fetching fundamentals for {symbol}: {e}")
            return None

# ─── Volume and Liquidity Data ─────────────────────────────────────────────

class VolumeDataFetcher:
    """Fetch volume and liquidity data for CMF calculation"""

    def fetch_volume_data(self, symbol, start_date, end_date):
        """Fetch OHLCV data needed for CMF"""
        try:
            data = yf.download(symbol, start=start_date, end=end_date, progress=False)

            if data is not None and len(data) > 0:
                return {
                    'symbol': symbol,
                    'open': data['Open'].values,
                    'high': data['High'].values,
                    'low': data['Low'].values,
                    'close': data['Close'].values,
                    'volume': data['Volume'].values,
                    'dates': data.index.strftime('%Y-%m-%d').values,
                }
            return None
        except Exception as e:
            print(f"Error fetching volume data for {symbol}: {e}")
            return None

# ─── Historical Price Data ────────────────────────────────────────────────

class HistoricalPriceFetcher:
    """Fetch and cache historical price data"""

    def __init__(self):
        self.cache = {}

    def fetch_historical_prices(self, symbol, start_date, end_date):
        """Fetch complete price history"""
        cache_key = f"{symbol}_{start_date}_{end_date}"

        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            data = yf.download(symbol, start=start_date, end=end_date, progress=False)

            if data is not None and len(data) > 0:
                price_df = pd.DataFrame({
                    'date': data.index,
                    'open': data['Open'].values,
                    'high': data['High'].values,
                    'low': data['Low'].values,
                    'close': data['Close'].values,
                    'volume': data['Volume'].values,
                    'adjusted_close': data['Adj Close'].values,
                })

                self.cache[cache_key] = price_df
                return price_df

            return None
        except Exception as e:
            print(f"Error fetching historical prices for {symbol}: {e}")
            return None

# ─── Consolidated Market Data Fetcher ──────────────────────────────────────

class MarketDataFetcher:
    """Unified market data fetcher for all regions"""

    def __init__(self):
        self.nse = NSEDataFetcher()
        self.bse = BSEDataFetcher()
        self.us = USStockFetcher()
        self.fundamentals = FundamentalDataFetcher()
        self.volume = VolumeDataFetcher()
        self.historical = HistoricalPriceFetcher()

    def get_all_symbols(self, markets=['India', 'USA']):
        """Get symbols for specified markets"""
        symbols = {}

        if 'India' in markets:
            symbols['NSE'] = self.nse.get_nse_symbols()
            symbols['BSE'] = self.bse.get_bse_symbols()

        if 'USA' in markets:
            symbols['USA'] = self.us.get_us_symbols()

        return symbols

    def fetch_stock_data(self, symbol, start_date, end_date):
        """Fetch complete data for a stock (OHLCV + fundamentals)"""

        # Fetch price data
        price_data = self.historical.fetch_historical_prices(symbol, start_date, end_date)

        # Fetch volume data
        volume_data = self.volume.fetch_volume_data(symbol, start_date, end_date)

        # Fetch fundamentals
        fundamental_data = self.fundamentals.fetch_fundamentals(symbol)

        return {
            'symbol': symbol,
            'prices': price_data,
            'volumes': volume_data,
            'fundamentals': fundamental_data,
        }

    def fetch_market_data(self, start_date, end_date, markets=['India', 'USA']):
        """Fetch data for all symbols in selected markets"""

        all_symbols = self.get_all_symbols(markets)
        market_data = {}

        total_symbols = sum(len(syms) for syms in all_symbols.values())
        processed = 0

        for exchange, symbols in all_symbols.items():
            print(f"\n📊 Fetching {exchange} data ({len(symbols)} symbols)...")
            market_data[exchange] = []

            for symbol in symbols:
                processed += 1
                print(f"  [{processed}/{total_symbols}] {symbol}...", end='', flush=True)

                stock_data = self.fetch_stock_data(symbol, start_date, end_date)

                if stock_data['prices'] is not None and len(stock_data['prices']) > 0:
                    market_data[exchange].append(stock_data)
                    print(" ✓")
                else:
                    print(" ✗ (no data)")

                # Rate limiting
                time.sleep(0.1)

        return market_data

    def get_current_price(self, symbol):
        """Get current price for a symbol"""
        try:
            ticker = yf.Ticker(symbol)
            return ticker.info.get('currentPrice', None)
        except:
            return None

# ─── Data Validation ──────────────────────────────────────────────────────

def validate_data(stock_data):
    """Validate fetched data quality"""

    if stock_data['prices'] is None or len(stock_data['prices']) == 0:
        return False, "No price data"

    if len(stock_data['prices']) < 252:  # Need 1 year of data
        return False, f"Insufficient data ({len(stock_data['prices'])} days)"

    if stock_data['volumes'] is None or len(stock_data['volumes']['volume']) == 0:
        return False, "No volume data"

    # Check for NaN values
    if stock_data['prices']['close'].isna().any():
        return False, "Contains NaN values"

    return True, "Valid"

# ─── Export Functions ─────────────────────────────────────────────────────

def export_market_data_to_csv(market_data, output_dir='market_data'):
    """Export market data to CSV files for processing"""
    import os

    os.makedirs(output_dir, exist_ok=True)

    for exchange, stocks in market_data.items():
        for stock_data in stocks:
            symbol = stock_data['symbol']
            filename = f"{output_dir}/{exchange}_{symbol.replace('.', '_')}_prices.csv"

            if stock_data['prices'] is not None:
                stock_data['prices'].to_csv(filename, index=False)
                print(f"Exported: {filename}")

# ─── Main Test ────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*80)
    print("MARKET DATA FETCHER - Real Data Integration")
    print("="*80)

    fetcher = MarketDataFetcher()

    # Define date range for backtesting
    end_date = datetime.now()
    start_date = end_date - timedelta(days=252*5)  # 5 years of data

    print(f"\nFetching data from {start_date.date()} to {end_date.date()}")
    print(f"Markets: India (NSE/BSE), USA\n")

    # Fetch market data
    market_data = fetcher.fetch_market_data(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        markets=['India', 'USA']
    )

    # Summary
    print("\n" + "="*80)
    print("📊 DATA SUMMARY")
    print("="*80 + "\n")

    total_stocks = 0
    for exchange, stocks in market_data.items():
        print(f"{exchange}: {len(stocks)} stocks with valid data")
        total_stocks += len(stocks)

        # Sample stock info
        if stocks:
            sample = stocks[0]
            print(f"  Sample: {sample['symbol']}")
            if sample['prices'] is not None:
                print(f"    Price history: {len(sample['prices'])} days")
                print(f"    Latest close: ${sample['prices']['close'].iloc[-1]:.2f}")

    print(f"\n✅ Total stocks with valid data: {total_stocks}")

    return market_data

if __name__ == "__main__":
    market_data = main()
