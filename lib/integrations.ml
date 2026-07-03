(* Integration layer for multi-market data sources and tools
   Bridges claude-stock-tools functionality into Merlin's OCaml architecture *)

open Printf

(* Market definitions *)
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

(* Predefined markets *)
let markets = [
  {
    code = "IN";
    name = "India";
    exchange = "NSE/BSE";
    symbol_count = 2681;
    data_source = "yfinance + nsepython";
    currency = "INR";
    timezone = "IST";
    market_cap_floor_usd = 60_000_000.0;  (* ₹500 Cr ~ $60M *)
  };
  {
    code = "US";
    name = "United States";
    exchange = "NYSE/NASDAQ";
    symbol_count = 8000;
    data_source = "yfinance";
    currency = "USD";
    timezone = "EST";
    market_cap_floor_usd = 1_000_000_000.0;  (* $1B *)
  };
  {
    code = "EU";
    name = "Europe";
    exchange = "EUREX/LSE";
    symbol_count = 3000;
    data_source = "yfinance";
    currency = "EUR";
    timezone = "CET";
    market_cap_floor_usd = 1_000_000_000.0;  (* €1B *)
  };
  {
    code = "JP";
    name = "Japan";
    exchange = "TSE";
    symbol_count = 3600;
    data_source = "yfinance";
    currency = "JPY";
    timezone = "JST";
    market_cap_floor_usd = 800_000_000.0;  (* ¥100B ~ $800M *)
  };
  {
    code = "KR";
    name = "South Korea";
    exchange = "KOSPI/KOSDAQ";
    symbol_count = 2500;
    data_source = "yfinance";
    currency = "KRW";
    timezone = "KST";
    market_cap_floor_usd = 800_000_000.0;  (* ₩100B ~ $800M *)
  };
  {
    code = "SG";
    name = "Singapore";
    exchange = "SGX";
    symbol_count = 700;
    data_source = "yfinance";
    currency = "SGD";
    timezone = "SGT";
    market_cap_floor_usd = 130_000_000.0;  (* S$100M ~ $130M *)
  };
]

let find_market code =
  List.find_opt (fun m -> m.code = code) markets

let list_markets () =
  List.iter (fun m ->
    printf "%s: %s (%s)\n  Exchange: %s | Symbols: %d | Source: %s\n"
      m.code m.name m.currency m.exchange m.symbol_count m.data_source
  ) markets

(* Daily report metadata *)
type daily_report = {
  market: string;
  generated_at: string;
  total_symbols: int;
  darvas_signals: int;
  triple_hits: int;
  filename: string;
}

(* Pipeline stages *)
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

(* Triple hit detection *)
type triple_hit = {
  symbol: string;
  market: string;
  darvas_signal: string;  (* BREAKOUT_BUY, BREAKDOWN_SELL, IN_BOX *)
  piotroski_score: int;   (* 0-9 *)
  coffee_can_pass: bool;
  fundamentals: (string * float) list;
  confidence: float;      (* 0.0-1.0, based on how close each criterion *)
}

(* Pipeline coordinator *)
let run_pipeline market_code stocks =
  let market = match find_market market_code with
    | Some m -> m
    | None -> failwith (sprintf "Unknown market: %s" market_code)
  in

  printf "🚀 Starting pipeline for %s (%d symbols)\n" market.name (List.length stocks);

  (* Stage 1: Darvas Box *)
  printf "📊 Stage 1: Darvas Box screening...\n";
  let start_time = Unix.gettimeofday () in
  let darvas_passes = List.filter (fun stock ->
    (* Run darvas_screen from screener module *)
    let result = Merlin_lib.Screener.darvas_screen {
      symbol = stock;
      market = market_code;
      ohlcv = [];
      fundamentals = [];
    } in
    result.passed
  ) stocks in
  let stage1_time = (Unix.gettimeofday () -. start_time) *. 1000.0 in
  printf "   ✓ %d/%d passed Darvas (%.0f ms)\n"
    (List.length darvas_passes) (List.length stocks) stage1_time;

  (* Stage 2: Piotroski (only on Darvas passes) *)
  printf "📊 Stage 2: Piotroski F-Score...\n";
  let start_time = Unix.gettimeofday () in
  let piotroski_passes = List.filter (fun symbol ->
    let result = Merlin_lib.Screener.piotroski_screen {
      symbol;
      market = market_code;
      ohlcv = [];
      fundamentals = [];
    } in
    result.passed
  ) darvas_passes in
  let stage2_time = (Unix.gettimeofday () -. start_time) *. 1000.0 in
  printf "   ✓ %d/%d passed Piotroski (%.0f ms)\n"
    (List.length piotroski_passes) (List.length darvas_passes) stage2_time;

  (* Stage 3: Coffee Can (only on Piotroski passes) *)
  printf "📊 Stage 3: Coffee Can Portfolio...\n";
  let start_time = Unix.gettimeofday () in
  let triple_hits = List.filter (fun symbol ->
    let result = Merlin_lib.Screener.coffee_can_screen {
      symbol;
      market = market_code;
      ohlcv = [];
      fundamentals = [];
    } in
    result.passed
  ) piotroski_passes in
  let stage3_time = (Unix.gettimeofday () -. start_time) *. 1000.0 in
  printf "   ✓ %d/%d passed Coffee Can (%.0f ms)\n"
    (List.length triple_hits) (List.length piotroski_passes) stage3_time;

  printf "\n🎯 PIPELINE RESULTS\n";
  printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
  printf "Market: %s\n" market.name;
  printf "Total processed: %d\n" (List.length stocks);
  printf "Darvas breakouts: %d (%.1f%%)\n"
    (List.length darvas_passes)
    (Float.of_int (List.length darvas_passes) /. Float.of_int (List.length stocks) *. 100.0);
  printf "Piotroski strong: %d (%.1f%%)\n"
    (List.length piotroski_passes)
    (Float.of_int (List.length piotroski_passes) /. Float.of_int (List.length darvas_passes) *. 100.0);
  printf "Triple Hits: %d (%.1f%%)\n"
    (List.length triple_hits)
    (Float.of_int (List.length triple_hits) /. Float.of_int (List.length stocks) *. 100.0);

  triple_hits

(* Daily report generator *)
let generate_daily_report market_code stocks =
  let market = match find_market market_code with
    | Some m -> m
    | None -> failwith (sprintf "Unknown market: %s" market_code)
  in

  let timestamp = Unix.time () |> int_of_float |> string_of_int in
  let triple_hits = run_pipeline market_code stocks in

  {
    market = market.name;
    generated_at = Printf.sprintf "%s UTC" (Unix.time () |> int_of_float |> string_of_int);
    total_symbols = List.length stocks;
    darvas_signals = List.length (List.filter (fun s ->
      let r = Merlin_lib.Screener.darvas_screen {
        symbol = s; market = market_code; ohlcv = []; fundamentals = []
      } in
      r.passed
    ) stocks);
    triple_hits = List.length triple_hits;
    filename = Printf.sprintf "%s_daily_report_%s.csv" market_code timestamp;
  }

(* Report formatting *)
let report_to_string report =
  sprintf "Daily Report: %s\n\
           Generated: %s\n\
           Symbols Scanned: %d\n\
           Darvas Signals: %d\n\
           Triple Hits: %d\n\
           Report: %s"
    report.market report.generated_at report.total_symbols
    report.darvas_signals report.triple_hits report.filename

(* Multi-market batch screening *)
let batch_screen markets_list =
  printf "\n🌍 GLOBAL MARKET SCREENING\n";
  printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n";

  List.iter (fun market_code ->
    match find_market market_code with
    | Some market ->
        printf "📍 %s (%s)\n" market.name market.exchange;
        printf "   Symbols: %d | Source: %s\n" market.symbol_count market.data_source;
        printf "   Market cap floor: $%.0f M\n\n" (market.market_cap_floor_usd /. 1_000_000.0)
    | None -> ()
  ) markets_list

(* Performance metrics *)
let calculate_market_stats results =
  let total = List.length results in
  let breakouts = List.length (List.filter (fun t ->
    match t.darvas_signal with
    | "BREAKOUT_BUY" -> true
    | _ -> false
  ) results) in
  let high_quality = List.length (List.filter (fun t ->
    t.piotroski_score >= 7 && t.coffee_can_pass
  ) results) in

  {|Market Statistics:
  Total candidates: |} ^ string_of_int total ^ {|
  Breakout signals: |} ^ string_of_int breakouts ^ {| (|} ^
    Printf.sprintf "%.1f" (Float.of_int breakouts /. Float.of_int total *. 100.0) ^ {|%)
  High-quality: |} ^ string_of_int high_quality ^ {| (|} ^
    Printf.sprintf "%.1f" (Float.of_int high_quality /. Float.of_int total *. 100.0) ^ {|%)|} ^
    "\n"

(* Export utilities *)
let export_to_csv filename triple_hits =
  let oc = open_out filename in
  fprintf oc "Symbol,Market,Darvas Signal,Piotroski Score,Coffee Can,Confidence\n";
  List.iter (fun hit ->
    fprintf oc "%s,%s,%s,%d,%b,%.2f\n"
      hit.symbol hit.market hit.darvas_signal
      hit.piotroski_score hit.coffee_can_pass hit.confidence
  ) triple_hits;
  close_out oc;
  printf "✓ Results exported to %s\n" filename
