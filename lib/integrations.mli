(* Integration layer for multi-market data and tools *)

type market = {
  code: string;
  name: string;
  exchange: string;
  symbol_count: int;
  data_source: string;
  currency: string;
  timezone: string;
  market_cap_floor_usd: float;
}

type daily_report = {
  market: string;
  generated_at: string;
  total_symbols: int;
  darvas_signals: int;
  triple_hits: int;
  filename: string;
}

type pipeline_stage = [
  | `Stage1_Darvas
  | `Stage2_Piotroski
  | `Stage3_CoffeeCan
]

type pipeline_result = {
  stage: pipeline_stage;
  stocks_passed: int;
  stocks_failed: int;
  execution_time_ms: float;
}

type triple_hit = {
  symbol: string;
  market: string;
  darvas_signal: string;
  piotroski_score: int;
  coffee_can_pass: bool;
  fundamentals: (string * float) list;
  confidence: float;
}

(* Market access *)
val markets : market list
val find_market : string -> market option
val list_markets : unit -> unit

(* Pipeline execution *)
val run_pipeline : string -> string list -> string list
val generate_daily_report : string -> string list -> daily_report
val batch_screen : string list -> unit

(* Reporting *)
val report_to_string : daily_report -> string
val calculate_market_stats : triple_hit list -> string
val export_to_csv : string -> triple_hit list -> unit
