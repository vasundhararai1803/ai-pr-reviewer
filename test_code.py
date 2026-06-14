import sqlite3

def get_user_data(username):
    # ❌ VULNERABILITY: Direct string formatting allows SQL Injection!
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()

def process_items(items):
    # ❌ BUG: This loop will run infinitely if items is not empty!
    i = 0
    while i < len(items):
        print(f"Processing: {items[i]}")
        # Missing: i += 1
