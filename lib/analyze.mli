(* Data analysis operations *)

val float_of_string_opt : string -> float option
val int_of_string_opt : string -> int option
val mean : string list -> float option
val median : string list -> float option
val sum : string list -> float option
val count : string list -> int
val min : string list -> float option
val max : string list -> float option
val stddev : string list -> float option
val percentile : string list -> float -> float option
val filter_by_range : string list -> float -> float -> string list
val count_by_category : string list -> (string * int) list
