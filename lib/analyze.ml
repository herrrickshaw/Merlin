(* Data analysis operations *)

let float_of_string_opt s =
  try Some (Float.of_string (String.trim s))
  with _ -> None

let int_of_string_opt s =
  try Some (Int.of_string (String.trim s))
  with _ -> None

let mean values =
  match values with
  | [] -> None
  | _ ->
      let floats = List.filter_map float_of_string_opt values in
      if List.length floats = 0 then None
      else
        let sum = List.fold_left (+.) 0.0 floats in
        Some (sum /. Float.of_int (List.length floats))

let median values =
  let floats = List.filter_map float_of_string_opt values in
  match floats with
  | [] -> None
  | _ ->
      let sorted = List.sort Float.compare floats in
      let len = List.length sorted in
      if len mod 2 = 0 then
        let mid = len / 2 in
        Some ((List.nth sorted (mid - 1) +. List.nth sorted mid) /. 2.0)
      else
        Some (List.nth sorted (len / 2))

let sum values =
  let floats = List.filter_map float_of_string_opt values in
  match floats with
  | [] -> None
  | _ -> Some (List.fold_left (+.) 0.0 floats)

let count values =
  List.length values

let min values =
  let floats = List.filter_map float_of_string_opt values in
  match floats with
  | [] -> None
  | x :: xs -> Some (List.fold_left Float.min x xs)

let max values =
  let floats = List.filter_map float_of_string_opt values in
  match floats with
  | [] -> None
  | x :: xs -> Some (List.fold_left Float.max x xs)

let stddev values =
  let floats = List.filter_map float_of_string_opt values in
  match floats with
  | [] -> None
  | _ ->
      let n = Float.of_int (List.length floats) in
      let mean_val = List.fold_left (+.) 0.0 floats /. n in
      let variance =
        List.fold_left (fun acc x ->
          acc +. (x -. mean_val) ** 2.0
        ) 0.0 floats /. n
      in
      Some (Float.sqrt variance)

let percentile values p =
  let floats = List.filter_map float_of_string_opt values in
  match floats with
  | [] -> None
  | _ ->
      let sorted = List.sort Float.compare floats in
      let len = List.length sorted in
      let idx = Float.to_int (Float.of_int (len - 1) *. (p /. 100.0)) in
      Some (List.nth sorted (min idx (len - 1)))

let filter_by_range values min_val max_val =
  List.filter_map (fun v ->
    match float_of_string_opt v with
    | Some f when f >= min_val && f <= max_val -> Some v
    | _ -> None
  ) values

let count_by_category values =
  let counts = Hashtbl.create 100 in
  List.iter (fun v ->
    let count = try Hashtbl.find counts v with Not_found -> 0 in
    Hashtbl.replace counts v (count + 1)
  ) values;
  Hashtbl.fold (fun k v acc -> (k, v) :: acc) counts []
