#!/usr/bin/env python3
"""
Real Market Data Fetcher
Integrates Yahoo Finance, NSE, BSE, and EDGA data sources

All network access goes through two injectable callables (``download`` and
``ticker_factory``) that default to ``yfinance``; tests pass fakes instead.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────

DEFAULT_MARKETS = ("India", "USA")
MIN_HISTORY_DAYS = 252          # one trading year, required by validate_data
BACKTEST_YEARS = 5              # history window used by main()
RATE_LIMIT_SECONDS = 0.1        # pause between symbols in fetch_market_data

NSE_SYMBOLS = [
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'WIPRO.NS', 'AXISBANK.NS',
    'HDFC.NS', 'MARUTI.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'ICICIBANK.NS',
    'SBIN.NS', 'HCLTECH.NS', 'TECHM.NS', 'ASIANPAINT.NS', 'DMART.NS',
    'SUNPHARMA.NS', 'HINDUNILVR.NS', 'LT.NS', 'LTTS.NS', 'INDIGO.NS',
    'ADANIENT.NS', 'ADANIPORTS.NS', 'APOLLOHOSP.NS', 'ASHOKLEY.NS', 'AUBANK.NS',
]
BSE_SYMBOLS = ['ABSLDWIN.BO', 'AFTL.BO', 'AMERBSES.BO', 'ANSAFETY.BO', 'APCL.BO']
US_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
    'TSLA', 'META', 'JPM', 'V', 'JNJ',
    'MA', 'PG', 'MCD', 'NFLX', 'ADBE',
    'CRM', 'PYPL', 'INTC', 'AMD', 'CSCO',
    'IBM', 'BA', 'GM', 'F', 'GE',
]

# yfinance ``Ticker.info`` key -> output key (missing keys default to 0)
FUNDAMENTAL_FIELDS = {
    'market_cap': 'marketCap',
    'pe_ratio': 'trailingPE',
    'peg_ratio': 'pegRatio',
    'roe': 'returnOnEquity',
    'roa': 'returnOnAssets',
    'debt_to_equity': 'debtToEquity',
    'current_ratio': 'currentRatio',
    'revenue': 'totalRevenue',
    'net_income': 'netIncomeToCommon',
    'operating_cash_flow': 'operatingCashflow',
    'free_cash_flow': 'freeCashflow',
    'profit_margin': 'profitMargins',
}

# ─── Dependency injection (yfinance is imported lazily) ────────────────────

Downloader = Callable[..., Any]       # (symbol, start=, end=, progress=) -> DataFrame
TickerFactory = Callable[[str], Any]  # symbol -> object with an ``info`` dict


def _yf_download(*args, **kwargs):
    """Default downloader: ``yfinance.download`` (imported on first use)."""
    import yfinance as yf
    return yf.download(*args, **kwargs)


def _yf_ticker(symbol):
    """Default ticker factory: ``yfinance.Ticker`` (imported on first use)."""
    import yfinance as yf
    return yf.Ticker(symbol)


def _download(download: Downloader, symbol: str, start_date, end_date):
    """Download daily bars for ``symbol`` (DataFrame indexed by date)."""
    return download(symbol, start=start_date, end=end_date, progress=False)


# ─── Exchange fetchers ─────────────────────────────────────────────────────

class _PriceFetcher:
    """Base for fetchers that only need a price downloader."""

    def __init__(self, download: Optional[Downloader] = None):
        self._download = download or _yf_download

    def _fetch_prices(self, label: str, symbol: str, start_date, end_date):
        """Download bars for ``symbol``; log and return None on any failure."""
        try:
            return _download(self._download, symbol, start_date, end_date)
        except Exception as exc:
            logger.warning("Error fetching %s data for %s: %s", label, symbol, exc)
            return None


class NSEDataFetcher(_PriceFetcher):
    """Fetch live NSE (National Stock Exchange) India data"""

    def __init__(self, download: Optional[Downloader] = None):
        super().__init__(download)
        self.base_url = "https://www.nseindia.com/api/quote-derivative"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        }

    def get_nse_symbols(self):
        """Get NSE-listed equity symbols (a fixed list of common stocks)"""
        return list(NSE_SYMBOLS)

    def fetch_nse_data(self, symbol, start_date, end_date):
        """Fetch NSE stock data.

        NOTE: the symbol is rewritten to its BSE (``.BO``) form before download;
        this long-standing quirk is preserved, not fixed.
        """
        yf_symbol = symbol.replace('.NS', '.BO') if '.NS' in symbol else symbol + '.BO'
        return self._fetch_prices("NSE", yf_symbol, start_date, end_date)


class BSEDataFetcher(_PriceFetcher):
    """Fetch BSE (Bombay Stock Exchange) data"""

    def get_bse_symbols(self):
        """Get BSE-listed symbols (smaller caps, less liquid)"""
        return list(BSE_SYMBOLS)

    def fetch_bse_data(self, symbol, start_date, end_date):
        """Fetch BSE stock data"""
        return self._fetch_prices("BSE", symbol, start_date, end_date)


class USStockFetcher(_PriceFetcher):
    """Fetch US market data from Yahoo Finance"""

    def get_us_symbols(self):
        """Get popular US stocks"""
        return list(US_SYMBOLS)

    def fetch_us_data(self, symbol, start_date, end_date):
        """Fetch US stock data from Yahoo Finance"""
        return self._fetch_prices("US", symbol, start_date, end_date)


# ─── Fundamental Data Fetcher ─────────────────────────────────────────────

class FundamentalDataFetcher:
    """Fetch fundamental data for calculating Piotroski F-Score"""

    def __init__(self, ticker_factory: Optional[TickerFactory] = None):
        self._ticker = ticker_factory or _yf_ticker

    def fetch_fundamentals(self, symbol):
        """Fetch fundamentals using yfinance; dict of FUNDAMENTAL_FIELDS or None on error"""
        try:
            info = self._ticker(symbol).info
            result = {'symbol': symbol}
            for key, info_key in FUNDAMENTAL_FIELDS.items():
                result[key] = info.get(info_key, 0)
            return result
        except Exception as exc:
            logger.warning("Error fetching fundamentals for %s: %s", symbol, exc)
            return None


# ─── Volume and Liquidity Data ─────────────────────────────────────────────

class VolumeDataFetcher(_PriceFetcher):
    """Fetch volume and liquidity data for CMF calculation"""

    def fetch_volume_data(self, symbol, start_date, end_date):
        """Fetch OHLCV arrays (dict of numpy arrays) needed for CMF"""
        try:
            data = _download(self._download, symbol, start_date, end_date)

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
        except Exception as exc:
            logger.warning("Error fetching volume data for %s: %s", symbol, exc)
            return None


# ─── Historical Price Data ────────────────────────────────────────────────

class HistoricalPriceFetcher(_PriceFetcher):
    """Fetch and cache historical price data"""

    def __init__(self, download: Optional[Downloader] = None):
        super().__init__(download)
        self.cache = {}

    def fetch_historical_prices(self, symbol, start_date, end_date):
        """Fetch complete price history as a DataFrame (cached per symbol/date range)"""
        cache_key = f"{symbol}_{start_date}_{end_date}"

        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            data = _download(self._download, symbol, start_date, end_date)

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
        except Exception as exc:
            logger.warning("Error fetching historical prices for %s: %s", symbol, exc)
            return None


# ─── Consolidated Market Data Fetcher ──────────────────────────────────────

class MarketDataFetcher:
    """Unified market data fetcher for all regions.

    ``download`` / ``ticker_factory`` default to yfinance and may be replaced
    with fakes for offline use.
    """

    def __init__(self, download: Optional[Downloader] = None,
                 ticker_factory: Optional[TickerFactory] = None):
        self._ticker = ticker_factory or _yf_ticker
        self.nse = NSEDataFetcher(download)
        self.bse = BSEDataFetcher(download)
        self.us = USStockFetcher(download)
        self.fundamentals = FundamentalDataFetcher(ticker_factory)
        self.volume = VolumeDataFetcher(download)
        self.historical = HistoricalPriceFetcher(download)

    def get_all_symbols(self, markets: Sequence[str] = DEFAULT_MARKETS):
        """Get symbols for specified markets ('India' -> NSE+BSE, 'USA')"""
        symbols = {}

        if 'India' in markets:
            symbols['NSE'] = self.nse.get_nse_symbols()
            symbols['BSE'] = self.bse.get_bse_symbols()

        if 'USA' in markets:
            symbols['USA'] = self.us.get_us_symbols()

        return symbols

    def fetch_stock_data(self, symbol, start_date, end_date):
        """Fetch complete data for a stock (OHLCV + fundamentals)"""
        return {
            'symbol': symbol,
            'prices': self.historical.fetch_historical_prices(symbol, start_date, end_date),
            'volumes': self.volume.fetch_volume_data(symbol, start_date, end_date),
            'fundamentals': self.fundamentals.fetch_fundamentals(symbol),
        }

    def fetch_market_data(self, start_date, end_date, markets: Sequence[str] = DEFAULT_MARKETS):
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

                time.sleep(RATE_LIMIT_SECONDS)

        return market_data

    def get_current_price(self, symbol):
        """Get current price for a symbol (None if unavailable)"""
        try:
            return self._ticker(symbol).info.get('currentPrice', None)
        except Exception as exc:
            logger.warning("Error fetching current price for %s: %s", symbol, exc)
            return None


# ─── Data Validation ──────────────────────────────────────────────────────

def validate_data(stock_data):
    """Validate fetched data quality"""

    if stock_data['prices'] is None or len(stock_data['prices']) == 0:
        return False, "No price data"

    if len(stock_data['prices']) < MIN_HISTORY_DAYS:  # Need 1 year of data
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
    start_date = end_date - timedelta(days=MIN_HISTORY_DAYS * BACKTEST_YEARS)  # 5 years of data

    print(f"\nFetching data from {start_date.date()} to {end_date.date()}")
    print("Markets: India (NSE/BSE), USA\n")

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
