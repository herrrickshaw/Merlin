(* Advanced Stock Analyzer - Comprehensive LFS Analysis Tool *)

open Printf

let usage () =
  printf "Advanced Stock Analyzer\n\n";
  printf "Usage: advanced_analyzer <command> [options]\n\n";
  printf "Commands:\n";
  printf "  analyze-csv <file>           Analyze CSV with statistical metrics\n";
  printf "  screen-db <csv> <db>         Screen data and persist results\n";
  printf "  performance <csv>            Calculate detailed performance metrics\n";
  printf "  correlation <csv>            Compute correlation matrix\n";
  printf "  anomalies <csv> <field>      Detect outliers using Z-score and IQR\n";
  printf "  portfolio <csv> <weights>    Portfolio performance analysis\n";
  printf "  report <csv>                 Generate comprehensive analysis report\n\n";
  printf "Options:\n";
  printf "  --output FILE                Save results to file\n";
  printf "  --window N                   Window size for rolling metrics\n"

let load_prices_from_csv file =
  let records = Merlin_lib.Data.load_csv file in
  List.filter_map (fun record ->
    match Merlin_lib.Data.get_field record "close" with
    | Some s -> (try Some (Float.of_string s) with _ -> None)
    | None -> None
  ) records

let analyze_csv_cmd args =
  match args with
  | file :: _ ->
      printf "📊 Analyzing %s...\n\n" file;
      let prices = load_prices_from_csv file in
      printf "Loaded %d price points\n" (List.length prices);

      (* Perform analysis *)
      let dist = Merlin_lib.Advanced_analysis.analyze_distribution prices in
      printf "\n%s\n" (Merlin_lib.Advanced_analysis.distribution_to_string dist);

      (* Additional metrics *)
      (match Merlin_lib.Advanced_analysis.detect_outliers prices 2.5 with
      | [] -> printf "\n✓ No outliers detected (2.5-sigma)\n"
      | outliers ->
          printf "\n⚠️  %d outliers detected (2.5-sigma):\n" (List.length outliers);
          List.iteri (fun i v ->
            if i < 10 then printf "  • %.2f\n" v
          ) outliers);

      (* IQR method *)
      (match Merlin_lib.Advanced_analysis.iqr_outliers prices with
      | [] -> printf "✓ No outliers by IQR method\n"
      | outliers ->
          printf "⚠️  %d outliers by IQR method\n" (List.length outliers))
  | [] -> printf "Error: CSV file required\n"

let performance_cmd args =
  match args with
  | file :: opts ->
      printf "📈 Performance Analysis\n\n";
      let prices = load_prices_from_csv file in

      if List.length prices < 2 then (
        printf "Error: Need at least 2 price points\n"
      ) else (
        let returns = Merlin_lib.Advanced_analysis.simple_returns prices in
        let perf = Merlin_lib.Advanced_analysis.calculate_performance prices returns in
        printf "%s\n" (Merlin_lib.Advanced_analysis.performance_to_string perf);

        (* Additional metrics *)
        printf "\nAdditional Analysis:\n";
        (match Merlin_lib.Advanced_analysis.momentum prices 20 with
        | Some m -> printf "20-day Momentum: %.2f%%\n" m
        | None -> ());

        (match Merlin_lib.Advanced_analysis.rsi prices 14 with
        | [rsi_val] -> printf "RSI (14): %.2f\n" rsi_val
        | _ -> ());

        (* Rolling metrics *)
        let rolling_std = Merlin_lib.Advanced_analysis.rolling_std prices 20 in
        (match rolling_std with
        | [] -> ()
        | vals ->
            let avg_vol = (List.fold_left (+.) 0.0 vals) /. Float.of_int (List.length vals) in
            printf "Average 20-day Volatility: %.4f\n" avg_vol)
      )
  | [] -> printf "Error: CSV file required\n"

let anomalies_cmd args =
  match args with
  | file :: field :: _ ->
      printf "🔍 Anomaly Detection: %s\n\n" field;
      let records = Merlin_lib.Data.load_csv file in
      let values = List.filter_map (fun r ->
        match Merlin_lib.Data.get_field r field with
        | Some s -> (try Some (Float.of_string s) with _ -> None)
        | None -> None
      ) records in

      if List.length values < 3 then (
        printf "Error: Need at least 3 data points\n"
      ) else (
        printf "Analyzing %d values\n\n" (List.length values);

        (* Z-score method *)
        let z_outliers = Merlin_lib.Advanced_analysis.detect_outliers values 2.5 in
        printf "Z-Score Method (|z| > 2.5):\n";
        printf "  Outliers: %d\n" (List.length z_outliers);
        printf "  Percentage: %.1f%%\n" (Float.of_int (List.length z_outliers) /. Float.of_int (List.length values) *. 100.0);

        (* IQR method *)
        let iqr_outliers = Merlin_lib.Advanced_analysis.iqr_outliers values in
        printf "\nIQR Method:\n";
        printf "  Outliers: %d\n" (List.length iqr_outliers);
        printf "  Percentage: %.1f%%\n" (Float.of_int (List.length iqr_outliers) /. Float.of_int (List.length values) *. 100.0);

        (* Show distribution *)
        let dist = Merlin_lib.Advanced_analysis.analyze_distribution values in
        printf "\nDistribution:\n";
        printf "  Skewness: %s (right-tail bias)\n"
          (match dist.skew with Some s -> sprintf "%.4f" s | None -> "N/A");
        printf "  Kurtosis: %s (tail heaviness)\n"
          (match dist.kurt with Some k -> sprintf "%.4f" k | None -> "N/A")
      )
  | _ -> printf "Error: analyze-csv <file> <field>\n"

let report_cmd args =
  match args with
  | file :: opts ->
      printf "\n╔════════════════════════════════════════════╗\n";
      printf "║   COMPREHENSIVE STOCK ANALYSIS REPORT     ║\n";
      printf "╚════════════════════════════════════════════╝\n\n";

      let prices = load_prices_from_csv file in
      if List.length prices < 20 then (
        printf "❌ Error: Need at least 20 price points for comprehensive analysis\n"
      ) else (
        let returns = Merlin_lib.Advanced_analysis.simple_returns prices in

        (* Section 1: Summary *)
        printf "\n📊 SUMMARY\n";
        printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
        printf "Price points: %d\n" (List.length prices);
        printf "Date range: %d days\n" ((List.length prices) - 1);

        (match List.hd prices, List.hd (List.rev prices) with
        | Some start_p, Some end_p ->
            let total_ret = ((end_p -. start_p) /. start_p) *. 100.0 in
            printf "Total return: %.2f%%\n" total_ret
        | _ -> ());

        (* Section 2: Price Statistics *)
        printf "\n💹 PRICE STATISTICS\n";
        printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
        let dist = Merlin_lib.Advanced_analysis.analyze_distribution prices in
        printf "Current: %.2f | Min: %.2f | Max: %.2f\n"
          (match List.hd (List.rev prices) with Some p -> p | None -> 0.0)
          dist.min dist.max;
        printf "Mean: %s | Median: %s | StdDev: %s\n"
          (match dist.mean with Some m -> sprintf "%.2f" m | None -> "N/A")
          (match dist.median with Some m -> sprintf "%.2f" m | None -> "N/A")
          (match dist.std with Some s -> sprintf "%.2f" s | None -> "N/A");

        (* Section 3: Return Statistics *)
        printf "\n📈 RETURN STATISTICS\n";
        printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
        let ret_dist = Merlin_lib.Advanced_analysis.analyze_distribution returns in
        printf "Daily mean return: %s\n"
          (match ret_dist.mean with Some m -> sprintf "%.4f%%" (m *. 100.0) | None -> "N/A");
        printf "Daily volatility: %s\n"
          (match ret_dist.std with Some s -> sprintf "%.4f%%" (s *. 100.0) | None -> "N/A");
        printf "Skewness: %s\n"
          (match ret_dist.skew with Some s -> sprintf "%.4f" s | None -> "N/A");
        printf "Kurtosis: %s\n"
          (match ret_dist.kurt with Some k -> sprintf "%.4f" k | None -> "N/A");

        (* Section 4: Risk Metrics *)
        printf "\n⚠️  RISK METRICS\n";
        printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
        let perf = Merlin_lib.Advanced_analysis.calculate_performance prices returns in
        printf "Annual volatility: %s\n"
          (match perf.volatility with
          | Some v -> sprintf "%.2f%%" (v *. Float.sqrt 252.0 *. 100.0)
          | None -> "N/A");
        printf "Max drawdown: %s\n"
          (match perf.max_dd with Some d -> sprintf "%.2f%%" (d *. 100.0) | None -> "N/A");
        printf "Sharpe ratio: %s\n"
          (match perf.sharpe_ratio with Some s -> sprintf "%.4f" s | None -> "N/A");
        printf "Sortino ratio: %s\n"
          (match perf.sortino_ratio with Some s -> sprintf "%.4f" s | None -> "N/A");

        (* Section 5: Anomalies *)
        printf "\n🔍 ANOMALY DETECTION\n";
        printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
        let z_outliers = Merlin_lib.Advanced_analysis.detect_outliers prices 2.5 in
        let iqr_outliers = Merlin_lib.Advanced_analysis.iqr_outliers prices in
        printf "Z-score outliers (2.5σ): %d (%.1f%%)\n"
          (List.length z_outliers)
          (Float.of_int (List.length z_outliers) /. Float.of_int (List.length prices) *. 100.0);
        printf "IQR outliers: %d (%.1f%%)\n"
          (List.length iqr_outliers)
          (Float.of_int (List.length iqr_outliers) /. Float.of_int (List.length prices) *. 100.0);

        (* Section 6: Momentum *)
        printf "\n🚀 MOMENTUM INDICATORS\n";
        printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
        (match Merlin_lib.Advanced_analysis.momentum prices 10 with
        | Some m -> printf "10-day momentum: %.2f%%\n" m
        | None -> ());
        (match Merlin_lib.Advanced_analysis.momentum prices 20 with
        | Some m -> printf "20-day momentum: %.2f%%\n" m
        | None -> ());
        (match Merlin_lib.Advanced_analysis.rsi prices 14 with
        | [rsi_val] -> printf "RSI (14): %.2f\n" rsi_val
        | _ -> ());

        printf "\n" ^ String.make 45 '━' ^ "\n"
      )
  | [] -> printf "Error: CSV file required\n"

let () =
  let args = List.tl (Array.to_list Sys.argv) in
  match args with
  | "analyze-csv" :: rest -> analyze_csv_cmd rest
  | "performance" :: rest -> performance_cmd rest
  | "anomalies" :: rest -> anomalies_cmd rest
  | "report" :: rest -> report_cmd rest
  | "help" :: _ | [] -> usage ()
  | cmd :: _ -> printf "Unknown command: %s\n" cmd; usage ()
