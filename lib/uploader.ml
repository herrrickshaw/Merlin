(* Git-based upload to Merlin repo *)

let run_cmd cmd =
  let ic = Unix.open_process_in cmd in
  let output = really_input_string ic (in_channel_length ic) in
  let _ = Unix.close_process_in ic in
  String.trim output

let git_add repo path =
  run_cmd (Printf.sprintf "cd %s && git add %s 2>&1" repo path)

let git_commit repo message =
  let safe_msg = String.concat " " (String.split_on_char '\n' message) in
  run_cmd (Printf.sprintf "cd %s && git commit -m \"%s\" 2>&1" repo safe_msg)

let git_push repo branch =
  run_cmd (Printf.sprintf "cd %s && git push origin %s 2>&1" repo branch)

let upload_file repo source dest_path =
  let dest = Filename.concat repo dest_path in
  let dest_dir = Filename.dirname dest in
  if not (Sys.file_exists dest_dir) then
    run_cmd (Printf.sprintf "mkdir -p %s" dest_dir) |> ignore;
  Sys.copy_file source dest;
  git_add repo dest_path

let upload_data repo filename data format =
  let dest = Filename.concat repo filename in
  let dest_dir = Filename.dirname dest in
  if not (Sys.file_exists dest_dir) then
    run_cmd (Printf.sprintf "mkdir -p %s" dest_dir) |> ignore;

  let oc = open_out dest in
  (match format with
  | "json" -> output_string oc data
  | "csv" -> output_string oc data
  | "txt" -> output_string oc data
  | _ -> output_string oc data);
  close_out oc;

  git_add repo filename

let upload_analysis repo timestamp analysis_type results =
  let date = Unix.time () |> int_of_float |> string_of_int in
  let filename = Printf.sprintf "analyses/%s-%s.json" analysis_type date in

  let json_data = Yojson.Basic.to_string (`Assoc [
    ("timestamp", `Int (int_of_float (Unix.time ())));
    ("type", `String analysis_type);
    ("results", `Assoc results)
  ]) in

  upload_data repo filename json_data "json"

let commit_and_push repo branch message =
  let _ = git_commit repo message in
  git_push repo branch

let status repo =
  run_cmd (Printf.sprintf "cd %s && git status --porcelain" repo)

let log repo limit =
  run_cmd (Printf.sprintf "cd %s && git log --oneline -n %d" repo limit)
