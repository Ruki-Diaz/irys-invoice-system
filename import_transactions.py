import os
import argparse
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime

def setup_cli():
    parser = argparse.ArgumentParser(description="Import transactions from Excel to Supabase")
    parser.add_argument("--file", required=True, help="Path to the Excel file")
    parser.add_argument("--sheet", default="Invoice Tracker", help="Name of the sheet to read")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without inserting data")
    return parser.parse_args()

def clean_string(val):
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() == 'nan' else s

def clean_number(val):
    if pd.isna(val) or val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def clean_date(val):
    if pd.isna(val) or val is None:
        return None
    try:
        if isinstance(val, datetime):
            return val.strftime('%Y-%m-%d')
        # Parse using pandas
        dt = pd.to_datetime(val)
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return None

def main():
    args = setup_cli()
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env or environment")
        return
        
    print(f"Connecting to Supabase at {url}...")
    supabase: Client = create_client(url, key)
    print("Supabase connected using service role key")
    
    # Load existing master data to minimize API calls
    print("Loading existing master data from Supabase...")
    existing_customers = {row['name'].lower(): row['name'] for row in supabase.table("customers").select("*").execute().data}
    existing_salespersons = {row['name'].lower(): row['name'] for row in supabase.table("salespersons").select("*").execute().data}
    
    print("Loading existing transactions to prevent duplicates...")
    existing_tx_data = supabase.table("transactions").select("*").execute().data
    
    # Create a set of signatures for fast duplicate checking
    # Signature: (invoice_no, customer, salesperson, transaction_date, invoice_amount, payment_amount, payment_type, bank_account, remark)
    def make_tx_signature(tx):
        return (
            str(tx.get('invoice_no') or '').strip().lower(),
            str(tx.get('customer') or '').strip().lower(),
            str(tx.get('salesperson') or '').strip().lower(),
            str(tx.get('transaction_date') or '').strip(),
            round(float(tx.get('invoice_amount') or 0.0), 2),
            round(float(tx.get('payment_amount') or 0.0), 2),
            str(tx.get('payment_type') or '').strip().lower(),
            str(tx.get('bank_account') or '').strip().lower(),
            str(tx.get('remark') or '').strip().lower()
        )
        
    existing_tx_signatures = set([make_tx_signature(tx) for tx in existing_tx_data])
    
    try:
        print(f"Reading Excel file: '{args.file}', Sheet: '{args.sheet}'...")
        df = pd.read_excel(args.file, sheet_name=args.sheet, engine='openpyxl')
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return
        
    # Summary counters
    total_read = 0
    customers_inserted = 0
    salespersons_inserted = 0
    tx_inserted = 0
    dups_skipped = 0
    errors = 0
    
    # Process rows
    print("\n--- Starting processing rows ---")
    if args.dry_run:
        print("*** DRY RUN MODE: No data will be written ***\n")
        
    for index, row in df.iterrows():
        # Skip fully empty rows based on checking if all values are NaN
        if row.isna().all():
            continue
            
        try:
            date_val = clean_date(row.get('Date'))
            inv_no = clean_string(row.get('Invoice Number'))
            customer = clean_string(row.get('Customer'))
            salesperson = clean_string(row.get('Salesperson'))
            
            # If critical fields are missing, treat as empty row or error
            if not inv_no and not customer and not date_val:
                continue
                
            total_read += 1
            
            inv_amt = clean_number(row.get('Invoice Amount'))
            pay_amt = clean_number(row.get('Payment Amount'))
            pay_type = clean_string(row.get('Payment Type'))
            bank_acc = clean_string(row.get('Bank Account'))
            remark = clean_string(row.get('Remark'))
            
            # 1. Ensure Customer
            if customer:
                c_key = customer.lower()
                if c_key not in existing_customers:
                    if not args.dry_run:
                        supabase.table("customers").insert({"name": customer}).execute()
                    print(f" [Customer] Inserted: {customer}")
                    existing_customers[c_key] = customer
                    customers_inserted += 1
                    
            # 2. Ensure Salesperson
            if salesperson:
                s_key = salesperson.lower()
                if s_key not in existing_salespersons:
                    if not args.dry_run:
                        supabase.table("salespersons").insert({"name": salesperson}).execute()
                    print(f" [Salesperson] Inserted: {salesperson}")
                    existing_salespersons[s_key] = salesperson
                    salespersons_inserted += 1
            
            # 3. Handle Transaction Insertion
            tx_data = {
                'invoice_no': inv_no,
                'customer': customer,
                'salesperson': salesperson,
                'transaction_date': date_val,
                'invoice_amount': inv_amt,
                'payment_amount': pay_amt,
                'payment_type': pay_type if pay_type else None,
                'bank_account': bank_acc if bank_acc else None,
                'remark': remark if remark else None
            }
            
            sig = make_tx_signature(tx_data)
            
            if sig in existing_tx_signatures:
                print(f" [Skip] Exact duplicate transaction found for Invoice: {inv_no}")
                dups_skipped += 1
            else:
                if not args.dry_run:
                    supabase.table("transactions").insert(tx_data).execute()
                print(f" [Transaction] Inserted: [{inv_no}] | Date: {date_val} | Cust: {customer} | Inv: ${inv_amt} | Pay: ${pay_amt}")
                existing_tx_signatures.add(sig)
                tx_inserted += 1
                
        except Exception as e:
            print(f" [Error] Failed processing row {index + 2}: {e}")
            errors += 1

    print("\n--- IMPORTS COMPLETED ---")
    if args.dry_run:
        print("*** DRY RUN SUMMARY (Nothing was saved) ***")
    else:
        print("*** REAL RUN SUMMARY ***")
    print(f"Total Rows Read:        {total_read}")
    print(f"Customers Inserted:     {customers_inserted}")
    print(f"Salespersons Inserted:  {salespersons_inserted}")
    print(f"Transactions Inserted:  {tx_inserted}")
    print(f"Duplicates Skipped:     {dups_skipped}")
    print(f"Row Errors:             {errors}")

if __name__ == "__main__":
    main()
