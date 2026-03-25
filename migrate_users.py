import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'app.db')

if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), 'app.db')

def migrate_users():
    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'role' not in columns:
            print("Adding 'role' column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'staff'")
            
        if 'is_active' not in columns:
            print("Adding 'is_active' column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")
            
        # Ensure the default admin user is actually set as an admin
        print("Setting existing 'admin' user to have admin role...")
        cursor.execute("UPDATE users SET role = 'admin' WHERE username = 'admin'")
        
        conn.commit()
        print("Successfully migrated users table!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_users()
