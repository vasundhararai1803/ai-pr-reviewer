import sqlite3

# Secret leak
PASSWORD = "super_secret_password_123"

def find_user(username):
    # SQL Injection flaw
    db = sqlite3.connect("data.db")
    return db.execute(f"SELECT * FROM users WHERE name = '{username}'")
