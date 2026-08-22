"""Diagnostic: when did each model's cache entries land? (throwaway, uncommitted)"""
import sqlite3

con = sqlite3.connect('agentaudit.db')
cur = con.cursor()

print("nemotron cache rows:")
for ts, in cur.execute(
    "select created_at from response_cache "
    "where model_version like 'nemotron%' order by created_at"
):
    print(' ', ts)

print("\nox-alpha current-gen cache span:")
for lo, hi, n in cur.execute(
    "select min(created_at), max(created_at), count(*) from response_cache "
    "where model_version = 'stealth/ox-alpha@2026-08-22'"
):
    print(f'  {lo} .. {hi}  ({n} rows)')

print("\nflagship cache span:")
for lo, hi, n in cur.execute(
    "select min(created_at), max(created_at), count(*) from response_cache "
    "where model_version like '%flagship'"
):
    print(f'  {lo} .. {hi}  ({n} rows)')

con.close()
