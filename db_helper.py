from psycopg2 import pool
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

db_pool = pool.ThreadedConnectionPool(1, 10, dsn=DATABASE_URL)

def get_db_connection():
    return db_pool.getconn()

def put_db_connection(conn):
    db_pool.putconn(conn)

def close_db_connections():
    db_pool.closeall()

def query_db(query, args=(), one=False):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, args)
    result = cur.fetchall()
    cur.close()
    put_db_connection(conn)
    return (result[0] if result else None) if one else result

def modify_db(query, args=()):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    cur.close()
    put_db_connection(conn)
