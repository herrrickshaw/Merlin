(* Portfolio Optimization Module - Modern Portfolio Theory
   Optimizes allocation of triple hits for maximum risk-adjusted returns *)

open Printf

(* ─── Types ────────────────────────────────────────────────────────────── *)

type asset = {
  symbol: string;
  expected_return: float;      (* Annual return in decimal: 0.15 = 15% *)
  volatility: float;           (* Annual volatility in decimal *)
  dividend_yield: float;       (* Annual dividend in decimal *)
  market_cap: float;           (* Market cap in millions *)
  piotroski_score: int;        (* 0-9 *)
  cmf_value: float;            (* CMF score *)
}

type portfolio = {
  assets: asset list;
  weights: float array;        (* Allocation weights, sum = 1.0 *)
  expected_return: float;      (* Portfolio expected return *)
  volatility: float;           (* Portfolio standard deviation *)
  sharpe_ratio: float;         (* Return per unit of risk *)
  sortino_ratio: float;        (* Return per unit of downside risk *)
  dividend_yield: float;       (* Blended dividend *)
}

type efficient_frontier = {
  min_var_portfolio: portfolio;
  max_sharpe_portfolio: portfolio;
  portfolios: portfolio list;
}

(* ─── Covariance Matrix Estimation ────────────────────────────────────── *)

(* Simple correlation estimation based on market characteristics *)
let estimate_correlation asset1 asset2 =
  (* Stocks with similar Piotroski scores tend to be correlated *)
  let score_diff = Float.abs (float_of_int (asset1.piotroski_score - asset2.piotroski_score)) in
  let score_corr = Float.exp (-. score_diff /. 3.0) in

  (* Stocks with similar CMF tend to move together *)
  let cmf_diff = Float.abs (asset1.cmf_value -. asset2.cmf_value) in
  let cmf_corr = Float.exp (-. cmf_diff /. 0.3) in

  (* Average correlation, cap at 0.95 *)
  let corr = (score_corr +. cmf_corr) /. 2.0 in
  Float.min corr 0.95

(* Build covariance matrix *)
let build_covariance_matrix assets =
  let n = List.length assets in
  let cov = Array.make_matrix n n 0.0 in

  List.iteri (fun i asset_i ->
    List.iteri (fun j asset_j ->
      if i = j then
        cov.(i).(j) <- asset_i.volatility *. asset_i.volatility
      else if i < j then
        let corr = estimate_correlation asset_i asset_j in
        let cov_val = corr *. asset_i.volatility *. asset_j.volatility in
        cov.(i).(j) <- cov_val;
        cov.(j).(i) <- cov_val
    ) assets
  ) assets;

  cov

(* ─── Portfolio Return and Risk Calculation ────────────────────────────── *)

let portfolio_return assets weights =
  Array.fold_left2 (fun acc asset w ->
    acc +. (asset.expected_return *. w)
  ) 0.0 (Array.of_list assets) weights

let portfolio_volatility assets weights =
  let n = Array.length weights in
  let cov = build_covariance_matrix assets in
  let variance = ref 0.0 in

  for i = 0 to n - 1 do
    for j = 0 to n - 1 do
      variance := !variance +. weights.(i) *. weights.(j) *. cov.(i).(j)
    done
  done;

  Float.sqrt !variance

let portfolio_dividend assets weights =
  Array.fold_left2 (fun acc asset w ->
    acc +. (asset.dividend_yield *. w)
  ) 0.0 (Array.of_list assets) weights

(* ─── Portfolio Quality Metrics ────────────────────────────────────────── *)

let sharpe_ratio ~ret ~vol ~risk_free_rate =
  if vol = 0.0 then 0.0
  else (ret -. risk_free_rate) /. vol

let sortino_ratio ~ret ~vol ~target_return =
  (* Downside deviation: only negative returns *)
  if vol = 0.0 then 0.0
  else
    let downside_dev = vol *. 0.6 in  (* Approximate: usually 60% of total vol *)
    (ret -. target_return) /. downside_dev

let calmar_ratio ~ret ~max_drawdown =
  if max_drawdown >= 0.0 || Float.is_nan max_drawdown then 0.0
  else ret /. (-.max_drawdown)

let create_portfolio assets weights =
  let assets_arr = Array.of_list assets in
  let ret = portfolio_return assets weights in
  let vol = portfolio_volatility assets weights in
  let div = portfolio_dividend assets weights in
  let sr = sharpe_ratio ~ret ~vol ~risk_free_rate:0.04 in
  let so = sortino_ratio ~ret ~vol ~target_return:0.0 in

  {
    assets;
    weights;
    expected_return = ret;
    volatility = vol;
    sharpe_ratio = sr;
    sortino_ratio = so;
    dividend_yield = div;
  }

(* ─── Minimum Variance Portfolio ──────────────────────────────────────── *)

let minimum_variance_portfolio assets =
  let n = List.length assets in
  if n = 0 then failwith "No assets provided"
  else if n = 1 then
    create_portfolio assets [| 1.0 |]
  else
    (* Equal weight as simple approximation *)
    (* In production, use quadratic optimization (e.g., cvx via OCaml bindings) *)
    let weight = 1.0 /. float_of_int n in
    let weights = Array.make n weight in
    create_portfolio assets weights

(* ─── Maximum Sharpe Ratio Portfolio ───────────────────────────────────── *)

let maximum_sharpe_portfolio assets =
  let n = List.length assets in
  if n = 0 then failwith "No assets provided"
  else if n = 1 then
    create_portfolio assets [| 1.0 |]
  else
    (* Weight by risk-adjusted return (Piotroski score) *)
    let assets_arr = Array.of_list assets in
    let total_score = ref 0.0 in

    Array.iter (fun asset ->
      total_score := !total_score +. float_of_int asset.piotroski_score
    ) assets_arr;

    if !total_score = 0.0 then
      let weight = 1.0 /. float_of_int n in
      let weights = Array.make n weight in
      create_portfolio assets weights
    else
      let weights = Array.map (fun asset ->
        float_of_int asset.piotroski_score /. !total_score
      ) assets_arr in
      create_portfolio assets weights

(* ─── Risk Parity Portfolio ────────────────────────────────────────────── *)

let risk_parity_portfolio assets =
  let n = List.length assets in
  if n = 0 then failwith "No assets provided"
  else
    let assets_arr = Array.of_list assets in
    let inv_vols = Array.map (fun asset ->
      if asset.volatility > 0.0 then 1.0 /. asset.volatility else 0.0
    ) assets_arr in

    let total_inv_vol = ref 0.0 in
    Array.iter (fun inv_vol -> total_inv_vol := !total_inv_vol +. inv_vol) inv_vols;

    if !total_inv_vol = 0.0 then
      let weight = 1.0 /. float_of_int n in
      let weights = Array.make n weight in
      create_portfolio assets weights
    else
      let weights = Array.map (fun inv_vol ->
        inv_vol /. !total_inv_vol
      ) inv_vols in
      create_portfolio assets weights

(* ─── Efficient Frontier Generation ────────────────────────────────────── *)

let generate_efficient_frontier assets ~num_portfolios =
  let min_var = minimum_variance_portfolio assets in
  let max_sharpe = maximum_sharpe_portfolio assets in

  (* Generate range of portfolios *)
  let portfolios = ref [min_var; max_sharpe] in

  for i = 0 to num_portfolios - 1 do
    let alpha = float_of_int i /. float_of_int num_portfolios in
    let n = List.length assets in
    let weight = 1.0 /. float_of_int n in

    (* Random-ish allocation based on alpha *)
    let weights = Array.init n (fun j ->
      if j mod 2 = 0 then weight *. (1.0 +. alpha)
      else weight *. (1.0 -. alpha)
    ) in

    (* Normalize *)
    let total = Array.fold_left (+.) 0.0 weights in
    Array.iteri (fun j _ -> weights.(j) <- weights.(j) /. total) weights;

    let portfolio = create_portfolio assets weights in
    portfolios := portfolio :: !portfolios
  done;

  (* Sort by Sharpe ratio *)
  let sorted = List.sort (fun p1 p2 ->
    Float.compare p2.sharpe_ratio p1.sharpe_ratio
  ) !portfolios in

  {
    min_var_portfolio = min_var;
    max_sharpe_portfolio = max_sharpe;
    portfolios = sorted;
  }

(* ─── Portfolio Analysis ────────────────────────────────────────────────── *)

let portfolio_to_string portfolio =
  sprintf "Portfolio:\n\
           Expected Return: %.2f%%\n\
           Volatility (Risk): %.2f%%\n\
           Dividend Yield: %.2f%%\n\
           Sharpe Ratio: %.2f\n\
           Sortino Ratio: %.2f\n\
           Allocation:\n%s"
    (portfolio.expected_return *. 100.0)
    (portfolio.volatility *. 100.0)
    (portfolio.dividend_yield *. 100.0)
    portfolio.sharpe_ratio
    portfolio.sortino_ratio
    (String.concat "\n" (List.mapi (fun i asset ->
      if portfolio.weights.(i) > 0.01 then
        sprintf "  %s: %.1f%%" asset.symbol (portfolio.weights.(i) *. 100.0)
      else ""
    ) portfolio.assets))

let frontier_to_string frontier =
  sprintf "Efficient Frontier:\n\
           Min Variance Portfolio:\n%s\n\n\
           Max Sharpe Ratio Portfolio:\n%s\n\n\
           Total Portfolios: %d"
    (portfolio_to_string frontier.min_var_portfolio)
    (portfolio_to_string frontier.max_sharpe_portfolio)
    (List.length frontier.portfolios)

(* ─── Sector and Quality-Based Weighting ────────────────────────────────── *)

let quality_weighted_portfolio assets =
  let n = List.length assets in
  if n = 0 then failwith "No assets provided"
  else
    let assets_arr = Array.of_list assets in
    let total_quality = ref 0.0 in

    (* Quality score: Piotroski + CMF boost *)
    Array.iter (fun asset ->
      let quality = float_of_int asset.piotroski_score +. (asset.cmf_value *. 3.0) in
      total_quality := !total_quality +. Float.max 0.0 quality
    ) assets_arr;

    if !total_quality = 0.0 then
      let weight = 1.0 /. float_of_int n in
      let weights = Array.make n weight in
      create_portfolio assets weights
    else
      let weights = Array.map (fun asset ->
        let quality = float_of_int asset.piotroski_score +. (asset.cmf_value *. 3.0) in
        Float.max 0.0 quality /. !total_quality
      ) assets_arr in
      create_portfolio assets weights

(* ─── Rebalancing Analysis ────────────────────────────────────────────── *)

type rebalancing_signal = {
  symbol: string;
  current_weight: float;
  target_weight: float;
  drift: float;
  action: string;  (* "BUY", "SELL", "HOLD" *)
}

let calculate_rebalancing_signals portfolio target_weights =
  List.mapi (fun i asset ->
    let current = portfolio.weights.(i) in
    let target = target_weights.(i) in
    let drift = current -. target in
    let action = if drift > 0.05 then "SELL"
                 else if drift < -0.05 then "BUY"
                 else "HOLD" in
    {
      symbol = asset.symbol;
      current_weight = current;
      target_weight = target;
      drift;
      action;
    }
  ) portfolio.assets

