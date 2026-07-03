(* Stock Screener — multi-strategy, multi-market screening *)

open Printf

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

let string_of_result r =
  let pass_str = if r.passed then "YES" else "NO" in
  let score_str = match r.score with
    | Some s -> sprintf "%.2f" s
    | None -> "N/A"
  in
  sprintf "%s,%s,%s,%s,%s" r.symbol r.strategy pass_str score_str r.note

(* Helpers *)
let safe_float v =
  try Some (Float.of_string (String.trim v))
  with _ -> None

let pct_change new_val old_val =
  match new_val, old_val with
  | Some n, Some o when o <> 0.0 -> Some ((n -. o) /. Float.abs o *. 100.0)
  | _ -> None

let cagr latest earliest years =
  if latest <= 0.0 || earliest <= 0.0 || years < 1.0 then None
  else Some (((latest /. earliest) ** (1.0 /. years) -. 1.0) *. 100.0)

let sma series n =
  if List.length series < n then None
  else
    let last_n = List.filteri (fun i _ -> i >= List.length series - n) series in
    match last_n with
    | [] -> None
    | xs ->
        let sum = List.fold_left (+.) 0.0 xs in
        Some (sum /. Float.of_int (List.length xs))

(* Get field from fundamentals *)
let get_field stock key =
  try List.assoc key stock.fundamentals
  with Not_found -> None

(* Last price *)
let ltp stock =
  match List.rev stock.ohlcv with
  | [] -> None
  | hd :: _ -> Some hd.close

(* 52-week high *)
let high_52w stock =
  match stock.ohlcv with
  | [] -> None
  | xs ->
      let last_252 = List.filteri (fun i _ -> i >= List.length xs - 252) xs in
      let highs = List.map (fun o -> o.high) last_252 in
      match highs with
      | [] -> None
      | h :: rest -> Some (List.fold_left Float.max h rest)

(* Volume helpers *)
let volumes stock =
  List.map (fun o -> o.volume) stock.ohlcv

let avg_volume_20d stock =
  let vols = volumes stock in
  let last_20 = List.filteri (fun i _ -> i >= List.length vols - 20) vols in
  match last_20 with
  | [] -> None
  | vs ->
      let sum = List.fold_left (+.) 0.0 vs in
      Some (sum /. Float.of_int (List.length vs))

(* Strategy: Darvas Box *)
let darvas_screen stock =
  let near_high_pct = 10.0 in
  let vol_mult_min = 1.5 in

  match high_52w stock, ltp stock, avg_volume_20d stock with
  | Some hi_52w, Some ltp_val, Some avg_vol when hi_52w > 0.0 ->
      let off_high = (hi_52w -. ltp_val) /. hi_52w *. 100.0 in
      let near_high = off_high <= near_high_pct in

      let vtoday = match List.rev (volumes stock) with
        | [] -> 0.0
        | hd :: _ -> hd
      in

      let vmult = if avg_vol > 0.0 then vtoday /. avg_vol else 0.0 in
      let vol_ok = vmult >= vol_mult_min in
      let passed = near_high && vol_ok in

      {
        symbol = stock.symbol;
        strategy = "darvas";
        passed;
        score = Some (-.off_high);
        metrics = [
          ("LTP", sprintf "%.2f" ltp_val);
          ("High_52w", sprintf "%.2f" hi_52w);
          ("Off_High%", sprintf "%.1f" off_high);
          ("Vol_x20d", sprintf "%.2f" vmult);
        ];
        note = if passed then "BREAKOUT" else (if near_high then "near_high" else "");
      }
  | _ ->
      {
        symbol = stock.symbol;
        strategy = "darvas";
        passed = false;
        score = None;
        metrics = [];
        note = "insufficient_data";
      }

(* Strategy: Piotroski F-Score *)
let piotroski_screen stock =
  let ni = get_field stock "net_income" in
  let roa = get_field stock "roa" in
  let roa_prev = get_field stock "roa_prev" in
  let cfo = get_field stock "cfo" in
  let lev = get_field stock "debt_to_assets" in
  let lev_prev = get_field stock "debt_to_assets_prev" in
  let cr = get_field stock "current_ratio" in
  let cr_prev = get_field stock "current_ratio_prev" in
  let sh = get_field stock "shares" in
  let sh_prev = get_field stock "shares_prev" in
  let gm = get_field stock "gross_margin" in
  let gm_prev = get_field stock "gross_margin_prev" in
  let at = get_field stock "asset_turnover" in
  let at_prev = get_field stock "asset_turnover_prev" in

  let pts = ref 0 in
  let checks = ref [] in

  let add name cond =
    let score = if cond then 1 else 0 in
    checks := (name, if cond then "1" else "0") :: !checks;
    pts := !pts + score
  in

  (match roa with
  | Some r when r > 0.0 -> add "ROA>0" true
  | _ -> add "ROA>0" false);

  (match cfo with
  | Some c when c > 0.0 -> add "CFO>0" true
  | _ -> add "CFO>0" false);

  (match roa, roa_prev with
  | Some r, Some rp when r > rp -> add "dROA>0" true
  | _ -> add "dROA>0" false);

  (match cfo, ni with
  | Some c, Some n when c > n -> add "Accrual_ok" true
  | _ -> add "Accrual_ok" false);

  (match lev, lev_prev with
  | Some l, Some lp when l < lp -> add "dLev<0" true
  | _ -> add "dLev<0" false);

  (match cr, cr_prev with
  | Some c, Some cp when c > cp -> add "dCR>0" true
  | _ -> add "dCR>0" false);

  (match sh, sh_prev with
  | Some s, Some sp when s <= sp -> add "NoDilute" true
  | _ -> add "NoDilute" false);

  (match gm, gm_prev with
  | Some g, Some gp when g > gp -> add "dGM>0" true
  | _ -> add "dGM>0" false);

  (match at, at_prev with
  | Some a, Some ap when a > ap -> add "dAT>0" true
  | _ -> add "dAT>0" false);

  let score = !pts in
  let passed = score >= 7 in
  {
    symbol = stock.symbol;
    strategy = "piotroski";
    passed;
    score = Some (Float.of_int score);
    metrics = ("F_Score", string_of_int score) :: !checks;
    note = if passed then "strong" else "";
  }

(* Strategy: Coffee Can Portfolio *)
let coffee_can_screen stock =
  let roe = get_field stock "roe" in
  let roe_hist = get_field stock "roe_history" in
  let revenue = get_field stock "revenue" in
  let revenue_5y = get_field stock "revenue_5y_ago" in
  let debt_to_equity = get_field stock "debt_to_equity" in

  let roe_min = 15.0 in
  let rev_growth_min = 10.0 in
  let de_max = 1.0 in

  let roe_ok = match roe with
    | Some r when r >= roe_min -> true
    | _ -> false
  in

  let rev_cagr = cagr revenue revenue_5y 5.0 in
  let rev_ok = match rev_cagr with
    | Some rc when rc >= rev_growth_min -> true
    | _ -> false
  in

  let de_ok = match debt_to_equity with
    | Some d when d <= de_max -> true
    | _ -> false
  in

  let passed = roe_ok && rev_ok && de_ok in

  {
    symbol = stock.symbol;
    strategy = "coffee_can";
    passed;
    score = roe;
    metrics = [
      ("ROE", (match roe with Some r -> sprintf "%.1f" r | None -> "N/A"));
      ("RevCAGR5y", (match rev_cagr with Some rc -> sprintf "%.1f" rc | None -> "N/A"));
      ("DE", (match debt_to_equity with Some d -> sprintf "%.2f" d | None -> "N/A"));
      ("ROE>=15", if roe_ok then "1" else "0");
      ("RevCAGR>=10", if rev_ok then "1" else "0");
      ("DE<=1", if de_ok then "1" else "0");
    ];
    note = if passed then "quality_compounder" else "";
  }

(* Strategy: Magic Formula (Greenblatt) *)
let magic_formula_screen stock =
  let roe = get_field stock "roe" in
  let earnings_yield = get_field stock "earnings_yield" in

  let roe_ok = match roe with
    | Some r when r > 15.0 -> true
    | _ -> false
  in

  let ey_ok = match earnings_yield with
    | Some ey when ey > 0.0 -> true
    | _ -> false
  in

  let passed = roe_ok && ey_ok in

  {
    symbol = stock.symbol;
    strategy = "magic_formula";
    passed;
    score = earnings_yield;
    metrics = [
      ("ROE", (match roe with Some r -> sprintf "%.1f" r | None -> "N/A"));
      ("Earnings_Yield", (match earnings_yield with Some ey -> sprintf "%.2f%%" ey | None -> "N/A"));
      ("ROE>15", if roe_ok then "1" else "0");
      ("EY>0", if ey_ok then "1" else "0");
    ];
    note = if passed then "cheap_quality" else "";
  }

(* Strategy: Golden Crossover (50/200 day MA) *)
let golden_crossover_screen stock =
  let closes = List.map (fun o -> o.close) stock.ohlcv in

  let sma_50 = sma closes 50 in
  let sma_200 = sma closes 200 in

  match sma_50, sma_200 with
  | Some s50, Some s200 ->
      let passed = s50 > s200 in
      let ratio = s50 /. s200 in
      {
        symbol = stock.symbol;
        strategy = "golden_crossover";
        passed;
        score = Some ratio;
        metrics = [
          ("SMA50", sprintf "%.2f" s50);
          ("SMA200", sprintf "%.2f" s200);
          ("Ratio", sprintf "%.4f" ratio);
        ];
        note = if passed then "bullish" else "bearish";
      }
  | _ ->
      {
        symbol = stock.symbol;
        strategy = "golden_crossover";
        passed = false;
        score = None;
        metrics = [];
        note = "insufficient_data";
      }

(* Strategy: Chaikin Money Flow (Accumulation Detection) *)
let cmf_screen stock =
  if List.length stock.ohlcv < 20 then
    {
      symbol = stock.symbol;
      strategy = "cmf_accumulation";
      passed = false;
      score = None;
      metrics = [];
      note = "insufficient_data";
    }
  else
    let candles = List.map (fun o ->
      {
        Advanced_analysis.open_ = o.open_;
        high = o.high;
        low = o.low;
        close = o.close;
        volume = o.volume;
      }
    ) stock.ohlcv in

    let cmf_20 = Advanced_analysis.chaikin_money_flow candles 20 in
    let cmf_50 = Advanced_analysis.chaikin_money_flow candles 50 in

    let accumulated = Advanced_analysis.is_strong_accumulation cmf_20 in
    let trend = Advanced_analysis.cmf_signal cmf_20 in

    let score_val = match cmf_20 with
      | Some c -> c
      | None -> -1.0
    in

    {
      symbol = stock.symbol;
      strategy = "cmf_accumulation";
      passed = accumulated;
      score = Some score_val;
      metrics = [
        ("CMF_20", sprintf "%.4f" (match cmf_20 with Some c -> c | None -> 0.0));
        ("CMF_50", sprintf "%.4f" (match cmf_50 with Some c -> c | None -> 0.0));
        ("Status", trend);
      ];
      note = if accumulated then "ACCUMULATION_PHASE" else trend;
    }

(* Run all strategies *)
let screen_stock stock =
  [
    darvas_screen stock;
    piotroski_screen stock;
    coffee_can_screen stock;
    magic_formula_screen stock;
    golden_crossover_screen stock;
    cmf_screen stock;
  ]

(* Batch screening *)
let screen_market stocks =
  List.concat (List.map screen_stock stocks)

(* Sort and filter results *)
let rank_results results strategy_name =
  results
  |> List.filter (fun r -> r.strategy = strategy_name && r.passed)
  |> List.sort (fun a b ->
      match a.score, b.score with
      | Some sa, Some sb -> Float.compare sb sa
      | Some _, None -> -1
      | None, Some _ -> 1
      | None, None -> 0
    )

(* Format for CSV output *)
let results_to_csv results =
  let header = "Symbol,Strategy,Pass,Score,Note" in
  let rows = List.map string_of_result results in
  String.concat "\n" (header :: rows)
