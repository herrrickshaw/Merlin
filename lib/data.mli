(* LFS Data loading and parsing *)

type record = (string * string) list

val parse_csv_line : string -> string list
val load_csv : string -> record list
val load_json : string -> Yojson.Basic.t list
val save_json : string -> Yojson.Basic.t list -> unit
val filter_records : record list -> (record -> bool) -> record list
val map_records : record list -> (record -> record) -> record list
val get_field : record -> string -> string option
val aggregate : record list -> string -> string -> (string list -> float option) -> (string * float option) list
