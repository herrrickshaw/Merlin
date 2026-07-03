(* Backtesting Module - Validates filter performance over historical data
   Tests Darvas + Piotroski + Coffee Can + CMF on 5 years of historical prices *)

open Printf

(* ─── Types ────────────────────────────────────────────────────────────── *)

type price_point = {
  date: string;
  open_: float;
  high: float;
  low: float;
  close: float;
  volume: float;
  adjusted_close: float;
}

type trade = {
  symbol: string;
  entry_date: string;
  entry_price: float;
  exit_date: string;
  exit_price: float;
  return_pct: float;
  days_held: int;
  volume_avg: float;
}

type backtest_results = {
  symbol: string;
  total_trades: int;
  winning_trades: int;
  losing_trades: int;
  win_rate: float;
  avg_win: float;
  avg_loss: float;
  profit_factor: float;
  total_return: float;
  annual_return: float;
  max_drawdown: float;
  sharpe_ratio: float;
  sortino_ratio: float;
  calmar_ratio: float;
  trades: trade list;
}

type cohort_analysis = {
  entry_date: string;
  exit_date: string;
  symbols: string list;
  avg_return: float;
  median_return: float;
  std_return: float;
  win_rate: float;
  max_drawdown: float;
  sharpe_ratio: float;
  best_performer: string option;
  worst_performer: string option;
}

(* ─── Price Data Functions ─────────────────────────────────────────────── *)

let get_price_on_date prices date =
  try
    let price = List.find (fun p -> p.date = date) prices in
    Some price.adjusted_close
  with Not_found -> None

let get_price_after_date prices date ~days =
  let rec find_next prices remaining_days =
    match prices with
    | [] -> None
    | p :: rest ->
        if p.date > date then
          if remaining_days <= 0 then Some p.adjusted_close
          else find_next rest (remaining_days - 1)
        else
          find_next rest remaining_days
  in
  find_next prices days

(* ─── Return Calculation ────────────────────────────────────────────────── *)

let calculate_return entry_price exit_price =
  if entry_price = 0.0 then 0.0
  else ((exit_price -. entry_price) /. entry_price) *. 100.0

let calculate_annual_return total_return days =
  if days = 0 then 0.0
  else total_return *. (365.0 /. float_of_int days)

(* ─── Drawdown Calculation ─────────────────────────────────────────────── *)

let calculate_max_drawdown returns =
  if List.length returns = 0 then 0.0
  else
    let running_max = ref 0.0 in
    let max_dd = ref 0.0 in

    List.iter (fun ret ->
      let cumulative = !running_max +. ret in
      if cumulative > !running_max then running_max := cumulative;
      let dd = (cumulative -. !running_max) /. !running_max in
      if dd < !max_dd then max_dd := dd
    ) returns;

    !max_dd

(* ─── Statistical Measures ─────────────────────────────────────────────── *)

let mean values =
  if List.length values = 0 then 0.0
  else
    let sum = List.fold_left (+.) 0.0 values in
    sum /. float_of_int (List.length values)

let standard_deviation values =
  if List.length values <= 1 then 0.0
  else
    let m = mean values in
    let squared_diffs = List.map (fun x -> (x -. m) ** 2.0) values in
    let variance = (List.fold_left (+.) 0.0 squared_diffs) /. float_of_int (List.length values - 1) in
    Float.sqrt variance

let median values =
  let sorted = List.sort Float.compare values in
  let len = List.length sorted in
  if len = 0 then 0.0
  else if len mod 2 = 0 then
    let mid1 = List.nth sorted ((len / 2) - 1) in
    let mid2 = List.nth sorted (len / 2) in
    (mid1 +. mid2) /. 2.0
  else
    List.nth sorted (len / 2)

(* ─── Trade Analysis ──────────────────────────────────────────────────── *)

let analyze_trades trades =
  if List.length trades = 0 then
    {
      symbol = "N/A";
      total_trades = 0;
      winning_trades = 0;
      losing_trades = 0;
      win_rate = 0.0;
      avg_win = 0.0;
      avg_loss = 0.0;
      profit_factor = 0.0;
      total_return = 0.0;
      annual_return = 0.0;
      max_drawdown = 0.0;
      sharpe_ratio = 0.0;
      sortino_ratio = 0.0;
      calmar_ratio = 0.0;
      trades;
    }
  else
    let symbol = (List.hd trades).symbol in
    let total_trades = List.length trades in
    let winning = List.filter (fun t -> t.return_pct > 0.0) trades in
    let losing = List.filter (fun t -> t.return_pct < 0.0) trades in
    let winning_trades = List.length winning in
    let losing_trades = List.length losing in
    let win_rate = float_of_int winning_trades /. float_of_int total_trades in

    let winning_returns = List.map (fun t -> t.return_pct) winning in
    let losing_returns = List.map (fun t -> t.return_pct) losing in

    let avg_win = if List.length winning_returns = 0 then 0.0 else mean winning_returns in
    let avg_loss = if List.length losing_returns = 0 then 0.0 else mean losing_returns in

    let total_wins = List.fold_left (+.) 0.0 winning_returns in
    let total_losses = Float.abs (List.fold_left (+.) 0.0 losing_returns) in
    let profit_factor = if total_losses = 0.0 then 1.0 else total_wins /. total_losses in

    let all_returns = List.map (fun t -> t.return_pct) trades in
    let total_return = mean all_returns in
    let days_held_avg = mean (List.map (fun t -> float_of_int t.days_held) trades) in
    let annual_return = calculate_annual_return total_return (int_of_float days_held_avg) in

    let returns_series = List.map (fun t -> t.return_pct /. 100.0) trades in
    let max_dd = calculate_max_drawdown returns_series in

    let sharpe = if List.length returns_series = 0 then 0.0 else
      let ret = mean returns_series in
      let vol = standard_deviation returns_series in
      if vol = 0.0 then 0.0 else ret /. vol
    in

    let sortino = if List.length returns_series = 0 then 0.0 else
      let ret = mean returns_series in
      let downside = List.filter (fun r -> r < 0.0) returns_series in
      let downside_dev = if List.length downside = 0 then 0.0 else
        standard_deviation downside
      in
      if downside_dev = 0.0 then 0.0 else ret /. downside_dev
    in

    let calmar = if max_dd >= 0.0 || Float.is_nan max_dd then 0.0 else
      annual_return /. (-.max_dd *. 100.0)
    in

    {
      symbol;
      total_trades;
      winning_trades;
      losing_trades;
      win_rate;
      avg_win;
      avg_loss;
      profit_factor;
      total_return;
      annual_return;
      max_drawdown;
      sharpe_ratio = sharpe;
      sortino_ratio = sortino;
      calmar_ratio = calmar;
      trades;
    }

(* ─── Cohort Analysis ──────────────────────────────────────────────────── *)

let analyze_cohort ~entry_date ~exit_date symbols returns_map =
  let returns = List.filter_map (fun symbol ->
    try Some (List.assoc symbol returns_map)
    with Not_found -> None
  ) symbols in

  if List.length returns = 0 then
    {
      entry_date;
      exit_date;
      symbols;
      avg_return = 0.0;
      median_return = 0.0;
      std_return = 0.0;
      win_rate = 0.0;
      max_drawdown = 0.0;
      sharpe_ratio = 0.0;
      best_performer = None;
      worst_performer = None;
    }
  else
    let winning = List.filter (fun r -> r > 0.0) returns in
    let win_rate = float_of_int (List.length winning) /. float_of_int (List.length returns) in
    let avg = mean returns in
    let med = median returns in
    let std = standard_deviation returns in
    let returns_normalized = List.map (fun r -> r /. 100.0) returns in
    let max_dd = calculate_max_drawdown returns_normalized in

    let best_idx = ref 0 in
    let best_ret = ref Float.neg_infinity in
    let worst_idx = ref 0 in
    let worst_ret = ref Float.infinity in

    List.iteri (fun i ret ->
      if ret > !best_ret then (best_ret := ret; best_idx := i);
      if ret < !worst_ret then (worst_ret := ret; worst_idx := i)
    ) returns;

    let best = if !best_ret = Float.neg_infinity then None else Some (List.nth symbols !best_idx) in
    let worst = if !worst_ret = Float.infinity then None else Some (List.nth symbols !worst_idx) in

    {
      entry_date;
      exit_date;
      symbols;
      avg_return = avg;
      median_return = med;
      std_return = std;
      win_rate;
      max_drawdown;
      sharpe_ratio = if std = 0.0 then 0.0 else avg /. std;
      best_performer = best;
      worst_performer = worst;
    }

(* ─── Reporting ────────────────────────────────────────────────────────── *)

let backtest_to_string bt =
  sprintf "Backtest Results for %s:\n\
           Total Trades: %d\n\
           Winning Trades: %d (%.1f%%)\n\
           Losing Trades: %d\n\
           Avg Win: %.2f%%\n\
           Avg Loss: %.2f%%\n\
           Profit Factor: %.2f\n\
           Total Return: %.2f%%\n\
           Annual Return: %.2f%%\n\
           Max Drawdown: %.2f%%\n\
           Sharpe Ratio: %.2f\n\
           Sortino Ratio: %.2f\n\
           Calmar Ratio: %.2f"
    bt.symbol bt.total_trades bt.winning_trades (bt.win_rate *. 100.0)
    bt.losing_trades bt.avg_win bt.avg_loss bt.profit_factor
    bt.total_return bt.annual_return (bt.max_drawdown *. 100.0)
    bt.sharpe_ratio bt.sortino_ratio bt.calmar_ratio

let cohort_to_string cohort =
  let best_str = match cohort.best_performer with
    | Some s -> s
    | None -> "N/A"
  in
  let worst_str = match cohort.worst_performer with
    | Some s -> s
    | None -> "N/A"
  in
  sprintf "Cohort Analysis (%s → %s):\n\
           Stocks: %d\n\
           Avg Return: %.2f%%\n\
           Median Return: %.2f%%\n\
           Std Dev: %.2f%%\n\
           Win Rate: %.1f%%\n\
           Max Drawdown: %.2f%%\n\
           Sharpe Ratio: %.2f\n\
           Best: %s\n\
           Worst: %s"
    cohort.entry_date cohort.exit_date
    (List.length cohort.symbols)
    cohort.avg_return cohort.median_return cohort.std_return
    (cohort.win_rate *. 100.0) (cohort.max_drawdown *. 100.0)
    cohort.sharpe_ratio best_str worst_str

