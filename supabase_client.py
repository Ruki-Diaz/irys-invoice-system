import os
from supabase import create_client, Client
from collections import defaultdict

url: str = os.getenv("SUPABASE_URL", "https://rgvttnndvhlzhwtluqzc.supabase.co")
key: str = os.getenv("SUPABASE_KEY", "sb_publishable_Iq6o25Xrk3wVmiD7gRSFxg_M2W7cSnv")

# Initialize the Supabase client
supabase: Client = create_client(url, key)

def add_transaction(data):
    """Insert a new transaction into Supabase."""
    response = supabase.table("transactions").insert(data).execute()
    return response

def get_transactions(filters=None):
    """Fetch transactions, applying optional filters."""
    query = supabase.table("transactions").select("*")
    
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
    return response.data

def get_transaction_by_id(tx_id):
    response = supabase.table("transactions").select("*").eq("id", tx_id).execute()
    if response.data:
        return response.data[0]
    return None

def get_transactions_by_invoice(invoice_no):
    response = supabase.table("transactions").select("*").eq("invoice_no", invoice_no).execute()
    return response.data

def delete_transaction(tx_id):
    supabase.table("transactions").delete().eq("id", tx_id).execute()

def update_transaction(tx_id, data):
    supabase.table("transactions").update(data).eq("id", tx_id).execute()

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
