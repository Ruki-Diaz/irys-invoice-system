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
    key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_ANON_KEY must be set in your .env file or environment.")
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

    stats = {
        "read": 0,
        "customers_inserted": 0,
        "salespersons_inserted": 0,
        "transactions_inserted": 0,
        "skipped_true_blank": 0,
        "skipped_summary_total": 0,
        "skipped_duplicates": 0,
        "inserted_blank_invoice": 0,
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

    last_valid_date = None

    for index, row in df.iterrows():
        stats["read"] += 1
        excel_row_num = index + 2
        try:
            invoice_no = clean_string(row.get('Invoice Number'))
            customer = clean_string(row.get('Customer'))
            salesperson = clean_string(row.get('Salesperson'))
            invoice_amount = clean_numeric(row.get('Invoice Amount'))
            payment_amount = clean_numeric(row.get('Payment Amount'))
            payment_type = clean_string(row.get('Payment Type')) or None
            bank_account = clean_string(row.get('Bank Account')) or None
            remark = clean_string(row.get('Remark')) or None
            parsed_date = clean_date(row.get('Date'))
            
            # Stop condition 1: completely blank rows (true blanks)
            is_completely_empty = not any([
                invoice_no, customer, salesperson,
                invoice_amount != 0.0, payment_amount != 0.0,
                payment_type, bank_account, remark, parsed_date
            ])
            
            if is_completely_empty:
                stats["skipped_true_blank"] += 1
                # print(f"Skipped row {excel_row_num}: true blank row") # kept silent to reduce noise
                continue
                
            # Stop condition 2: Summary/Total rows
            if "total" in invoice_no.lower() or "total" in customer.lower():
                stats["skipped_summary_total"] += 1
                print(f"Skipped row {excel_row_num}: summary row (detected 'Total')")
                continue

            # Fallback date logic
            is_recovered_date = False
            if parsed_date:
                last_valid_date = parsed_date
                final_date = parsed_date
            else:
                final_date = last_valid_date
                is_recovered_date = True

            if not final_date:
                stats["errors"] += 1
                print(f"ERROR on Excel row {excel_row_num}: Missing transaction date (and no previous date to fallback to).")
                continue

            # Tracking handles
            handling_notes = []
            if not invoice_no: 
                handling_notes.append("blank invoice number")
                stats["inserted_blank_invoice"] += 1
            if not customer: handling_notes.append("blank customer")
            if not salesperson: handling_notes.append("blank salesperson")
            if is_recovered_date: handling_notes.append(f"filled blank date with {final_date}")
            
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
                "transaction_date": final_date,
                "invoice_amount": invoice_amount,
                "payment_amount": payment_amount,
                "payment_type": payment_type,
                "bank_account": bank_account,
                "remark": remark
            }

            # Pre-flight duplicate check
            if is_exact_duplicate(tx_data):
                stats["skipped_duplicates"] += 1
                # print(f"Skipped row {excel_row_num}: exact duplicate")
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
            note_str = f" [{', '.join(handling_notes)}]" if handling_notes else ""
            print(f"{prefix}Inserted valid row {excel_row_num}: Invoice '{invoice_no}' | Customer '{customer[:15]}' | AED {tx_data['payment_amount']}{note_str}")

        except Exception as e:
            stats["errors"] += 1
            print(f"ERROR on Excel row {excel_row_num}: {e}")

    # Final summary display
    print("\n" + "="*40)
    print("IMPORT SUMMARY")
    print("="*40)
    print(f"Total rows read:           {stats['read']}")
    print(f"Customers inserted:        {stats['customers_inserted']}")
    print(f"Salespersons inserted:     {stats['salespersons_inserted']}")
    print(f"Transactions inserted:     {stats['transactions_inserted']}")
    print(f"  (Included blank inv):    {stats['inserted_blank_invoice']}")
    print(f"Skipped (True Blank):      {stats['skipped_true_blank']}")
    print(f"Skipped (Summary/Total):   {stats['skipped_summary_total']}")
    print(f"Skipped (Exact Duplicates):{stats['skipped_duplicates']}")
    print(f"Row errors:                {stats['errors']}")
    print("="*40)
    print(f"Total valid tx accounted:  {stats['transactions_inserted'] + stats['skipped_duplicates']}")
    
    if args.dry_run:
         print("This was a DRY RUN. No data was actually written to Supabase.")

if __name__ == "__main__":
    main()
