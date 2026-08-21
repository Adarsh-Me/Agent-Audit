"""Stall check: flushed trial counts + newest timestamps for the live run."""
import sqlite3

cx = sqlite3.connect("agentaudit.db")
rows = cx.execute(
    "select model, count(*), max(latency_ms), sum(parse_ok) "
    "from trials where run_id like 'a481127e%' group by model"
).fetchall()
print("model            flushed  max_lat_ms  parsed")
for m, n, mx, ok in rows:
    print(f"{m:16s} {n:7d}  {mx:10d}  {ok:6d}")
total = cx.execute(
    "select count(*) from trials where run_id like 'a481127e%'"
).fetchone()[0]
print("flushed total:", total)
