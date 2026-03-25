import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'app.db')

def migrate():
    print(f"Connecting to database at {db_path}...")
    if not os.path.exists(db_path):
        print("Database not found! Migration aborted.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if the UNIQUE index exists explicitly
        cursor.execute("PRAGMA index_list('transactions');")
        indexes = cursor.fetchall()
        
        # In SQLite, when a column is created with UNIQUE, it creates an auto-index like sqlite_autoindex_transactions_1
        # The safest way to drop a constraint in SQLite is to recreate the table.
        
        print("Creating transactions_new table...")
        cursor.execute("""
            CREATE TABLE transactions_new (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                salesperson_id INTEGER NOT NULL,
                invoice_number VARCHAR(50) NOT NULL,
                date DATE NOT NULL,
                invoice_amount FLOAT,
                payment_amount FLOAT,
                payment_type_id INTEGER,
                bank_account_id INTEGER,
                remark TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers (id),
                FOREIGN KEY(salesperson_id) REFERENCES salespersons (id),
                FOREIGN KEY(payment_type_id) REFERENCES payment_types (id),
                FOREIGN KEY(bank_account_id) REFERENCES bank_accounts (id)
            )
        """)

        print("Copying data from transactions to transactions_new...")
        cursor.execute("""
            INSERT INTO transactions_new (id, customer_id, salesperson_id, invoice_number, date, invoice_amount, payment_amount, payment_type_id, bank_account_id, remark)
            SELECT id, customer_id, salesperson_id, invoice_number, date, invoice_amount, payment_amount, payment_type_id, bank_account_id, remark 
            FROM transactions
        """)

        print("Dropping old transactions table...")
        cursor.execute("DROP TABLE transactions")

        print("Renaming transactions_new to transactions...")
        cursor.execute("ALTER TABLE transactions_new RENAME TO transactions")

        conn.commit()
        print("Migration completed successfully! UNIQUE constraint removed from invoice_number.")
    
    except Exception as e:
        conn.rollback()
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
