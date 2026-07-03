(* LFS Data loading and parsing *)

type record = (string * string) list

let parse_csv_line line =
  let rec parse_fields acc current = function
    | [] ->
        List.rev (String.trim current :: acc)
    | '"' :: rest ->
        let in_quotes = ref true in
        let field_chars = ref [] in
        let rec read_quoted () = match rest with
          | [] -> List.rev !field_chars
          | '"' :: '"' :: tail -> field_chars := '"' :: !field_chars; read_quoted_rest tail
          | '"' :: tail -> read_quoted_rest tail
          | c :: tail -> field_chars := c :: !field_chars; read_quoted ()
        and read_quoted_rest = function
          | ',' :: tail -> parse_fields (String.trim (String.concat "" (List.map String.make [1] !field_chars)) :: acc) "" tail
          | ' ' :: tail -> read_quoted_rest tail
          | c :: tail -> field_chars := c :: !field_chars; read_quoted_rest tail
          | [] -> List.rev !field_chars
        in
        let quoted_content = read_quoted () in
        parse_fields (String.concat "" (List.map String.make [1] quoted_content) :: acc) "" []
    | ',' :: rest ->
        parse_fields (String.trim current :: acc) "" rest
    | c :: rest ->
        parse_fields acc (current ^ String.make 1 c) rest
  in
  parse_fields [] "" (List.init (String.length line) (String.get line))

let load_csv file =
  let ic = open_in file in
  let headers =
    try
      let line = input_line ic in
      parse_csv_line line
    with End_of_file -> []
  in
  let rec read_records acc =
    try
      let line = input_line ic in
      if String.length (String.trim line) > 0 then
        let values = parse_csv_line line in
        let record = List.combine headers values in
        read_records (record :: acc)
      else
        read_records acc
    with End_of_file ->
      close_in ic;
      List.rev acc
  in
  read_records []

let load_json file =
  let ic = open_in file in
  let json_str = really_input_string ic (in_channel_length ic) in
  close_in ic;
  try
    match Yojson.Basic.from_string json_str with
    | `List items -> items
    | _ -> []
  with _ -> []

let save_json file data =
  let oc = open_out file in
  output_string oc (Yojson.Basic.pretty_to_string (`List data));
  close_out oc

let filter_records records predicate =
  List.filter (fun record ->
    predicate record
  ) records

let map_records records transform =
  List.map (fun record ->
    transform record
  ) records

let get_field record key =
  try Some (List.assoc key record)
  with Not_found -> None

let aggregate records key_field agg_field agg_fn =
  let groups = Hashtbl.create 100 in
  List.iter (fun record ->
    match get_field record key_field, get_field record agg_field with
    | Some k, Some v ->
        let values =
          try Hashtbl.find groups k
          with Not_found -> []
        in
        Hashtbl.replace groups k (v :: values)
    | _ -> ()
  ) records;

  Hashtbl.fold (fun key values acc ->
    (key, agg_fn values) :: acc
  ) groups []
