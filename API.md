# Merlin API Reference

Complete API documentation for Merlin's OCaml modules.

## Module: Data

Low-level CSV/JSON parsing and record operations.

### Types

```ocaml
type record = (string * string) list  (* Key-value pairs *)
```

### Functions

#### `parse_csv_line : string -> string list`
Parse a single CSV line into fields.

```ocaml
let fields = parse_csv_line "Name,Age,City"
(* Result: ["Name"; "Age"; "City"] *)
```

**Handles:**
- Quoted fields with commas
- Escaped quotes
- Whitespace trimming

#### `load_csv : string -> record list`
Load and parse a CSV file.

```ocaml
let records = load_csv "data.csv"
(* Each record: [("symbol", "RELIANCE"); ("price", "2880"); ...] *)
```

#### `load_json : string -> Yojson.Basic.t list`
Load JSON array from file.

```ocaml
let items = load_json "data.json"
```

#### `save_json : string -> Yojson.Basic.t list -> unit`
Save JSON data to file.

```ocaml
save_json "output.json" json_data
```

#### `filter_records : record list -> (record -> bool) -> record list`
Filter records by predicate.

```ocaml
let high_prices = filter_records records (fun r ->
  match get_field r "price" with
  | Some p -> Float.of_string p > 3000.0
  | None -> false
)
```

#### `map_records : record list -> (record -> record) -> record list`
Transform each record.

```ocaml
let doubled = map_records records (fun r ->
  match get_field r "quantity" with
  | Some q ->
      let new_qty = string_of_int (int_of_string q * 2) in
      ("quantity", new_qty) :: (List.remove_assoc "quantity" r)
  | None -> r
)
```

#### `get_field : record -> string -> string option`
Get field value from record.

```ocaml
match get_field record "symbol" with
| Some s -> Printf.printf "Symbol: %s\n" s
| None -> Printf.printf "Field not found\n"
```

#### `aggregate : record list -> string -> string -> (string list -> float option) -> (string * float option) list`
Group and aggregate records.

**Parameters:**
- `records` - Input records
- `key_field` - Grouping field
- `agg_field` - Field to aggregate
- `agg_fn` - Aggregation function

```ocaml
let avg_prices = aggregate records "symbol" "close" Analyze.mean
(* Result: [("RELIANCE", Some 2880.5); ("TCS", Some 3215.0); ...] *)
```

---

## Module: Analyze

Statistical analysis operations.

### Functions

#### `mean : string list -> float option`
Calculate arithmetic mean.

```ocaml
let prices = ["100"; "200"; "300"] in
mean prices  (* Some 200.0 *)
```

#### `median : string list -> float option`
Calculate median value.

```ocaml
let prices = ["100"; "200"; "300"; "400"; "500"] in
median prices  (* Some 300.0 *)
```

#### `sum : string list -> float option`
Calculate sum.

```ocaml
sum ["10"; "20"; "30"]  (* Some 60.0 *)
```

#### `count : string list -> int`
Count elements.

```ocaml
count ["a"; "b"; "c"]  (* 3 *)
```

#### `min : string list -> float option`
Find minimum value.

```ocaml
min ["50"; "10"; "100"]  (* Some 10.0 *)
```

#### `max : string list -> float option`
Find maximum value.

```ocaml
max ["50"; "10"; "100"]  (* Some 100.0 *)
```

#### `stddev : string list -> float option`
Calculate standard deviation.

```ocaml
stddev ["1"; "2"; "3"; "4"; "5"]  (* Some 1.414... *)
```

#### `percentile : string list -> float -> float option`
Calculate nth percentile (0-100).

```ocaml
percentile values 95.0  (* 95th percentile *)
```

#### `filter_by_range : string list -> float -> float -> string list`
Filter values within range.

```ocaml
filter_by_range prices 100.0 500.0
(* Returns values between 100 and 500 *)
```

#### `count_by_category : string list -> (string * int) list`
Count occurrences of each category.

```ocaml
count_by_category ["A"; "B"; "A"; "C"; "B"; "B"]
(* [("A", 2); ("B", 3); ("C", 1)] *)
```

---

## Module: Uploader

Git-based repository operations.

### Functions

#### `run_cmd : string -> string`
Execute shell command and return output.

```ocaml
let status = run_cmd "git status"
```

#### `git_add : string -> string -> string`
Add file to git index.

**Parameters:**
- `repo` - Repository path
- `path` - File path (relative to repo)

```ocaml
git_add "/path/to/repo" "data/results.json"
```

#### `git_commit : string -> string -> string`
Commit changes with message.

**Parameters:**
- `repo` - Repository path
- `message` - Commit message

```ocaml
git_commit "/path/to/repo" "Update analysis results"
```

#### `git_push : string -> string -> string`
Push to remote branch.

```ocaml
git_push "/path/to/repo" "main"
```

#### `upload_file : string -> string -> string -> string`
Copy file to repo and stage it.

**Parameters:**
- `repo` - Repository path
- `source` - Source file path
- `dest_path` - Destination path (relative to repo)

```ocaml
upload_file "/path/to/repo" "local_data.csv" "data/uploaded.csv"
```

#### `upload_data : string -> string -> string -> string -> unit`
Write data to repo file.

**Parameters:**
- `repo` - Repository path
- `filename` - Target filename (relative to repo)
- `data` - Data to write
- `format` - Format type ("json", "csv", "txt")

```ocaml
let json_str = Yojson.Basic.to_string json_data in
upload_data repo "results.json" json_str "json"
```

#### `upload_analysis : string -> string -> string -> (string * Yojson.Basic.t) list -> string`
Upload analysis results with timestamp.

**Parameters:**
- `repo` - Repository path
- `timestamp` - Timestamp string
- `analysis_type` - Type of analysis
- `results` - Assoc list of results

```ocaml
upload_analysis repo "20250101" "stock_prices" [
  ("mean", `Float 2900.0);
  ("count", `Int 100);
]
```

#### `commit_and_push : string -> string -> string -> string`
Commit and push in one operation.

```ocaml
commit_and_push "/path/to/repo" "main" "Add new analysis"
```

#### `status : string -> string`
Get git status output.

```ocaml
let changes = status "/path/to/repo"
```

#### `log : string -> int -> string`
Get git log (last N commits).

```ocaml
log "/path/to/repo" 10  (* Last 10 commits *)
```

---

## Usage Examples

### Example 1: Analyze and Upload

```ocaml
(* Load data *)
let records = Data.load_csv "stocks.csv" in

(* Get closing prices for analysis *)
let prices = List.filter_map (fun r ->
  Data.get_field r "close"
) records in

(* Compute statistics *)
let stats = [
  ("mean", Analyze.mean prices);
  ("median", Analyze.median prices);
  ("stddev", Analyze.stddev prices);
] in

(* Upload results *)
let repo = Sys.getenv "MERLIN_REPO" in
let _ = Uploader.upload_analysis repo "" "stock_analysis" 
  (List.map (fun (k, v) ->
    (k, match v with
    | Some f -> `Float f
    | None -> `Null)
  ) stats)
in
Uploader.commit_and_push repo "main" "Stock analysis results"
```

### Example 2: Batch Processing

```ocaml
(* Process multiple files *)
let files = ["nse.csv"; "bse.csv"; "mcx.csv"] in
List.iter (fun file ->
  let records = Data.load_csv file in
  let avg_close = Analyze.mean (List.filter_map (fun r ->
    Data.get_field r "close"
  ) records) in

  Printf.printf "%s: avg = %s\n" file (
    match avg_close with
    | Some f -> Printf.sprintf "%.2f" f
    | None -> "N/A"
  );

  (* Upload *)
  let json = `Assoc [("file", `String file); ("average", match avg_close with
    | Some f -> `Float f | None -> `Null)] in
  Uploader.upload_data repo (file ^ ".json") 
    (Yojson.Basic.to_string json) "json"
) files
```

### Example 3: Aggregation Pipeline

```ocaml
(* Load records *)
let records = Data.load_csv "market_data.csv" in

(* Filter by sector *)
let it_stocks = Data.filter_records records (fun r ->
  match Data.get_field r "sector" with
  | Some s -> s = "IT"
  | None -> false
) in

(* Aggregate by company *)
let avg_by_company = Data.aggregate it_stocks "symbol" "close" Analyze.mean in

(* Print results *)
List.iter (fun (symbol, avg) ->
  Printf.printf "%s: %s\n" symbol (
    match avg with
    | Some f -> Printf.sprintf "%.2f" f
    | None -> "N/A"
  )
) avg_by_company
```

---

## Error Handling

Most functions use `option` types for safe error handling:

```ocaml
match Analyze.mean values with
| Some mean_val -> Printf.printf "Mean: %.2f\n" mean_val
| None -> Printf.printf "Cannot compute mean\n"
```

For file I/O errors, functions raise standard OCaml exceptions.

---

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| `load_csv` | O(n) | Linear in file size |
| `parse_csv_line` | O(m) | m = line length |
| `filter_records` | O(n) | n = record count |
| `aggregate` | O(n log n) | Due to sorting in fold |
| `mean/median` | O(n) | Full pass over data |
| `stddev` | O(n) | Two passes required |
| `git_add` | O(1) | File staging |
| `git_push` | O(f) | f = file size |

---

## Dependencies

- `str` - String processing (OCaml stdlib)
- `yojson` - JSON handling
- `unix` - System operations (git, file I/O)

## Thread Safety

The current implementation is NOT thread-safe. For concurrent operations:
- Use separate OCaml processes
- Synchronize access to `Uploader` module
- Or use Merlin.exe CLI (inherently single-threaded)
