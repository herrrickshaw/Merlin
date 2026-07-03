(* Stock Screener CLI *)

open Printf
open Merlin_lib.Screener

let load_csv_to_stock_data file =
  let records = Merlin_lib.Data.load_csv file in
  let stocks = Hashtbl.create 100 in

  List.iter (fun record ->
    let symbol = Merlin_lib.Data.get_field record "symbol" in
    let date = Merlin_lib.Data.get_field record "date" in
    let open_ = Merlin_lib.Data.get_field record "open" in
    let high = Merlin_lib.Data.get_field record "high" in
    let low = Merlin_lib.Data.get_field record "low" in
    let close = Merlin_lib.Data.get_field record "close" in
    let volume = Merlin_lib.Data.get_field record "volume" in

    match symbol, date, close with
    | Some sym, Some d, Some c ->
        let bar = {
          date = d;
          open_ = (match open_ with Some s -> (try Float.of_string s with _ -> 0.0) | None -> 0.0);
          high = (match high with Some s -> (try Float.of_string s with _ -> 0.0) | None -> 0.0);
          low = (match low with Some s -> (try Float.of_string s with _ -> 0.0) | None -> 0.0);
          close = (try Float.of_string c with _ -> 0.0);
          volume = (match volume with Some s -> (try Float.of_string s with _ -> 0.0) | None -> 0.0);
        } in

        let stock = try Hashtbl.find stocks sym with Not_found ->
          { symbol = sym; market = ""; ohlcv = []; fundamentals = [] }
        in

        let updated_stock = { stock with ohlcv = stock.ohlcv @ [bar] } in
        Hashtbl.replace stocks sym updated_stock
    | _ -> ()
  ) records;

  Hashtbl.fold (fun _ stock acc -> stock :: acc) stocks []

let load_fundamentals_csv file stocks =
  let records = Merlin_lib.Data.load_csv file in

  List.iter (fun record ->
    let symbol = Merlin_lib.Data.get_field record "symbol" in
    match symbol with
    | Some sym ->
        let stock = List.find_opt (fun s -> s.symbol = sym) stocks in
        (match stock with
        | Some s ->
            let fundamentals = Hashtbl.create 50 in
            List.iter (fun (key, value) ->
              if key <> "symbol" then
                try
                  Hashtbl.add fundamentals key (Some (Float.of_string value))
                with _ -> ()
            ) record;
            Hashtbl.fold (fun k v acc -> (k, v) :: acc) fundamentals s.fundamentals |> ignore
        | None -> ())
    | None -> ()
  ) records;
  stocks

let screen_cmd args =
  match args with
  | csv_file :: opts ->
      printf "Loading stock data from %s\n" csv_file;
      let stocks = load_csv_to_stock_data csv_file in
      printf "Loaded %d stocks\n" (List.length stocks);

      let strategy = ref "" in
      let top = ref 10 in
      let output = ref None in

      let rec parse_opts = function
        | [] -> ()
        | "--strategy" :: s :: rest -> strategy := s; parse_opts rest
        | "--top" :: t :: rest -> top := (try int_of_string t with _ -> 10); parse_opts rest
        | "--output" :: o :: rest -> output := Some o; parse_opts rest
        | _ :: rest -> parse_opts rest
      in
      parse_opts opts;

      printf "Running screening...\n";
      let results = screen_market stocks in
      printf "Found %d total results\n" (List.length results);

      if !strategy <> "" then (
        let ranked = rank_results results !strategy in

        printf "\n=== Top %d %s Results ===\n" !top !strategy;
        List.iteri (fun i r ->
          if i < !top then (
            printf "%d. %s (score: %s) - %s\n"
              (i + 1) r.symbol
              (match r.score with Some s -> sprintf "%.2f" s | None -> "N/A")
              r.note;
            List.iter (fun (k, v) ->
              printf "   %s: %s\n" k v
            ) r.metrics
          )
        ) ranked
      ) else (
        printf "\n=== All Screening Results ===\n";
        let csv_output = results_to_csv results in
        printf "%s\n" csv_output;

        match !output with
        | Some file ->
            let oc = open_out file in
            output_string oc csv_output;
            close_out oc;
            printf "Results saved to %s\n" file
        | None -> ()
      )
  | [] -> printf "Error: CSV file required\n"

let usage () =
  printf "Stock Screener\n\n";
  printf "Usage: screener <csv_file> [OPTIONS]\n\n";
  printf "Options:\n";
  printf "  --strategy NAME    Filter by strategy (darvas, piotroski, coffee_can, etc.)\n";
  printf "  --top N            Show top N results (default: 10)\n";
  printf "  --output FILE      Save results to CSV file\n"

let () =
  let args = List.tl (Array.to_list Sys.argv) in
  match args with
  | file :: rest -> screen_cmd (file :: rest)
  | [] -> usage ()
