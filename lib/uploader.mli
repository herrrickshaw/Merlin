(* Git-based upload to Merlin repo *)

val run_cmd : string -> string
val git_add : string -> string -> string
val git_commit : string -> string -> string
val git_push : string -> string -> string
val upload_file : string -> string -> string -> string
val upload_data : string -> string -> string -> string -> unit
val upload_analysis : string -> string -> string -> (string * Yojson.Basic.t) list -> string
val commit_and_push : string -> string -> string -> string
val status : string -> string
val log : string -> int -> string
