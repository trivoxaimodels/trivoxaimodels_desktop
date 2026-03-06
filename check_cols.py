import psycopg2
import sys

try:
    conn = psycopg2.connect('postgresql://postgres:u-1fPnWekHYPzq4VUV-ctQm5QdR5OQnnX9w2fSrRdWs@db.iiyewbxdgncosiqtllnm.supabase.co:5432/postgres')
    cur = conn.cursor()
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='registered_devices'")
    rows = cur.fetchall()
    print("Columns in registered_devices:")
    for row in rows:
        print(row)
except Exception as e:
    print(e)
