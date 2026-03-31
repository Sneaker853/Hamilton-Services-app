import sys
sys.path.insert(0, r"c:\Database\portfolio_web\backend")
from db import init_db_pool, get_cursor
from migrations_runner import run_migrations

init_db_pool()
print("Running migrations...")
run_migrations()
print("Done.")

with get_cursor(dict_cursor=True) as (_, cur):
    cur.execute("""SELECT table_name FROM information_schema.tables 
                   WHERE table_schema='public' 
                   AND table_name IN ('user_watchlist','price_alerts','portfolio_snapshots','portfolio_goals','audit_log')
                   ORDER BY table_name""")
    print("New tables:", [r['table_name'] for r in cur.fetchall()])

    cur.execute("""SELECT column_name FROM information_schema.columns 
                   WHERE table_name='stocks' AND column_name IN ('esg_score','carbon_intensity')""")
    print("ESG columns:", [r['column_name'] for r in cur.fetchall()])

    cur.execute("""SELECT filename FROM schema_migrations ORDER BY filename""")
    print("Applied migrations:", [r['filename'] for r in cur.fetchall()])
