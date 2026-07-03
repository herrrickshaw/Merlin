(* Stock Screener Interface *)

type ohlcv = {
  date: string;
  open_: float;
  high: float;
  low: float;
  close: float;
  volume: float;
}

type stock_data = {
  symbol: string;
  market: string;
  ohlcv: ohlcv list;
  fundamentals: (string * float option) list;
}

type result = {
  symbol: string;
  strategy: string;
  passed: bool;
  score: float option;
  metrics: (string * string) list;
  note: string;
}

val screen_stock : stock_data -> result list
val screen_market : stock_data list -> result list
val rank_results : result list -> string -> result list
val results_to_csv : result list -> string
val darvas_screen : stock_data -> result
val piotroski_screen : stock_data -> result
val coffee_can_screen : stock_data -> result
val magic_formula_screen : stock_data -> result
val golden_crossover_screen : stock_data -> result
