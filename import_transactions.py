import argparse
import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime

def clean_string(val):
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    return s if s.lower() != 'nan' else ""

def clean_numeric(val):
    if pd.isna(val) or val is None or str(val).strip() == '':
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0

def clean_date(val):
    if pd.isna(val) or val is None:
        return None
    try:
        if isinstance(val, pd.Timestamp) or isinstance(val, datetime):
            return val.strftime('%Y-%m-%d')
        parsed = pd.to_datetime(val)
        return parsed.strftime('%Y-%m-%d')
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description="Import historical transactions from Excel to Supabase.")
    parser.add_argument("--file", required=True, help="Path to the Excel file")
    parser.add_argument("--sheet", default="Invoice Tracker", help="Sheet name to read (default: 'Invoice Tracker')")
    parser.add_argument("--dry-run", action="store_true", help="Run without inserting data into Supabase")
    args = parser.parse_args()

    # Load from .env if present
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in your .env file or environment.")
        return

    # Initialize Supabase Client
    supabase: Client = create_client(url, key)

    print(f"Reading Excel file: {args.file}, Sheet: {args.sheet}")
    try:
         # Use openpyxl engine specifically as requested
        df = pd.read_excel(args.file, sheet_name=args.sheet, engine='openpyxl')
    except Exception as e:
        print(f"ERROR reading Excel file: {e}")
        return

    # Check for core columns before proceeding
    expected_cols = ['Invoice Number', 'Customer', 'Salesperson', 'Date']
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        print(f"ERROR: Missing expected columns in sheet: {', '.join(missing)}")
        return

    # Filter out completely empty rows based on Invoice Number
    df = df.dropna(subset=['Invoice Number'], how='all')

    stats = {
        "read": 0,
        "customers_inserted": 0,
        "salespersons_inserted": 0,
        "transactions_inserted": 0,
        "duplicates": 0,
        "errors": 0
    }

    # Fetch existing master data to avoid redundant checks/inserts
    print("Fetching existing data to prevent duplicates...")
    try:
        existing_customers = {c['name'].lower() for c in supabase.table("customers").select("name").execute().data}
        existing_salespersons = {s['name'].lower() for s in supabase.table("salespersons").select("name").execute().data}
        all_existing_tx = supabase.table("transactions").select("*").execute().data
    except Exception as e:
        print(f"ERROR connecting to Supabase: {e}")
        return
    
    # Helper to aggressively check for exact row duplicates
    def is_exact_duplicate(tx):
        for extx in all_existing_tx:
            # Check key fields for match
            if str(extx.get('invoice_no', '')) != str(tx['invoice_no']): continue
            if str(extx.get('customer', '')).lower() != str(tx['customer']).lower(): continue
            if str(extx.get('transaction_date', '')) != str(tx['transaction_date']): continue
            
            # Numeric checks (tolerance for float comparisons)
            if abs(float(extx.get('invoice_amount') or 0.0) - float(tx['invoice_amount'])) > 0.01: continue
            if abs(float(extx.get('payment_amount') or 0.0) - float(tx['payment_amount'])) > 0.01: continue
            
            # Sub-fields
            if str(extx.get('payment_type') or '') != str(tx['payment_type'] or ''): continue
            if str(extx.get('bank_account') or '') != str(tx['bank_account'] or ''): continue
            
            # If all these align, it's an exact duplicate
            return True
        return False

    if args.dry_run:
        print("\n=== DRY RUN MODE: No data will be written to the database ===\n")

    for index, row in df.iterrows():
        stats["read"] += 1
        try:
            invoice_no = clean_string(row.get('Invoice Number'))
            if not invoice_no:
                continue

            customer = clean_string(row.get('Customer'))
            salesperson = clean_string(row.get('Salesperson'))
            
            # Master data insertion logic
            if customer and customer.lower() not in existing_customers:
                if not args.dry_run:
                    supabase.table("customers").insert({"name": customer}).execute()
                existing_customers.add(customer.lower())
                stats["customers_inserted"] += 1
                prefix = "[DRY-RUN] " if args.dry_run else ""
                print(f"{prefix}Inserted new Customer: {customer}")

            if salesperson and salesperson.lower() not in existing_salespersons:
                if not args.dry_run:
                    supabase.table("salespersons").insert({"name": salesperson}).execute()
                existing_salespersons.add(salesperson.lower())
                stats["salespersons_inserted"] += 1
                prefix = "[DRY-RUN] " if args.dry_run else ""
                print(f"{prefix}Inserted new Salesperson: {salesperson}")

            # Define the transaction mapped dictionary
            tx_data = {
                "invoice_no": invoice_no,
                "customer": customer,
                "salesperson": salesperson,
                "transaction_date": clean_date(row.get('Date')),
                "invoice_amount": clean_numeric(row.get('Invoice Amount')),
                "payment_amount": clean_numeric(row.get('Payment Amount')),
                "payment_type": clean_string(row.get('Payment Type')) or None,
                "bank_account": clean_string(row.get('Bank Account')) or None,
                "remark": clean_string(row.get('Remark')) or None
            }

            # Pre-flight duplicate check
            if is_exact_duplicate(tx_data):
                stats["duplicates"] += 1
                print(f"Skipped duplicate row: Invoice {invoice_no} | Date: {tx_data['transaction_date']} | Pay: {tx_data['payment_amount']}")
                continue

            # Full insert transaction
            if not args.dry_run:
                response = supabase.table("transactions").insert(tx_data).execute()
                # Update local cache to catch duplicates occurring in the same Excel sheet
                if response.data:
                    all_existing_tx.append(response.data[0])
                else: 
                    all_existing_tx.append(tx_data)
                    
            stats["transactions_inserted"] += 1
            prefix = "[DRY-RUN] " if args.dry_run else ""
            print(f"{prefix}Inserted Transaction: Invoice {invoice_no} | Customer: {customer} | AED {tx_data['payment_amount']}")

        except Exception as e:
            stats["errors"] += 1
            # Excel rows are 1-indexed, and header is row 1. DataFrame index 0 is row 2.
            print(f"ERROR on Excel row {index + 2}: {e}")

    # Final summary display
    print("\n" + "="*40)
    print("IMPORT SUMMARY")
    print("="*40)
    print(f"Total rows read:       {stats['read']}")
    print(f"Customers inserted:    {stats['customers_inserted']}")
    print(f"Salespersons inserted: {stats['salespersons_inserted']}")
    print(f"Transactions inserted: {stats['transactions_inserted']}")
    print(f"Duplicates skipped:    {stats['duplicates']}")
    print(f"Row errors:            {stats['errors']}")
    print("="*40)
    if args.dry_run:
         print("This was a DRY RUN. No data was actually written to Supabase.")

if __name__ == "__main__":
    main()
