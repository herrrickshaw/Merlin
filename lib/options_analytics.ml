(* Options Analytics Module - Black-Scholes, Greeks, and Implied Volatility
   Provides insights into expected stock price movements and volatility *)

open Printf

(* ─── Constants ─────────────────────────────────────────────────────────── *)

let pi = 3.14159265358979323846
let sqrt_2pi = 2.50662827463100050241

(* ─── Normal Distribution Functions ──────────────────────────────────────── *)

(* Cumulative standard normal distribution *)
let rec norm_cdf x =
  if x < -6.0 then 0.0
  else if x > 6.0 then 1.0
  else
    let a = 0.2316419 in
    let b1 = 0.319381530 in
    let b2 = -0.356563782 in
    let b3 = 1.781477937 in
    let b4 = -1.821255978 in
    let b5 = 1.330274429 in
    let t = 1.0 /. (1.0 +. a *. Float.abs x) in
    let t2 = t *. t in
    let t3 = t2 *. t in
    let t4 = t3 *. t in
    let t5 = t4 *. t in
    let n = 1.0 /. sqrt_2pi *. Float.exp (-. x *. x /. 2.0) in
    let result = 1.0 -. n *. (b1 *. t +. b2 *. t2 +. b3 *. t3 +. b4 *. t4 +. b5 *. t5) in
    if x < 0.0 then 1.0 -. result else result

(* Probability density function *)
let norm_pdf x =
  (1.0 /. sqrt_2pi) *. Float.exp (-. x *. x /. 2.0)

(* ─── Black-Scholes Option Pricing ──────────────────────────────────────── *)

type option_type = Call | Put

type option_params = {
  spot: float;          (* Current stock price *)
  strike: float;        (* Strike price *)
  time: float;          (* Time to expiry in years *)
  rate: float;          (* Risk-free rate *)
  dividend: float;      (* Dividend yield *)
  volatility: float;    (* Implied volatility *)
}

type option_price = {
  option_type: option_type;
  price: float;
  delta: float;
  gamma: float;
  vega: float;
  theta: float;
  rho: float;
}

(* Calculate d1 and d2 for Black-Scholes *)
let calculate_d1_d2 params =
  let numerator = Float.log (params.spot /. params.strike) +.
                  (params.rate -. params.dividend +. params.volatility ** 2.0 /. 2.0) *. params.time in
  let denominator = params.volatility *. Float.sqrt params.time in
  let d1 = numerator /. denominator in
  let d2 = d1 -. params.volatility *. Float.sqrt params.time in
  (d1, d2)

(* Black-Scholes call price *)
let bs_call_price params =
  let d1, d2 = calculate_d1_d2 params in
  let discount = Float.exp (-. params.rate *. params.time) in
  let spot_adjusted = params.spot *. Float.exp (-. params.dividend *. params.time) in
  let call = (spot_adjusted *. norm_cdf d1) -. (params.strike *. discount *. norm_cdf d2) in
  call

(* Black-Scholes put price *)
let bs_put_price params =
  let d1, d2 = calculate_d1_d2 params in
  let discount = Float.exp (-. params.rate *. params.time) in
  let spot_adjusted = params.spot *. Float.exp (-. params.dividend *. params.time) in
  let put = (params.strike *. discount *. norm_cdf (-. d2)) -. (spot_adjusted *. norm_cdf (-. d1)) in
  put

(* ─── Greeks Calculation ────────────────────────────────────────────────── *)

(* Delta: rate of change of option price with respect to spot price *)
let calculate_delta params opt_type =
  let d1, _ = calculate_d1_d2 params in
  let spot_adjusted = Float.exp (-. params.dividend *. params.time) in
  match opt_type with
  | Call -> spot_adjusted *. norm_cdf d1
  | Put -> spot_adjusted *. (norm_cdf d1 -. 1.0)

(* Gamma: second derivative of option price with respect to spot *)
let calculate_gamma params =
  let d1, _ = calculate_d1_d2 params in
  let numerator = norm_pdf d1 *. Float.exp (-. params.dividend *. params.time) in
  let denominator = params.spot *. params.volatility *. Float.sqrt params.time in
  numerator /. denominator

(* Vega: sensitivity to volatility changes (per 1% change) *)
let calculate_vega params =
  let d1, _ = calculate_d1_d2 params in
  let spot_adjusted = params.spot *. Float.exp (-. params.dividend *. params.time) in
  (spot_adjusted *. norm_pdf d1 *. Float.sqrt params.time) /. 100.0

(* Theta: time decay (per day) *)
let calculate_theta params opt_type =
  let d1, d2 = calculate_d1_d2 params in
  let discount = Float.exp (-. params.rate *. params.time) in
  let spot_adjusted = params.spot *. Float.exp (-. params.dividend *. params.time) in
  let term1 = (-. spot_adjusted *. norm_pdf d1 *. params.volatility *. Float.exp (-. params.dividend *. params.time)) /. (2.0 *. Float.sqrt params.time) in

  match opt_type with
  | Call ->
      let term2 = params.rate *. params.strike *. discount *. norm_cdf d2 in
      let term3 = params.dividend *. spot_adjusted *. norm_cdf d1 in
      (term1 +. term2 -. term3) /. 365.0
  | Put ->
      let term2 = params.rate *. params.strike *. discount *. norm_cdf (-. d2) in
      let term3 = params.dividend *. spot_adjusted *. norm_cdf (-. d1) in
      (term1 -. term2 +. term3) /. 365.0

(* Rho: sensitivity to interest rate changes (per 1% change) *)
let calculate_rho params opt_type =
  let _, d2 = calculate_d1_d2 params in
  let discount = Float.exp (-. params.rate *. params.time) in
  match opt_type with
  | Call -> params.strike *. params.time *. discount *. norm_cdf d2 /. 100.0
  | Put -> (-. params.strike *. params.time *. discount *. norm_cdf (-. d2)) /. 100.0

(* Price option and calculate all Greeks *)
let price_option params opt_type =
  let price = match opt_type with
    | Call -> bs_call_price params
    | Put -> bs_put_price params
  in
  {
    option_type = opt_type;
    price;
    delta = calculate_delta params opt_type;
    gamma = calculate_gamma params;
    vega = calculate_vega params;
    theta = calculate_theta params opt_type;
    rho = calculate_rho params opt_type;
  }

(* ─── Implied Volatility (Newton-Raphson method) ──────────────────────── *)

let implied_volatility market_price params opt_type ~max_iterations:max_iter =
  let rec newton_raphson vol iteration =
    if iteration >= max_iter then Some vol
    else
      let current_params = { params with volatility = vol } in
      let current_price = match opt_type with
        | Call -> bs_call_price current_params
        | Put -> bs_put_price current_params
      in
      let price_diff = current_price -. market_price in

      if Float.abs price_diff < 0.01 then Some vol  (* Converged *)
      else
        let vega = calculate_vega current_params in
        if Float.abs vega < 1e-10 then None  (* Vega too small *)
        else
          let new_vol = vol -. (price_diff /. vega) in
          if new_vol < 0.01 then newton_raphson 0.01 (iteration + 1)
          else if new_vol > 3.0 then newton_raphson 3.0 (iteration + 1)
          else newton_raphson new_vol (iteration + 1)
  in
  newton_raphson 0.20 0  (* Start with 20% volatility guess *)

(* ─── Forward Price Estimation ──────────────────────────────────────────── *)

(* Expected stock price at expiry based on options *)
type price_forecast = {
  spot_price: float;
  forward_price: float;
  expected_return: float;
  annual_volatility: float;
  confidence_interval_68: (float * float);  (* 1 sigma *)
  confidence_interval_95: (float * float);  (* 2 sigma *)
}

let forecast_price params ~forecast_days =
  let forecast_years = float_of_int forecast_days /. 365.0 in
  let forward = params.spot *. Float.exp (params.rate *. forecast_years) in
  let expected_move = forward *. params.volatility *. Float.sqrt forecast_years in

  {
    spot_price = params.spot;
    forward_price = forward;
    expected_return = ((forward -. params.spot) /. params.spot) *. 100.0;
    annual_volatility = params.volatility *. 100.0;
    confidence_interval_68 = (forward -. expected_move, forward +. expected_move);
    confidence_interval_95 = (forward -. 2.0 *. expected_move, forward +. 2.0 *. expected_move);
  }

(* ─── Options Summary Report ────────────────────────────────────────────── *)

let option_to_string opt =
  let opt_type_str = match opt.option_type with Call -> "CALL" | Put -> "PUT" in
  sprintf "%s\n\
           Price: %.4f\n\
           Delta: %.4f\n\
           Gamma: %.6f\n\
           Vega:  %.4f\n\
           Theta: %.4f (per day)\n\
           Rho:   %.4f"
    opt_type_str opt.price opt.delta opt.gamma opt.vega opt.theta opt.rho

let forecast_to_string forecast =
  let ci68_low, ci68_high = forecast.confidence_interval_68 in
  let ci95_low, ci95_high = forecast.confidence_interval_95 in
  sprintf "Price Forecast:\n\
           Current:   %.2f\n\
           Forward:   %.2f\n\
           Exp Return: %.2f%%\n\
           Volatility: %.2f%%\n\
           68%% CI:   [%.2f, %.2f]\n\
           95%% CI:   [%.2f, %.2f]"
    forecast.spot_price forecast.forward_price forecast.expected_return
    forecast.annual_volatility ci68_low ci68_high ci95_low ci95_high

(* ─── Volatility Smile Analysis ────────────────────────────────────────── *)

type volatility_term = {
  maturity_days: int;
  atm_volatility: float;
  volatility_skew: float;  (* Difference between OTM put vol and ATM vol *)
}

let analyze_volatility_curve ~spot ~rate ~dividend volatilities =
  let term_struct = List.mapi (fun i (days, vol) ->
    let params = {
      spot;
      strike = spot;
      time = float_of_int days /. 365.0;
      rate;
      dividend;
      volatility = vol;
    } in
    {
      maturity_days = days;
      atm_volatility = vol;
      volatility_skew = vol *. 0.05;  (* Approximate skew *)
    }
  ) volatilities in
  term_struct

