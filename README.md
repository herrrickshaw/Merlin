# Merlin: stock screening, backtesting and LFS data analysis

Merlin is a small OCaml tool (CSV/JSON analysis, statistics, uploading results to a Git repo, multi-strategy
stock screeners) together with a set of Python scripts that run the same screening strategies on CSV or
yfinance data and backtest them (India NSE/BSE and US equities). It produces console reports, CSV exports
(for example `triple_hits_results.csv`) and JSON analysis files.

> Status: research-only snapshot. Educational use only; not investment advice. Market data comes from Yahoo
> Finance via `yfinance` (unofficial; subject to Yahoo's terms and rate limits).

New here? See [How to use this repo with AI](HOW_TO_USE_WITH_AI.md).
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/herrrickshaw/Merlin/blob/master/notebooks/colab_test.ipynb)

## What it does
- OCaml CLI (`merlin`): `analyze-csv`, `analyze-json`, `stats`, `filter`, `upload` (commit/push a file to a repo).
- OCaml executables `screener`, `advanced_analyzer` and `multi_market` for multi-strategy screening.
- `screener_runner.py`: Darvas Box, Piotroski F-Score, Coffee Can, Magic Formula and Golden Crossover screens
  over a CSV of OHLCV + fundamentals.
- `data_fetcher.py` + `batch_screener.py`: fetch prices/fundamentals with yfinance and run a four-stage filter
  (Darvas, Piotroski >= 7, Coffee Can quality, Chaikin Money Flow accumulation) to find "triple hits".
- Python backtests of the screens (five-year, currency-adjusted, options portfolio, yen carry trade, CMF accumulation).

## Quick start
```bash
git clone https://github.com/herrrickshaw/Merlin.git
cd Merlin
python3 -m venv .venv && source .venv/bin/activate
pip install pandas numpy yfinance pytest ruff
python3 screener_runner.py examples/screener_test_data.csv --top 5   # offline demo, no network
```
OCaml part (needs `opam`, `dune >= 3.0`, `yojson`, `ppx_deriving_yojson`): `make build`, then e.g.
`dune exec bin/merlin.exe -- stats examples/nse_sample.csv close`.

## How it works
| Stage | Module | Output |
|---|---|---|
| Load CSV (`symbol,date,open,high,low,close,volume` + fundamentals) | `screener_runner.load_csv_to_stocks` | `StockData` objects |
| Apply strategies (registry `STRATEGIES`) | `screener_runner.screen_market` | `Result` per stock/strategy |
| Rank and report | `screener_runner.print_*` | ranked console report |
| Fetch prices/fundamentals (yfinance, injectable) | `data_fetcher.MarketDataFetcher` | dict of prices, volumes, fundamentals |
| Four-stage filter | `batch_screener.BatchScreener` | triple hits, `triple_hits_results.csv` |

Design notes: network access in `data_fetcher.py` goes through injectable `download` / `ticker_factory`
callables (default: yfinance, imported lazily) so everything can be tested offline. New screens are added by
registering a function in `screener_runner.STRATEGIES`.

## Repository layout
| Path | Purpose |
|---|---|
| `bin/`, `lib/`, `dune-project`, `merlin.opam` | OCaml CLI and library |
| `screener_runner.py`, `data_fetcher.py`, `batch_screener.py` | Python screening stack (refactored, tested) |
| `*_backtest*.py`, `benchmark.py`, `alternative_screens_analysis.py`, ... | Python backtest/analysis scripts (not yet refactored) |
| `examples/` | sample CSVs and `stock_analysis_workflow.sh` |
| `tests/` | pytest suite: characterisation golden files + unit tests (no network) |
| `*.md` guides | long-form notes (`SCREENER_README.md`, `LIVE_BACKTEST_GUIDE.md`, `API.md`, ...) |
| `*.json`, `*.csv` in root | generated analysis outputs, kept as-is |

## Data sources
| Source | What is taken | Access route | Caveat |
|---|---|---|---|
| Yahoo Finance | OHLCV, `Ticker.info` fundamentals | `yfinance` | unofficial API, rate-limited; fundamentals often missing |
| `examples/*.csv` | tiny sample data | tracked in repo | synthetic/demo only |

## Configuration
No environment variables or secrets are used. Thresholds (52-week window, 10% near-high, 1.5x volume, Piotroski >= 7,
CMF > 0.05) are named constants at the top of `batch_screener.py` and `screener_runner.py`.

## Testing
```bash
pytest -q          # 13 tests, no network
ruff check data_fetcher.py batch_screener.py screener_runner.py tests
```
CI (`.github/workflows/ci.yml`) runs lint, `compileall` and pytest. The OCaml build is not covered by CI.

## Limitations and known issues
- `data_fetcher.NSEDataFetcher.fetch_nse_data` rewrites `.NS` symbols to `.BO` (BSE) before downloading; kept
  as-is, almost certainly unintended.
- `yfinance` removed the `Adj Close` column by default in recent versions; `HistoricalPriceFetcher` may fail
  against newer yfinance and return `None` (logged).
- `screener_runner.py --strategy` is parsed but does not filter the report.
- Performance figures in older guides (for example "~30x faster than Python") are estimates, not measurements.
- Only `data_fetcher.py`, `batch_screener.py` and `screener_runner.py` have been refactored and tested; the other
  scripts are unchanged.

## Licence
The old README states MIT, but the repository contains no `LICENSE` file. Treat as all rights reserved until the
owner adds one.
