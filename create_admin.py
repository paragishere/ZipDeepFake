import sqlite3
import hashlib

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

username = "admin"
password = "admin123"

# 🔥 password hash
hashed = hashlib.sha256(password.encode()).hexdigest()

cursor.execute("INSERT INTO admin (username, password) VALUES (?, ?)", (username, hashed))

conn.commit()
conn.close()

print("✅ Admin created")