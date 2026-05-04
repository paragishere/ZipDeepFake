import sqlite3

DB_NAME = "database.db"

def get_db():
    conn = sqlite3.connect("database.db", timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()



    # logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,           
        filename TEXT,
        result TEXT,
        ip TEXT,
        user_agent TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # event table
    cursor.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT,
    ip TEXT,
    endpoint TEXT,
    method TEXT,
    user_agent TEXT,
    status TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

    # 🔐 admin table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)
# login user with google
    # user table
    cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password TEXT NULL,
    is_verified INTEGER DEFAULT 0,
    otp TEXT,               
    ip TEXT,
    user_agent TEXT,               
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")

    conn.commit()
    conn.close()
    