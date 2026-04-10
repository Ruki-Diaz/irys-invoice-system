import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client, Client, ClientOptions
from collections import defaultdict
from flask import session

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_ANON_KEY")

if not url or not key:
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in the environment.")

def get_supabase() -> Client:
    access_token = session.get('supabase_token')
    if access_token:
        options = ClientOptions(headers={'Authorization': f'Bearer {access_token}'})
        return create_client(url, key, options=options)
    return create_client(url, key)

def add_transaction(data):
    """Insert a new transaction into Supabase."""
    return get_supabase().table("transactions").insert(data).execute()

def get_transactions(filters=None):
    """Fetch transactions, applying optional filters."""
    import logging
    try:
        query = get_supabase().table("transactions").select("*")
        
        if filters:
            if filters.get('customer'):
                query = query.ilike('customer', f"%{filters['customer']}%")
            if filters.get('invoice_no'):
                query = query.ilike('invoice_no', f"%{filters['invoice_no']}%")
            if filters.get('start_date'):
                query = query.gte('transaction_date', filters['start_date'])
            if filters.get('end_date'):
                query = query.lte('transaction_date', filters['end_date'])
            if filters.get('salesperson'):
                 query = query.eq('salesperson', filters['salesperson'])
                
        response = query.order('transaction_date', desc=True).execute()
        return response.data if response and hasattr(response, 'data') and response.data else []
    except Exception as e:
        logging.error(f"Error fetching transactions: {e}")
        return []

def get_transaction_by_id(tx_id):
    import logging
    try:
        response = get_supabase().table("transactions").select("*").eq("id", tx_id).execute()
        if response and hasattr(response, 'data') and response.data:
            return response.data[0]
        return None
    except Exception as e:
        logging.error(f"Error fetching transaction by ID {tx_id}: {e}")
        return None

def get_transactions_by_invoice(invoice_no):
    import logging
    try:
        response = get_supabase().table("transactions").select("*").eq("invoice_no", invoice_no).execute()
        return response.data if response and hasattr(response, 'data') and response.data else []
    except Exception as e:
        logging.error(f"Error fetching transactions by invoice {invoice_no}: {e}")
        return []

def delete_transaction(tx_id):
    get_supabase().table("transactions").delete().eq("id", tx_id).execute()

def update_transaction(tx_id, data):
    get_supabase().table("transactions").update(data).eq("id", tx_id).execute()

def get_invoice_totals(transactions=None):
    """Group transactions by invoice_number and calculate totals/status."""
    if transactions is None:
        transactions = get_transactions()
        
    invoice_totals = defaultdict(lambda: {
        'invoiced': 0.0, 
        'paid': 0.0, 
        'balance': 0.0,
        'customer': '', 
        'salesperson': '',
        'status': 'Pending', 
        'transactions': []
    })
    
    for t in transactions:
        inv = t['invoice_no']
        # accumulate totals
        invoice_totals[inv]['invoiced'] += float(t.get('invoice_amount') or 0.0)
        invoice_totals[inv]['paid'] += float(t.get('payment_amount') or 0.0)
        # Use first seen customer and salesperson for metadata
        if not invoice_totals[inv]['customer']:
            invoice_totals[inv]['customer'] = t.get('customer', '')
            invoice_totals[inv]['salesperson'] = t.get('salesperson', '')
            
        invoice_totals[inv]['transactions'].append(t)
        
    # Calculate statuses and balances
    for inv, totals in invoice_totals.items():
        totals['balance'] = totals['invoiced'] - totals['paid']
        
        if totals['paid'] >= totals['invoiced'] and totals['invoiced'] > 0:
            totals['status'] = 'Paid'
        elif totals['paid'] > 0 and totals['paid'] < totals['invoiced']:
            totals['status'] = 'Partial'
            
    return dict(invoice_totals)

def get_outstanding_by_customer(transactions=None):
    """Group aggregated invoices by customer."""
    invoice_totals = get_invoice_totals(transactions)
    
    customer_totals = defaultdict(lambda: {
        'tot_inv': 0.0,
        'tot_pay': 0.0,
        'balance': 0.0
    })
    
    for inv, totals in invoice_totals.items():
        cust = totals['customer']
        if cust:
            customer_totals[cust]['tot_inv'] += totals['invoiced']
            customer_totals[cust]['tot_pay'] += totals['paid']
            customer_totals[cust]['balance'] += totals['balance']
            
    # filter positive balances
    outstanding = {k: v for k, v in customer_totals.items() if v['balance'] > 0}
    return outstanding


# --- Customers ---
def get_customers():
    import logging
    try:
        response = get_supabase().table("customers").select("*").order("name").execute()
        return response.data if response and hasattr(response, 'data') and response.data else []
    except Exception as e:
        logging.error(f"Error fetching customers: {e}")
        return []

def get_customer_by_id(cust_id):
    import logging
    try:
        response = get_supabase().table("customers").select("*").eq("id", cust_id).execute()
        if response and hasattr(response, 'data') and response.data:
            return response.data[0]
        return None
    except Exception as e:
        logging.error(f"Error fetching customer by ID {cust_id}: {e}")
        return None

def update_customer(cust_id, name):
    try:
        get_supabase().table("customers").update({"name": name}).eq("id", cust_id).execute()
    except Exception as e:
        import logging
        logging.error(f"Error updating customer {cust_id}: {e}")

def delete_customer(cust_id):
    try:
        get_supabase().table("customers").delete().eq("id", cust_id).execute()
    except Exception as e:
        import logging
        logging.error(f"Error deleting customer {cust_id}: {e}")

def ensure_customer(name):
    if not name:
        return None
    name = name.strip()
    import logging
    try:
        existing = get_supabase().table("customers").select("*").ilike("name", name).execute()
        if existing and hasattr(existing, 'data') and existing.data:
            pass
        else:
            get_supabase().table("customers").insert({"name": name}).execute()
    except Exception as e:
        logging.error(f"Error ensuring customer {name}: {e}")
    return name


# --- Salespersons ---
def get_salespersons():
    import logging
    try:
        response = get_supabase().table("salespersons").select("*").order("name").execute()
        return response.data if response and hasattr(response, 'data') and response.data else []
    except Exception as e:
        logging.error(f"Error fetching salespersons: {e}")
        return []

def get_salesperson_by_id(sp_id):
    import logging
    try:
        response = get_supabase().table("salespersons").select("*").eq("id", sp_id).execute()
        if response and hasattr(response, 'data') and response.data:
            return response.data[0]
        return None
    except Exception as e:
        logging.error(f"Error fetching salesperson by ID {sp_id}: {e}")
        return None

def update_salesperson(sp_id, name):
    try:
        get_supabase().table("salespersons").update({"name": name}).eq("id", sp_id).execute()
    except Exception as e:
        import logging
        logging.error(f"Error updating salesperson {sp_id}: {e}")

def delete_salesperson(sp_id):
    try:
        get_supabase().table("salespersons").delete().eq("id", sp_id).execute()
    except Exception as e:
        import logging
        logging.error(f"Error deleting salesperson {sp_id}: {e}")

def ensure_salesperson(name):
    if not name:
        return None
    name = name.strip()
    import logging
    try:
        existing = get_supabase().table("salespersons").select("*").ilike("name", name).execute()
        if existing and hasattr(existing, 'data') and existing.data:
            pass
        else:
            get_supabase().table("salespersons").insert({"name": name}).execute()
    except Exception as e:
        logging.error(f"Error ensuring salesperson {name}: {e}")
    return name

