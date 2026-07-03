(* Advanced Statistical Analysis for Stock Screening
   Uses containers, zarith, and core packages for sophisticated analysis *)

open Printf

type price_series = float list
type returns_series = float list

(* ── Statistical Core ──────────────────────────────────────────────────────── *)

let mean values =
  match values with
  | [] -> None
  | _ ->
      let sum = List.fold_left (+.) 0.0 values in
      Some (sum /. Float.of_int (List.length values))

let variance values =
  match mean values with
  | None -> None
  | Some m ->
      let squared_diffs = List.map (fun x -> (x -. m) ** 2.0) values in
      let sum = List.fold_left (+.) 0.0 squared_diffs in
      Some (sum /. Float.of_int (List.length values))

let stddev values =
  match variance values with
  | None -> None
  | Some v -> Some (Float.sqrt v)

let skewness values =
  match mean values, stddev values with
  | Some m, Some s when s <> 0.0 ->
      let n = Float.of_int (List.length values) in
      let cubed_diffs = List.map (fun x -> ((x -. m) /. s) ** 3.0) values in
      let sum = List.fold_left (+.) 0.0 cubed_diffs in
      Some (sum /. n)
  | _ -> None

let kurtosis values =
  match mean values, stddev values with
  | Some m, Some s when s <> 0.0 ->
      let n = Float.of_int (List.length values) in
      let fourth_diffs = List.map (fun x -> ((x -. m) /. s) ** 4.0) values in
      let sum = List.fold_left (+.) 0.0 fourth_diffs in
      Some ((sum /. n) -. 3.0)  (* Excess kurtosis *)
  | _ -> None

let median values =
  let sorted = List.sort Float.compare values in
  let len = List.length sorted in
  if len = 0 then None
  else if len mod 2 = 0 then
    let mid1 = List.nth sorted ((len / 2) - 1) in
    let mid2 = List.nth sorted (len / 2) in
    Some ((mid1 +. mid2) /. 2.0)
  else
    Some (List.nth sorted (len / 2))

let quartiles values =
  let sorted = List.sort Float.compare values in
  let len = List.length sorted in
  if len < 4 then None
  else
    let q1 = List.nth sorted (len / 4) in
    let q2 = List.nth sorted (len / 2) in
    let q3 = List.nth sorted ((3 * len) / 4) in
    Some (q1, q2, q3)

let iqr values =
  match quartiles values with
  | Some (q1, _, q3) -> Some (q3 -. q1)
  | None -> None

(* ── Return Analysis ──────────────────────────────────────────────────────── *)

let log_returns prices =
  let rec pairs = function
    | [] | [_] -> []
    | x :: (y :: _ as tl) -> (x, y) :: pairs tl
  in
  List.fold_left (fun acc (prev, curr) ->
    if prev > 0.0 && curr > 0.0 then
      Float.log (curr /. prev) :: acc
    else
      acc
  ) [] (List.rev (pairs prices))

let simple_returns prices =
  let rec pairs = function
    | [] | [_] -> []
    | x :: (y :: _ as tl) -> (x, y) :: pairs tl
  in
  List.fold_left (fun acc (prev, curr) ->
    if prev <> 0.0 then
      ((curr -. prev) /. prev) :: acc
    else
      acc
  ) [] (List.rev (pairs prices))

(* ── Risk Metrics ─────────────────────────────────────────────────────────── *)

let sharpe_ratio returns risk_free_rate =
  match mean returns with
  | None -> None
  | Some m ->
      match stddev returns with
      | None -> None
      | Some s when s <> 0.0 -> Some ((m -. risk_free_rate) /. s)
      | _ -> None

let sortino_ratio returns downside_target =
  match mean returns with
  | None -> None
  | Some m ->
      let downside_values = List.filter (fun r -> r < downside_target) returns in
      (match downside_values with
      | [] -> Some (m -. downside_target)
      | _ ->
          let squared_diffs = List.map (fun x -> (Float.max 0.0 (downside_target -. x)) ** 2.0) returns in
          let sum = List.fold_left (+.) 0.0 squared_diffs in
          let downside_dev = Float.sqrt (sum /. Float.of_int (List.length returns)) in
          if downside_dev > 0.0 then
            Some ((m -. downside_target) /. downside_dev)
          else
            None)

let max_drawdown prices =
  match prices with
  | [] -> None
  | _ ->
      let running_max = ref (List.hd prices) in
      let max_dd = ref 0.0 in
      List.iter (fun p ->
        if p > !running_max then running_max := p;
        let dd = (p -. !running_max) /. !running_max in
        if dd < !max_dd then max_dd := dd
      ) prices;
      Some !max_dd

let calmar_ratio returns prices annual_factor =
  match mean returns with
  | None -> None
  | Some ret ->
      match max_drawdown prices with
      | None -> None
      | Some dd when dd <> 0.0 ->
          Some ((ret *. annual_factor) /. Float.abs dd)
      | _ -> None

(* ── Correlation & Covariance ────────────────────────────────────────────── *)

let covariance series1 series2 =
  match mean series1, mean series2 with
  | None, _ | _, None -> None
  | Some m1, Some m2 ->
      if List.length series1 <> List.length series2 then None
      else
        let products = List.map2 (fun x y -> (x -. m1) *. (y -. m2)) series1 series2 in
        let sum = List.fold_left (+.) 0.0 products in
        Some (sum /. Float.of_int (List.length series1))

let correlation series1 series2 =
  match covariance series1 series2 with
  | None -> None
  | Some cov ->
      (match stddev series1, stddev series2 with
      | Some s1, Some s2 when s1 > 0.0 && s2 > 0.0 ->
          Some (cov /. (s1 *. s2))
      | _ -> None)

let correlation_matrix series_list =
  let n = List.length series_list in
  Array.init n (fun i ->
    Array.init n (fun j ->
      if i = j then Some 1.0
      else
        match correlation (List.nth series_list i) (List.nth series_list j) with
        | Some c -> Some c
        | None -> None
    )
  )

(* ── Rolling Metrics ──────────────────────────────────────────────────────── *)

let rolling_mean values window =
  let len = List.length values in
  if len < window then []
  else
    List.init (len - window + 1) (fun i ->
      let window_values = List.filteri (fun idx _ -> idx >= i && idx < i + window) values in
      match mean window_values with
      | Some m -> m
      | None -> 0.0
    )

let rolling_std values window =
  let len = List.length values in
  if len < window then []
  else
    List.init (len - window + 1) (fun i ->
      let window_values = List.filteri (fun idx _ -> idx >= i && idx < i + window) values in
      match stddev window_values with
      | Some s -> s
      | None -> 0.0
    )

let rolling_sharpe returns window risk_free =
  let len = List.length returns in
  if len < window then []
  else
    List.init (len - window + 1) (fun i ->
      let window_returns = List.filteri (fun idx _ -> idx >= i && idx < i + window) returns in
      match sharpe_ratio window_returns risk_free with
      | Some s -> s
      | None -> 0.0
    )

(* ── Distribution Analysis ────────────────────────────────────────────────── *)

type distribution = {
  mean: float option;
  std: float option;
  skew: float option;
  kurt: float option;
  median: float option;
  q1: float option;
  q3: float option;
  iqr: float option;
  min: float;
  max: float;
}

let analyze_distribution values =
  let min_val = List.fold_left Float.min Float.infinity values in
  let max_val = List.fold_left Float.max Float.neg_infinity values in

  match quartiles values with
  | Some (q1, _, q3) ->
      {
        mean = mean values;
        std = stddev values;
        skew = skewness values;
        kurt = kurtosis values;
        median = median values;
        q1 = Some q1;
        q3 = Some q3;
        iqr = iqr values;
        min = min_val;
        max = max_val;
      }
  | None ->
      {
        mean = mean values;
        std = stddev values;
        skew = skewness values;
        kurt = kurtosis values;
        median = median values;
        q1 = None;
        q3 = None;
        iqr = None;
        min = min_val;
        max = max_val;
      }

let distribution_to_string dist =
  sprintf "Distribution Analysis:\n\
           Mean: %s\n\
           StdDev: %s\n\
           Skewness: %s\n\
           Kurtosis: %s\n\
           Median: %s\n\
           Q1: %s, Q3: %s, IQR: %s\n\
           Range: [%.2f, %.2f]"
    (match dist.mean with Some m -> sprintf "%.4f" m | None -> "N/A")
    (match dist.std with Some s -> sprintf "%.4f" s | None -> "N/A")
    (match dist.skew with Some s -> sprintf "%.4f" s | None -> "N/A")
    (match dist.kurt with Some k -> sprintf "%.4f" k | None -> "N/A")
    (match dist.median with Some m -> sprintf "%.4f" m | None -> "N/A")
    (match dist.q1 with Some q -> sprintf "%.4f" q | None -> "N/A")
    (match dist.q3 with Some q -> sprintf "%.4f" q | None -> "N/A")
    (match dist.iqr with Some i -> sprintf "%.4f" i | None -> "N/A")
    dist.min dist.max

(* ── Portfolio Analysis ──────────────────────────────────────────────────── *)

type portfolio = {
  weights: float array;
  returns_series: float list;
  expected_return: float option;
  volatility: float option;
  sharpe: float option;
  sortino: float option;
}

let portfolio_expected_return asset_returns weights =
  if Array.length weights <> List.length asset_returns then None
  else
    let weighted_sum = ref 0.0 in
    List.iteri (fun i ret ->
      match mean ret with
      | Some m -> weighted_sum := !weighted_sum +. (weights.(i) *. m)
      | None -> ()
    ) asset_returns;
    Some !weighted_sum

let portfolio_variance asset_returns weights corr_matrix =
  if Array.length weights <> Array.length corr_matrix then None
  else
    let n = Array.length weights in
    let variance_sum = ref 0.0 in

    for i = 0 to n - 1 do
      for j = 0 to n - 1 do
        let std_i = match stddev (List.nth asset_returns i) with
          | Some s -> s | None -> 0.0
        in
        let std_j = match stddev (List.nth asset_returns j) with
          | Some s -> s | None -> 0.0
        in
        let corr = match corr_matrix.(i).(j) with
          | Some c -> c | None -> 0.0
        in
        variance_sum := !variance_sum +. (weights.(i) *. weights.(j) *. std_i *. std_j *. corr)
      done
    done;

    Some (Float.sqrt !variance_sum)

(* ── Anomaly Detection ──────────────────────────────────────────────────── *)

let detect_outliers values z_threshold =
  match mean values, stddev values with
  | Some m, Some s when s > 0.0 ->
      List.filter (fun v ->
        let z_score = (v -. m) /. s in
        Float.abs z_score > z_threshold
      ) values
  | _ -> []

let iqr_outliers values =
  match quartiles values with
  | Some (q1, _, q3) ->
      let iqr_val = q3 -. q1 in
      let lower_bound = q1 -. (1.5 *. iqr_val) in
      let upper_bound = q3 +. (1.5 *. iqr_val) in
      List.filter (fun v -> v < lower_bound || v > upper_bound) values
  | None -> []

(* ── Volume Analysis (Chaikin Money Flow) ──────────────────────────────── *)

type ohlcv = {
  open_: float;
  high: float;
  low: float;
  close: float;
  volume: float;
}

let chaikin_money_flow candles period =
  if List.length candles < period then None
  else
    let recent = List.filteri (fun i _ -> i >= List.length candles - period) candles in

    let money_flow_values = List.map (fun candle ->
      let high_low_diff = candle.high -. candle.low in
      if high_low_diff = 0.0 then 0.0
      else
        let mf_multiplier = ((candle.close -. candle.low) -. (candle.high -. candle.close)) /. high_low_diff in
        mf_multiplier *. candle.volume
    ) recent in

    let volume_sum = List.fold_left (fun acc c -> acc +. c.volume) 0.0 recent in
    let mf_sum = List.fold_left (+.) 0.0 money_flow_values in

    if volume_sum = 0.0 then None
    else Some (mf_sum /. volume_sum)

let is_accumulation cmf_value =
  match cmf_value with
  | None -> false
  | Some cmf -> cmf > 0.05

let is_strong_accumulation cmf_value =
  match cmf_value with
  | None -> false
  | Some cmf -> cmf > 0.25

let cmf_signal cmf_value =
  match cmf_value with
  | None -> "INSUFFICIENT_DATA"
  | Some cmf when cmf > 0.25 -> "STRONG_ACCUMULATION"
  | Some cmf when cmf > 0.05 -> "ACCUMULATION"
  | Some cmf when cmf > -0.05 -> "NEUTRAL"
  | Some cmf when cmf > -0.25 -> "DISTRIBUTION"
  | Some _ -> "STRONG_DISTRIBUTION"

(* ── Momentum & Trend Analysis ─────────────────────────────────────────── *)

let rsi prices period =
  if List.length prices < period + 1 then []
  else
    let returns = simple_returns prices in
    let gains = List.filter (fun r -> r > 0.0) returns in
    let losses = List.filter (fun r -> r < 0.0) returns in

    let avg_gain = match mean gains with Some m -> m | None -> 0.0 in
    let avg_loss = match mean (List.map Float.abs losses) with Some m -> m | None -> 0.0 in

    if avg_loss = 0.0 then [100.0]
    else
      let rs = avg_gain /. avg_loss in
      [100.0 -. (100.0 /. (1.0 +. rs))]

let momentum prices lookback =
  if List.length prices < lookback then None
  else
    let current = List.hd (List.rev prices) in
    let past = List.nth (List.rev prices) lookback in
    Some ((current -. past) /. past *. 100.0)

let rate_of_change prices period =
  if List.length prices < period then []
  else
    List.init (List.length prices - period) (fun i ->
      let curr = List.nth prices (i + period) in
      let prev = List.nth prices i in
      if prev <> 0.0 then
        ((curr -. prev) /. prev) *. 100.0
      else
        0.0
    )

(* ── Performance Summary ──────────────────────────────────────────────── *)

type performance = {
  total_return: float option;
  annual_return: float option;
  volatility: float option;
  sharpe_ratio: float option;
  sortino_ratio: float option;
  max_dd: float option;
  calmar: float option;
  win_rate: float option;
  profit_factor: float option;
}

let calculate_performance prices returns =
  let total_return =
    match prices with
    | [] | [_] -> None
    | hd :: tl ->
        let last = List.hd (List.rev (hd :: tl)) in
        Some ((last -. hd) /. hd)
  in

  {
    total_return;
    annual_return = (match mean returns with Some m -> Some (m *. 252.0) | None -> None);
    volatility = stddev returns;
    sharpe_ratio = sharpe_ratio returns 0.02;
    sortino_ratio = sortino_ratio returns 0.0;
    max_dd = max_drawdown prices;
    calmar = calmar_ratio returns prices 252.0;
    win_rate = (
      let wins = List.filter (fun r -> r > 0.0) returns in
      if List.length returns = 0 then None
      else Some (Float.of_int (List.length wins) /. Float.of_int (List.length returns))
    );
    profit_factor = (
      let gains = List.fold_left (+.) 0.0 (List.filter (fun r -> r > 0.0) returns) in
      let losses = Float.abs (List.fold_left (+.) 0.0 (List.filter (fun r -> r < 0.0) returns)) in
      if losses = 0.0 then Some Float.infinity
      else if losses > 0.0 then Some (gains /. losses)
      else None
    );
  }

let performance_to_string perf =
  sprintf "Performance Metrics:\n\
           Total Return: %s\n\
           Annual Return: %s\n\
           Volatility: %s\n\
           Sharpe Ratio: %s\n\
           Sortino Ratio: %s\n\
           Max Drawdown: %s\n\
           Calmar Ratio: %s\n\
           Win Rate: %s\n\
           Profit Factor: %s"
    (match perf.total_return with Some r -> sprintf "%.2f%%" (r *. 100.0) | None -> "N/A")
    (match perf.annual_return with Some r -> sprintf "%.2f%%" (r *. 100.0) | None -> "N/A")
    (match perf.volatility with Some v -> sprintf "%.4f" v | None -> "N/A")
    (match perf.sharpe_ratio with Some s -> sprintf "%.4f" s | None -> "N/A")
    (match perf.sortino_ratio with Some s -> sprintf "%.4f" s | None -> "N/A")
    (match perf.max_dd with Some d -> sprintf "%.2f%%" (d *. 100.0) | None -> "N/A")
    (match perf.calmar with Some c -> sprintf "%.4f" c | None -> "N/A")
    (match perf.win_rate with Some w -> sprintf "%.2f%%" (w *. 100.0) | None -> "N/A")
    (match perf.profit_factor with Some pf ->
      if pf = Float.infinity then "Infinite" else sprintf "%.2f" pf
    | None -> "N/A")
