"""Diagnostic: inspect the two overnight runs + cache state. (throwaway)"""
import sqlite3

con = sqlite3.connect('agentaudit.db')
cur = con.cursor()

for rid in ('a840125c-69ee-4d2a-8eae-a2627983b988',
            '6ee157a7-83dd-42e6-b326-59272f5d38d3'):
    print('=== RUN', rid)
    print('run row:', cur.execute(
        'select status,type,parent_run_id,cost_usd,trials_total,started_at,completed_at '
        'from runs where id=?', (rid,)).fetchone())
    print('per-model (count, parse_ok_sum, from_cache_sum):')
    for row in cur.execute(
        'select model, count(*), sum(parse_ok), sum(from_cache) '
        'from trials where run_id=? group by model', (rid,)
    ):
        print('  ', row)
    print()

print('response_cache per model_version:')
for row in cur.execute(
    'select model_version, count(*), max(created_at) from response_cache '
    'group by model_version'
):
    print('  ', row)

con.close()
