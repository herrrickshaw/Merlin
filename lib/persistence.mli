(* Database Persistence Interface *)

type db

(* Database operations *)
val init_db : string -> db
val close_db : db -> unit

(* Insert operations *)
val insert_stock : db -> string -> string -> int option
val insert_ohlcv : db -> int -> string -> float -> float -> float -> float -> int -> unit
val insert_fundamentals : db -> int -> float option -> float option -> float option ->
                          float option -> float option -> float option -> float option -> unit
val insert_result : db -> int -> string -> bool -> float option -> string -> unit

(* Query operations *)
val query_results : db -> string -> bool option -> (string * float option * string) list
val get_ohlcv : db -> string -> (string * float * float * float * float * int) list

(* Caching *)
val cache_metric : db -> int -> string -> float -> unit
val get_cached_metric : db -> int -> string -> float option

(* Statistics *)
val get_statistics : db -> string
