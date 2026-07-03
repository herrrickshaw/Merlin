(* Advanced Statistical Analysis Interface *)

type price_series = float list
type returns_series = float list

(* Statistical measures *)
val mean : float list -> float option
val variance : float list -> float option
val stddev : float list -> float option
val skewness : float list -> float option
val kurtosis : float list -> float option
val median : float list -> float option
val quartiles : float list -> (float * float * float) option
val iqr : float list -> float option

(* Return calculations *)
val log_returns : price_series -> returns_series
val simple_returns : price_series -> returns_series

(* Risk metrics *)
val sharpe_ratio : returns_series -> float -> float option
val sortino_ratio : returns_series -> float -> float option
val max_drawdown : price_series -> float option
val calmar_ratio : returns_series -> price_series -> float -> float option

(* Correlation analysis *)
val covariance : float list -> float list -> float option
val correlation : float list -> float list -> float option
val correlation_matrix : float list list -> float option array array

(* Rolling metrics *)
val rolling_mean : float list -> int -> float list
val rolling_std : float list -> int -> float list
val rolling_sharpe : returns_series -> int -> float -> float list

(* Distribution analysis *)
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

val analyze_distribution : float list -> distribution
val distribution_to_string : distribution -> string

(* Portfolio analysis *)
type portfolio = {
  weights: float array;
  returns_series: float list;
  expected_return: float option;
  volatility: float option;
  sharpe: float option;
  sortino: float option;
}

val portfolio_expected_return : float list list -> float array -> float option
val portfolio_variance : float list list -> float array -> float option array array -> float option

(* Anomaly detection *)
val detect_outliers : float list -> float -> float list
val iqr_outliers : float list -> float list

(* Momentum & Trend *)
val rsi : price_series -> int -> float list
val momentum : price_series -> int -> float option
val rate_of_change : price_series -> int -> float list

(* Performance summary *)
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

val calculate_performance : price_series -> returns_series -> performance
val performance_to_string : performance -> string
