(* Merlin: LFS Data Analyzer & Uploader *)

let usage () =
  Printf.printf "Merlin - LFS Data Analyzer & Uploader\n";
  Printf.printf "Usage: merlin [COMMAND] [OPTIONS]\n\n";
  Printf.printf "Commands:\n";
  Printf.printf "  analyze-csv <file> [--key FIELD] [--agg SUM|MEAN|COUNT] [--output FILE]\n";
  Printf.printf "  analyze-json <file> [--field FIELD] [--output FILE]\n";
  Printf.printf "  upload <repo> <source> <dest> [--message MSG] [--push]\n";
  Printf.printf "  stats <file> <field> [--output FILE]\n";
  Printf.printf "  filter <file> <field> <op> <value> [--output FILE]\n";
  Printf.printf "  merge <file1> <file2> [--output FILE]\n";
  Printf.printf "  info <file>\n";
  Printf.printf "  help\n"

let analyze_csv_cmd args =
  match args with
  | file :: opts ->
      let records = Merlin_lib.Data.load_csv file in
      Printf.printf "Loaded %d records from %s\n" (List.length records) file;

      let key_field = ref "id" in
      let agg_type = ref "sum" in
      let agg_field = ref "" in
      let output = ref None in

      let rec parse_opts = function
        | [] -> ()
        | "--key" :: k :: rest -> key_field := k; parse_opts rest
        | "--agg" :: a :: rest -> agg_type := a; parse_opts rest
        | "--field" :: f :: rest -> agg_field := f; parse_opts rest
        | "--output" :: o :: rest -> output := Some o; parse_opts rest
        | _ :: rest -> parse_opts rest
      in
      parse_opts opts;

      if !agg_field <> "" then (
        let agg_fn = match !agg_type with
          | "sum" -> Merlin_lib.Analyze.sum
          | "mean" -> Merlin_lib.Analyze.mean
          | "count" -> fun vs -> Some (float_of_int (Merlin_lib.Analyze.count vs))
          | _ -> Merlin_lib.Analyze.sum
        in

        let results = Merlin_lib.Data.aggregate records !key_field !agg_field agg_fn in
        let json_results = `List (List.map (fun (k, v) ->
          `Assoc [("key", `String k); ("value", match v with Some f -> `Float f | None -> `Null)]
        ) results) in

        (match !output with
        | Some f ->
            Merlin_lib.Data.save_json f [json_results];
            Printf.printf "Results saved to %s\n" f
        | None ->
            Printf.printf "%s\n" (Yojson.Basic.pretty_to_string json_results))
      )
  | [] -> Printf.printf "Error: CSV file required\n"

let analyze_json_cmd args =
  match args with
  | file :: opts ->
      let json_list = Merlin_lib.Data.load_json file in
      Printf.printf "Loaded JSON data from %s\n" file;
      Printf.printf "Records: %d\n" (List.length json_list)
  | [] -> Printf.printf "Error: JSON file required\n"

let upload_cmd args =
  match args with
  | repo :: src :: dest :: opts ->
      let message = ref "Update data" in
      let do_push = ref false in

      let rec parse_opts = function
        | [] -> ()
        | "--message" :: m :: rest -> message := m; parse_opts rest
        | "--push" :: rest -> do_push := true; parse_opts rest
        | _ :: rest -> parse_opts rest
      in
      parse_opts opts;

      if Sys.file_exists src then (
        let _ = Merlin_lib.Uploader.upload_file repo src dest in
        let status = Merlin_lib.Uploader.status repo in
        Printf.printf "Status:\n%s\n" status;

        if !do_push then (
          let _ = Merlin_lib.Uploader.commit_and_push repo "main" !message in
          Printf.printf "Pushed to origin/main\n"
        )
      ) else
        Printf.printf "Error: Source file %s not found\n" src
  | _ -> Printf.printf "Error: upload <repo> <source> <dest> [--message MSG] [--push]\n"

let stats_cmd args =
  match args with
  | file :: field :: opts ->
      let records = Merlin_lib.Data.load_csv file in
      let values = List.filter_map (fun r ->
        match Merlin_lib.Data.get_field r field with
        | Some v -> Some v
        | None -> None
      ) records in

      let mean = Merlin_lib.Analyze.mean values in
      let median = Merlin_lib.Analyze.median values in
      let min = Merlin_lib.Analyze.min values in
      let max = Merlin_lib.Analyze.max values in
      let stddev = Merlin_lib.Analyze.stddev values in

      Printf.printf "Statistics for field '%s':\n" field;
      Printf.printf "  Count: %d\n" (Merlin_lib.Analyze.count values);
      (match mean with Some v -> Printf.printf "  Mean: %.4f\n" v | None -> ());
      (match median with Some v -> Printf.printf "  Median: %.4f\n" v | None -> ());
      (match min with Some v -> Printf.printf "  Min: %.4f\n" v | None -> ());
      (match max with Some v -> Printf.printf "  Max: %.4f\n" v | None -> ());
      (match stddev with Some v -> Printf.printf "  StdDev: %.4f\n" v | None -> ())
  | _ -> Printf.printf "Error: stats <file> <field>\n"

let () =
  let args = List.tl (Array.to_list Sys.argv) in
  match args with
  | "analyze-csv" :: rest -> analyze_csv_cmd rest
  | "analyze-json" :: rest -> analyze_json_cmd rest
  | "upload" :: rest -> upload_cmd rest
  | "stats" :: rest -> stats_cmd rest
  | "help" :: _ | [] -> usage ()
  | cmd :: _ -> Printf.printf "Unknown command: %s\n" cmd; usage ()
