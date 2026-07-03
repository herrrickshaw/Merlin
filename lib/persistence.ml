(* Database Persistence for LFS Analysis Results
   Uses SQLite for efficient storage and querying *)

open Printf

type db = Sqlite3.db

(* Initialize database *)
let init_db filename =
  let db = Sqlite3.db_open filename in
  Sqlite3.exec db "
    CREATE TABLE IF NOT EXISTS stocks (
      id INTEGER PRIMARY KEY,
      symbol TEXT UNIQUE,
      market TEXT,
      last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ohlcv (
      id INTEGER PRIMARY KEY,
      stock_id INTEGER,
      date TEXT,
      open REAL,
      high REAL,
      low REAL,
      close REAL,
      volume INTEGER,
      FOREIGN KEY(stock_id) REFERENCES stocks(id),
      UNIQUE(stock_id, date)
    );

    CREATE TABLE IF NOT EXISTS fundamentals (
      id INTEGER PRIMARY KEY,
      stock_id INTEGER,
      roe REAL,
      revenue REAL,
      debt_to_equity REAL,
      current_ratio REAL,
      roa REAL,
      gross_margin REAL,
      asset_turnover REAL,
      FOREIGN KEY(stock_id) REFERENCES stocks(id)
    );

    CREATE TABLE IF NOT EXISTS screening_results (
      id INTEGER PRIMARY KEY,
      stock_id INTEGER,
      strategy TEXT,
      passed BOOLEAN,
      score REAL,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
      metrics TEXT,
      FOREIGN KEY(stock_id) REFERENCES stocks(id)
    );

    CREATE TABLE IF NOT EXISTS analysis_cache (
      id INTEGER PRIMARY KEY,
      stock_id INTEGER,
      metric_name TEXT,
      metric_value REAL,
      computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(stock_id, metric_name),
      FOREIGN KEY(stock_id) REFERENCES stocks(id)
    );

    CREATE INDEX IF NOT EXISTS idx_screening_strategy ON screening_results(strategy);
    CREATE INDEX IF NOT EXISTS idx_screening_passed ON screening_results(passed);
    CREATE INDEX IF NOT EXISTS idx_ohlcv_date ON ohlcv(date);
  " |> ignore;

  db

(* Insert stock *)
let insert_stock db symbol market =
  let stmt = Sqlite3.prepare db "INSERT OR IGNORE INTO stocks (symbol, market) VALUES (?, ?)" in
  Sqlite3.bind stmt 1 (Sqlite3.Data.TEXT symbol);
  Sqlite3.bind stmt 2 (Sqlite3.Data.TEXT market);
  let _ = Sqlite3.step stmt in
  Sqlite3.finalize stmt;

  (* Get the ID *)
  let stmt = Sqlite3.prepare db "SELECT id FROM stocks WHERE symbol = ?" in
  Sqlite3.bind stmt 1 (Sqlite3.Data.TEXT symbol);
  let id = match Sqlite3.step stmt with
    | Sqlite3.Rc.ROW ->
        (match Sqlite3.column stmt 0 with
        | Sqlite3.Data.INT i -> Some i
        | _ -> None)
    | _ -> None
  in
  Sqlite3.finalize stmt;
  id

(* Insert OHLCV data *)
let insert_ohlcv db stock_id date open_ high low close volume =
  let stmt = Sqlite3.prepare db
    "INSERT OR REPLACE INTO ohlcv (stock_id, date, open, high, low, close, volume)
     VALUES (?, ?, ?, ?, ?, ?, ?)" in
  Sqlite3.bind stmt 1 (Sqlite3.Data.INT stock_id);
  Sqlite3.bind stmt 2 (Sqlite3.Data.TEXT date);
  Sqlite3.bind stmt 3 (Sqlite3.Data.FLOAT open_);
  Sqlite3.bind stmt 4 (Sqlite3.Data.FLOAT high);
  Sqlite3.bind stmt 5 (Sqlite3.Data.FLOAT low);
  Sqlite3.bind stmt 6 (Sqlite3.Data.FLOAT close);
  Sqlite3.bind stmt 7 (Sqlite3.Data.INT (Int64.of_int volume));
  let _ = Sqlite3.step stmt in
  Sqlite3.finalize stmt

(* Insert fundamentals *)
let insert_fundamentals db stock_id roe revenue de cr roa gm at =
  let stmt = Sqlite3.prepare db
    "INSERT OR REPLACE INTO fundamentals
     (stock_id, roe, revenue, debt_to_equity, current_ratio, roa, gross_margin, asset_turnover)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)" in
  Sqlite3.bind stmt 1 (Sqlite3.Data.INT stock_id);
  Sqlite3.bind stmt 2 (match roe with Some f -> Sqlite3.Data.FLOAT f | None -> Sqlite3.Data.NULL);
  Sqlite3.bind stmt 3 (match revenue with Some f -> Sqlite3.Data.FLOAT f | None -> Sqlite3.Data.NULL);
  Sqlite3.bind stmt 4 (match de with Some f -> Sqlite3.Data.FLOAT f | None -> Sqlite3.Data.NULL);
  Sqlite3.bind stmt 5 (match cr with Some f -> Sqlite3.Data.FLOAT f | None -> Sqlite3.Data.NULL);
  Sqlite3.bind stmt 6 (match roa with Some f -> Sqlite3.Data.FLOAT f | None -> Sqlite3.Data.NULL);
  Sqlite3.bind stmt 7 (match gm with Some f -> Sqlite3.Data.FLOAT f | None -> Sqlite3.Data.NULL);
  Sqlite3.bind stmt 8 (match at with Some f -> Sqlite3.Data.FLOAT f | None -> Sqlite3.Data.NULL);
  let _ = Sqlite3.step stmt in
  Sqlite3.finalize stmt

(* Insert screening result *)
let insert_result db stock_id strategy passed score metrics =
  let stmt = Sqlite3.prepare db
    "INSERT INTO screening_results (stock_id, strategy, passed, score, metrics)
     VALUES (?, ?, ?, ?, ?)" in
  Sqlite3.bind stmt 1 (Sqlite3.Data.INT stock_id);
  Sqlite3.bind stmt 2 (Sqlite3.Data.TEXT strategy);
  Sqlite3.bind stmt 3 (Sqlite3.Data.INT (if passed then 1L else 0L));
  Sqlite3.bind stmt 4 (match score with Some f -> Sqlite3.Data.FLOAT f | None -> Sqlite3.Data.NULL);
  Sqlite3.bind stmt 5 (Sqlite3.Data.TEXT metrics);
  let _ = Sqlite3.step stmt in
  Sqlite3.finalize stmt

(* Query screening results *)
let query_results db strategy passed =
  let query = match passed with
    | Some true -> "SELECT s.symbol, sr.score, sr.metrics FROM screening_results sr
                    JOIN stocks s ON sr.stock_id = s.id
                    WHERE sr.strategy = ? AND sr.passed = 1
                    ORDER BY sr.score DESC"
    | Some false -> "SELECT s.symbol, sr.score, sr.metrics FROM screening_results sr
                     JOIN stocks s ON sr.stock_id = s.id
                     WHERE sr.strategy = ? AND sr.passed = 0"
    | None -> "SELECT s.symbol, sr.score, sr.metrics FROM screening_results sr
               JOIN stocks s ON sr.stock_id = s.id
               WHERE sr.strategy = ?"
  in

  let stmt = Sqlite3.prepare db query in
  Sqlite3.bind stmt 1 (Sqlite3.Data.TEXT strategy);

  let results = ref [] in
  let rec collect_results () =
    match Sqlite3.step stmt with
    | Sqlite3.Rc.ROW ->
        let symbol = match Sqlite3.column stmt 0 with
          | Sqlite3.Data.TEXT s -> s
          | _ -> ""
        in
        let score = match Sqlite3.column stmt 1 with
          | Sqlite3.Data.FLOAT f -> Some f
          | _ -> None
        in
        let metrics = match Sqlite3.column stmt 2 with
          | Sqlite3.Data.TEXT m -> m
          | _ -> ""
        in
        results := (symbol, score, metrics) :: !results;
        collect_results ()
    | _ -> ()
  in
  collect_results ();
  Sqlite3.finalize stmt;
  List.rev !results

(* Get stock OHLCV *)
let get_ohlcv db symbol =
  let stmt = Sqlite3.prepare db
    "SELECT date, open, high, low, close, volume FROM ohlcv
     WHERE stock_id = (SELECT id FROM stocks WHERE symbol = ?)
     ORDER BY date ASC" in
  Sqlite3.bind stmt 1 (Sqlite3.Data.TEXT symbol);

  let data = ref [] in
  let rec collect () =
    match Sqlite3.step stmt with
    | Sqlite3.Rc.ROW ->
        let date = match Sqlite3.column stmt 0 with
          | Sqlite3.Data.TEXT d -> d | _ -> ""
        in
        let open_ = match Sqlite3.column stmt 1 with
          | Sqlite3.Data.FLOAT f -> f | _ -> 0.0
        in
        let high = match Sqlite3.column stmt 2 with
          | Sqlite3.Data.FLOAT f -> f | _ -> 0.0
        in
        let low = match Sqlite3.column stmt 3 with
          | Sqlite3.Data.FLOAT f -> f | _ -> 0.0
        in
        let close = match Sqlite3.column stmt 4 with
          | Sqlite3.Data.FLOAT f -> f | _ -> 0.0
        in
        let volume = match Sqlite3.column stmt 5 with
          | Sqlite3.Data.INT i -> Int64.to_int i | _ -> 0
        in
        data := (date, open_, high, low, close, volume) :: !data;
        collect ()
    | _ -> ()
  in
  collect ();
  Sqlite3.finalize stmt;
  List.rev !data

(* Cache analysis metrics *)
let cache_metric db stock_id metric_name value =
  let stmt = Sqlite3.prepare db
    "INSERT OR REPLACE INTO analysis_cache (stock_id, metric_name, metric_value)
     VALUES (?, ?, ?)" in
  Sqlite3.bind stmt 1 (Sqlite3.Data.INT stock_id);
  Sqlite3.bind stmt 2 (Sqlite3.Data.TEXT metric_name);
  Sqlite3.bind stmt 3 (Sqlite3.Data.FLOAT value);
  let _ = Sqlite3.step stmt in
  Sqlite3.finalize stmt

(* Get cached metric *)
let get_cached_metric db stock_id metric_name =
  let stmt = Sqlite3.prepare db
    "SELECT metric_value FROM analysis_cache
     WHERE stock_id = ? AND metric_name = ?
     ORDER BY computed_at DESC LIMIT 1" in
  Sqlite3.bind stmt 1 (Sqlite3.Data.INT stock_id);
  Sqlite3.bind stmt 2 (Sqlite3.Data.TEXT metric_name);

  let result = match Sqlite3.step stmt with
    | Sqlite3.Rc.ROW ->
        (match Sqlite3.column stmt 0 with
        | Sqlite3.Data.FLOAT f -> Some f
        | _ -> None)
    | _ -> None
  in
  Sqlite3.finalize stmt;
  result

(* Statistics *)
let get_statistics db =
  let get_count query =
    let stmt = Sqlite3.prepare db query in
    let count = match Sqlite3.step stmt with
      | Sqlite3.Rc.ROW ->
          (match Sqlite3.column stmt 0 with
          | Sqlite3.Data.INT i -> Int64.to_int i
          | _ -> 0)
      | _ -> 0
    in
    Sqlite3.finalize stmt;
    count
  in

  let stocks = get_count "SELECT COUNT(*) FROM stocks" in
  let ohlcv_bars = get_count "SELECT COUNT(*) FROM ohlcv" in
  let results = get_count "SELECT COUNT(*) FROM screening_results" in
  let strategies = get_count "SELECT COUNT(DISTINCT strategy) FROM screening_results" in

  {|Statistics:
  Stocks: |} ^ string_of_int stocks ^ {|
  OHLCV bars: |} ^ string_of_int ohlcv_bars ^ {|
  Screening results: |} ^ string_of_int results ^ {|
  Strategies run: |} ^ string_of_int strategies

(* Close database *)
let close_db db =
  Sqlite3.db_close db
