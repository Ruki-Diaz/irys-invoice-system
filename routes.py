from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, session
from models import db, Customer, Salesperson, PaymentType, BankAccount
import supabase_client as sc
from sqlalchemy import func
import pandas as pd
import io
from fpdf import FPDF
from datetime import datetime
import traceback
import logging
from functools import wraps

routes_bp = Blueprint('routes', __name__)

def is_authenticated():
    return session.get('supabase_token') is not None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('routes.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            flash('You do not have permission to access that page.', 'danger')
            return redirect(url_for('routes.login'))
        return f(*args, **kwargs)
    return decorated_function

@routes_bp.route('/login', methods=['GET', 'POST'])
def login():
    if is_authenticated():
        return redirect(url_for('routes.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            auth_response = sc.get_supabase().auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            if auth_response.user and auth_response.session:
                session['supabase_token'] = auth_response.session.access_token
                session['user_id'] = auth_response.user.id
                return redirect(url_for('routes.dashboard'))
            else:
                flash('Invalid credentials.', 'danger')
        except Exception as e:
            logging.error(f"Login error: {e}")
            flash('Invalid email or password', 'danger')
            
    return render_template('login.html')

@routes_bp.route('/logout')
@login_required
def logout():
    try:
        sc.get_supabase().auth.sign_out()
    except Exception as e:
        logging.error(f"Sign out error: {e}")
    session.pop('supabase_token', None)
    session.pop('user_id', None)
    return redirect(url_for('routes.login'))

@routes_bp.route('/')
@routes_bp.route('/dashboard')
@login_required
def dashboard():
    # Calculate summary metrics from Supabase
    all_tx = sc.get_transactions()
    total_tx = len(all_tx)
    total_invoice = sum(float(t.get('invoice_amount') or 0.0) for t in all_tx)
    total_payment = sum(float(t.get('payment_amount') or 0.0) for t in all_tx)
    total_outstanding = total_invoice - total_payment
    
    return render_template('dashboard.html', 
                           total_tx=total_tx, 
                           total_invoice=total_invoice, 
                           total_payment=total_payment, 
                           total_outstanding=total_outstanding)

@routes_bp.route('/transactions/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    customers = sc.get_customers()
    salespersons = sc.get_salespersons()
    payment_types = PaymentType.query.order_by(PaymentType.type_name).all()
    bank_accounts = BankAccount.query.order_by(BankAccount.account_name).all()
    
    if request.method == 'POST':
        try:
            date_str = request.form.get('date')
            tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            invoice_amount = float(request.form.get('invoice_amount') or 0.0)
            payment_amount = float(request.form.get('payment_amount') or 0.0)
            
            if invoice_amount < 0 or payment_amount < 0:
                flash('Amounts cannot be negative.', 'danger')
                return redirect(request.url)
            
            # Check for existing invoice
            invoice_number = request.form.get('invoice_number').strip()
            
            # Master data IDs vs Names mapping
            # (We will store strings in Supabase so filters don't require JOIN logic later)
            # Master data names
            cust_name = request.form.get('customer_name')
            if cust_name == '___OTHER___':
                cust_name = request.form.get('new_customer_name')
                
            sp_name = request.form.get('salesperson_name')
            if sp_name == '___OTHER___':
                sp_name = request.form.get('new_salesperson_name')
            
            final_cust_name = sc.ensure_customer(cust_name)
            final_sp_name = sc.ensure_salesperson(sp_name)
            pt = PaymentType.query.get(request.form.get('payment_type_id')) if request.form.get('payment_type_id') else None
            ba = BankAccount.query.get(request.form.get('bank_account_id')) if request.form.get('bank_account_id') else None

            # Aggregate existing payments for this invoice
            existing_txs = sc.get_transactions_by_invoice(invoice_number)
            
            if existing_txs:
                # It's a follow-up payment
                original_tx = existing_txs[0]
                
                # Validation: ensure customer matches
                if original_tx.get('customer') != final_cust_name:
                    flash(f'Invoice {invoice_number} belongs to a different customer ({original_tx.get("customer")}).', 'danger')
                    return redirect(request.url)
                    
                # Calculate total outstanding
                total_invoiced = sum(float(t.get('invoice_amount') or 0) for t in existing_txs)
                total_paid = sum(float(t.get('payment_amount') or 0) for t in existing_txs)
                remaining = total_invoiced - total_paid
                
                if payment_amount > remaining:
                    flash(f'Overpayment detected. Remaining balance for invoice {invoice_number} is only AED {remaining:.2f}.', 'warning')
                    return redirect(request.url)
                    
                # Force invoice amount to 0 for follow-up payments
                invoice_amount = 0.0
                flash(f'Added follow-up payment for Invoice {invoice_number}.', 'info')
            
            remark_type = request.form.get('remark_type')
            if remark_type == 'Invoice':
                final_remark = 'Invoice'
            elif remark_type == 'Payment':
                final_remark = 'Payment'
            else:
                custom_val = request.form.get('remark_custom')
                final_remark = custom_val.strip() if custom_val else ''

            tx_data = {
                'customer': final_cust_name,
                'salesperson': final_sp_name,
                'invoice_no': invoice_number,
                'transaction_date': date_str,
                'invoice_amount': invoice_amount,
                'payment_amount': payment_amount,
                'payment_type': pt.type_name if pt else None,
                'bank_account': ba.account_name if ba else None,
                'remark': final_remark
            }
            
            sc.add_transaction(tx_data)
            flash('Transaction added successfully.', 'success')
            return redirect(url_for('routes.view_transactions'))
        except Exception as e:
            flash(f'Error adding transaction: {str(e)}', 'danger')
            
    return render_template('add_transaction.html', 
                           customers=customers, 
                           salespersons=salespersons, 
                           payment_types=payment_types, 
                           bank_accounts=bank_accounts)

@routes_bp.route('/api/invoice_details/<path:invoice_number>', methods=['GET'])
@login_required
def invoice_details(invoice_number):
    txs = sc.get_transactions_by_invoice(invoice_number)
    if not txs:
        return {'exists': False}
    
    original_tx = txs[0]
    total_invoiced = sum(float(t.get('invoice_amount') or 0.0) for t in txs)
    total_paid = sum(float(t.get('payment_amount') or 0.0) for t in txs)
    
    # Return customer string name for UI auto-fill
    return {
        'exists': True,
        'customer': original_tx.get('customer'),
        'total_invoiced': total_invoiced,
        'total_paid': total_paid,
        'remaining_balance': total_invoiced - total_paid
    }

@routes_bp.route('/transactions', methods=['GET'])
@login_required
def view_transactions():
    # Search / Filters
    filters = {}
    search_cust = request.args.get('customer_name', '')
    search_inv = request.args.get('invoice_number', '')
    filter_start = request.args.get('start_date', '')
    filter_end = request.args.get('end_date', '')
    filter_sp = request.args.get('salesperson_name', '')
    
    if search_cust:
        filters['customer'] = search_cust
    if search_inv:
        filters['invoice_no'] = search_inv
    if filter_start:
        filters['start_date'] = filter_start
    if filter_end:
        filters['end_date'] = filter_end
    if filter_sp:
        filters['salesperson'] = filter_sp
            
    # Retrieve matching transactions
    transactions = sc.get_transactions(filters)
    # Calculate grouped invoice totals
    invoice_totals = sc.get_invoice_totals(transactions)
    
    # Apply status filter
    filter_status = request.args.get('status', 'all')
    if filter_status == 'paid':
        invoice_totals = {k: v for k, v in invoice_totals.items() if v['status'] == 'Paid'}
    elif filter_status == 'pending':
        invoice_totals = {k: v for k, v in invoice_totals.items() if v['status'] != 'Paid'}
    salespersons = sc.get_salespersons()
    payment_types = PaymentType.query.order_by(PaymentType.type_name).all()
    
    return render_template('view_transactions.html', 
                           salespersons=salespersons,
                           payment_types=payment_types,
                           invoice_totals=invoice_totals)

@routes_bp.route('/transactions/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_transaction(id):
    logging.info(f"Accessing edit_transaction for ID: {id}")
    try:
        tx = sc.get_transaction_by_id(id)
        if not tx:
            flash('Transaction not found.', 'danger')
            return redirect(url_for('routes.view_transactions'))
    except Exception as e:
        logging.error(f"Error fetching transaction {id}: {e}\n{traceback.format_exc()}")
        flash('An error occurred while fetching the transaction.', 'danger')
        return redirect(url_for('routes.view_transactions'))
        
    customers = sc.get_customers()
    salespersons = sc.get_salespersons()
    payment_types = PaymentType.query.order_by(PaymentType.type_name).all()
    bank_accounts = BankAccount.query.order_by(BankAccount.account_name).all()
    
    if request.method == 'POST':
        try:
            date_str = request.form.get('date')
            invoice_amount_str = request.form.get('invoice_amount')
            payment_amount_str = request.form.get('payment_amount')
            
            invoice_amount = float(invoice_amount_str) if invoice_amount_str else 0.0
            payment_amount = float(payment_amount_str) if payment_amount_str else 0.0
            
            if invoice_amount < 0 or payment_amount < 0:
                flash('Amounts cannot be negative.', 'danger')
                return redirect(request.url)
            
            new_invoice_number = request.form.get('invoice_number')
            cust_name = request.form.get('customer_name')
            if cust_name == '___OTHER___':
                cust_name = request.form.get('new_customer_name')
                
            sp_name = request.form.get('salesperson_name')
            if sp_name == '___OTHER___':
                sp_name = request.form.get('new_salesperson_name')
            
            payment_type_id = request.form.get('payment_type_id')
            bank_account_id = request.form.get('bank_account_id')
            
            if not new_invoice_number:
                flash('Invoice number is required.', 'danger')
                return redirect(request.url)
            
            if new_invoice_number != tx.get('invoice_no'):
                existing_txs = sc.get_transactions_by_invoice(new_invoice_number)
                if existing_txs:
                    original_tx = existing_txs[0]
                    if original_tx.get('customer') != sc.ensure_customer(cust_name):
                        flash(f'Cannot change to invoice {new_invoice_number}. It belongs to a different customer ({original_tx.get("customer")}).', 'danger')
                        return redirect(request.url)
            
            final_cust_name = sc.ensure_customer(cust_name)
            final_sp_name = sc.ensure_salesperson(sp_name)
            pt = PaymentType.query.get(payment_type_id) if payment_type_id else None
            ba = BankAccount.query.get(bank_account_id) if bank_account_id else None

            remark_type = request.form.get('remark_type')
            if remark_type == 'Invoice':
                final_remark = 'Invoice'
            elif remark_type == 'Payment':
                final_remark = 'Payment'
            else:
                custom_val = request.form.get('remark_custom')
                final_remark = custom_val.strip() if custom_val else ''

            update_data = {
                'invoice_no': new_invoice_number,
                'customer': final_cust_name,
                'salesperson': final_sp_name,
                'transaction_date': date_str,
                'invoice_amount': invoice_amount,
                'payment_amount': payment_amount,
                'payment_type': pt.type_name if pt else None,
                'bank_account': ba.account_name if ba else None,
                'remark': final_remark
            }
            
            logging.info(f"Updating transaction {id} with payload: {update_data}")
            sc.update_transaction(id, update_data)
            flash('Transaction updated successfully.', 'success')
            return redirect(url_for('routes.view_transactions'))
        except Exception as e:
            logging.error(f"Error updating transaction {id}: {e}\n{traceback.format_exc()}")
            flash(f'Error updating transaction: {str(e)}', 'danger')

    # Safe normalization for GET
    safe_tx = {
        'id': tx.get('id'),
        'invoice_no': tx.get('invoice_no') or '',
        'transaction_date': tx.get('transaction_date') or '',
        'customer': tx.get('customer') or '',
        'salesperson': tx.get('salesperson') or '',
        'invoice_amount': float(tx.get('invoice_amount') or 0.0),
        'payment_amount': float(tx.get('payment_amount') or 0.0),
        'payment_type': tx.get('payment_type') or '',
        'bank_account': tx.get('bank_account') or '',
        'remark': tx.get('remark') or ''
    }
    
    if safe_tx['transaction_date']:
        try:
            dt = datetime.strptime(safe_tx['transaction_date'].split('T')[0], '%Y-%m-%d')
            safe_tx['transaction_date'] = dt.strftime('%Y-%m-%d')
        except ValueError:
            pass

    return render_template('edit_transaction.html', 
                           tx=safe_tx, 
                           customers=customers, 
                           salespersons=salespersons, 
                           payment_types=payment_types, 
                           bank_accounts=bank_accounts)

@routes_bp.route('/transactions/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_transaction(id):
    try:
        sc.delete_transaction(id)
        flash('Transaction deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting transaction: {str(e)}', 'danger')
    return redirect(url_for('routes.view_transactions'))

@routes_bp.route('/reports', methods=['GET'])
@login_required
def reports():
    customers = sc.get_customers()
    return render_template('reports.html', customers=customers)

@routes_bp.route('/export/excel')
@login_required
def export_excel():
    # Apply identical Search / Filters
    filters = {}
    search_cust = request.args.get('customer_name', '')
    search_inv = request.args.get('invoice_number', '')
    filter_start = request.args.get('start_date', '')
    filter_end = request.args.get('end_date', '')
    filter_sp = request.args.get('salesperson_name', '')
    
    if search_cust:
        filters['customer'] = search_cust
    if search_inv:
        filters['invoice_no'] = search_inv
    if filter_start:
        filters['start_date'] = filter_start
    if filter_end:
        filters['end_date'] = filter_end
    if filter_sp:
        filters['salesperson'] = filter_sp
            
    transactions = sc.get_transactions(filters)
    
    data = []
    total_invoice = 0
    total_payment = 0
    
    for tx in transactions:
        inv_amt = float(tx.get('invoice_amount') or 0.0)
        pay_amt = float(tx.get('payment_amount') or 0.0)
        total_invoice += inv_amt
        total_payment += pay_amt
        data.append({
            'Date': tx.get('transaction_date'),
            'Invoice Number': tx.get('invoice_no'),
            'Customer': tx.get('customer'),
            'Salesperson': tx.get('salesperson'),
            'Invoice Amount': inv_amt,
            'Payment Amount': pay_amt,
            'Outstanding': inv_amt - pay_amt,
            'Payment Type': tx.get('payment_type') or '',
            'Bank Account': tx.get('bank_account') or '',
            'Remark': tx.get('remark') or ''
        })
        
    df_trans = pd.DataFrame(data)
    
    # Summary Data
    summary_data = [{
        'Total Transactions': len(transactions),
        'Total Invoiced': total_invoice,
        'Total Paid': total_payment,
        'Total Outstanding': total_invoice - total_payment
    }]
    df_summary = pd.DataFrame(summary_data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_trans.to_excel(writer, index=False, sheet_name='Transactions')
        df_summary.to_excel(writer, index=False, sheet_name='Summary')
    
    output.seek(0)
    return send_file(output, download_name='transactions.xlsx', as_attachment=True)

class PDFReport(FPDF):
    def header(self):
        # Company/System Branding
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(0, 51, 102) # Dark blue
        self.cell(0, 10, 'Irys Invoice Management System', 0, 1, 'L')
        self.set_font('Helvetica', 'I', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'Finance Dashboard Reports', 0, 1, 'L')
        
        # Draw a line
        self.set_draw_color(0, 51, 102)
        self.set_line_width(0.5)
        self.line(10, 26, 200, 26)
        self.ln(10)
        self.set_text_color(0, 0, 0) # Reset
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()} - Generated on {datetime.now().strftime("%Y-%m-%d")}', 0, 0, 'C')

@routes_bp.route('/export/pdf/customer_statement/<path:customer_name>')
@login_required
def pdf_customer_statement(customer_name):
    transactions = sc.get_transactions({'customer': customer_name})
    transactions.sort(key=lambda x: x['transaction_date']) # sort asc
    
    total_inv = sum(float(tx.get('invoice_amount') or 0) for tx in transactions)
    total_pay = sum(float(tx.get('payment_amount') or 0) for tx in transactions)
    balance = total_inv - total_pay
    
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, f'Customer Statement: {customer_name}', 0, 1)
    
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, f'Total Invoiced: AED {total_inv:.2f}', 0, 1)
    pdf.cell(0, 8, f'Total Paid: AED {total_pay:.2f}', 0, 1)
    pdf.cell(0, 8, f'Outstanding Balance: AED {balance:.2f}', 0, 1)
    pdf.cell(0, 8, f'Total Transactions: {len(transactions)}', 0, 1)
    pdf.ln(5)
    
    # Table Header
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(30, 8, 'Date', 1, 0, 'C', fill=True)
    pdf.cell(35, 8, 'Invoice No', 1, 0, 'C', fill=True)
    pdf.cell(35, 8, 'Inv Amount', 1, 0, 'R', fill=True)
    pdf.cell(35, 8, 'Pay Amount', 1, 0, 'R', fill=True)
    pdf.cell(55, 8, 'Remark', 1, 1, 'L', fill=True)
    
    # Table Body
    pdf.set_font('Helvetica', '', 9)
    for tx in transactions:
        pdf.cell(30, 8, tx.get('transaction_date'), 1, 0, 'C')
        pdf.cell(35, 8, tx.get('invoice_no'), 1, 0, 'C')
        inv_amt = float(tx.get('invoice_amount') or 0)
        pay_amt = float(tx.get('payment_amount') or 0)
        pdf.cell(35, 8, f'AED {inv_amt:.2f}', 1, 0, 'R')
        pdf.cell(35, 8, f'AED {pay_amt:.2f}', 1, 0, 'R')
        # truncate remark
        remark_text = tx.get('remark') or ''
        remark = (remark_text[:30] + '..') if len(remark_text) > 30 else remark_text
        pdf.cell(55, 8, remark, 1, 1, 'L')
        
    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    return send_file(output, download_name=f'statement_{customer_name.replace(" ", "_")}.pdf', mimetype='application/pdf', as_attachment=True)

@routes_bp.route('/export/pdf/outstanding')
@login_required
def pdf_outstanding():
    # aggregate by customer using Supabase
    outstanding_data = sc.get_outstanding_by_customer()
    
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Outstanding Payments Report', 0, 1)
    pdf.ln(5)
    
    # Table Header
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(75, 8, 'Customer', 1, 0, 'L', fill=True)
    pdf.cell(40, 8, 'Total Invoiced', 1, 0, 'R', fill=True)
    pdf.cell(40, 8, 'Total Paid', 1, 0, 'R', fill=True)
    pdf.cell(35, 8, 'Balance', 1, 1, 'R', fill=True)
    
    # Table Body
    pdf.set_font('Helvetica', '', 10)
    total_balance = 0
    for cust_name, data in outstanding_data.items():
        inv = data['tot_inv']
        pay = data['tot_pay']
        bal = data['balance']
        total_balance += bal
        
        pdf.cell(75, 8, cust_name, 1, 0, 'L')
        pdf.cell(40, 8, f'AED {inv:.2f}', 1, 0, 'R')
        pdf.cell(40, 8, f'AED {pay:.2f}', 1, 0, 'R')
        pdf.cell(35, 8, f'AED {bal:.2f}', 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, f'Total System Outstanding: AED {total_balance:.2f}', 0, 1, 'R')
    
    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    return send_file(output, download_name='outstanding_payments.pdf', mimetype='application/pdf', as_attachment=True)

@routes_bp.route('/export/pdf/summary')
@login_required
def pdf_summary():
    all_tx = sc.get_transactions()
    total_tx = len(all_tx)
    total_inv = sum(float(t.get('invoice_amount') or 0.0) for t in all_tx)
    total_pay = sum(float(t.get('payment_amount') or 0.0) for t in all_tx)
    balance = total_inv - total_pay
    
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'System Summary Report', 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 10, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
    pdf.ln(5)
    
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(90, 10, 'Metric', 1, 0, 'L', fill=True)
    pdf.cell(90, 10, 'Value', 1, 1, 'R', fill=True)
    
    pdf.set_font('Helvetica', '', 12)
    metrics = [
        ('Total Transactions', str(total_tx)),
        ('Total Invoiced Amount', f'AED {total_inv:.2f}'),
        ('Total Payment Amount', f'AED {total_pay:.2f}'),
        ('Total Outstanding Balance', f'AED {balance:.2f}')
    ]
    
    for k, v in metrics:
        pdf.cell(90, 10, k, 1, 0, 'L')
        pdf.cell(90, 10, v, 1, 1, 'R')
        
    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    return send_file(output, download_name='summary_report.pdf', mimetype='application/pdf', as_attachment=True)


@routes_bp.route('/export/outstanding', methods=['GET'])
@login_required
def export_outstanding():
    mode = request.args.get('mode', 'all')
    customer_name = request.args.get('customer_name')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    export_format = request.args.get('format', 'pdf')

    filters = {}
    if start_date: filters['start_date'] = start_date
    if end_date: filters['end_date'] = end_date
    
    if mode == 'single' and customer_name:
        filters['customer'] = customer_name

    transactions = sc.get_transactions(filters)
    outstanding_data = sc.get_outstanding_by_customer(transactions)

    if not outstanding_data:
        flash('No outstanding balances found for the selected criteria.', 'warning')
        return redirect(url_for('routes.reports'))

    if export_format == 'pdf':
        pdf = PDFReport()
        pdf.add_page()
        
        if mode == 'single' and customer_name:
            if not outstanding_data:
                cust_name = customer_name
                bal = 0
            else:
                cust_name = list(outstanding_data.keys())[0]
            data = outstanding_data[cust_name]
            bal = data['balance']
            pdf.set_font('Helvetica', 'B', 14)
            pdf.cell(0, 10, f'Outstanding Statement: {cust_name}', 0, 1)
            pdf.set_font('Helvetica', '', 11)
            date_str = f"From: {start_date or 'Start'} To: {end_date or 'Today'}"
            pdf.cell(0, 8, date_str, 0, 1)
            pdf.cell(0, 8, f'Total Invoiced: AED {data["tot_inv"]:.2f}', 0, 1)
            pdf.cell(0, 8, f'Total Paid: AED {data["tot_pay"]:.2f}', 0, 1)
            pdf.cell(0, 8, f'Outstanding Balance: AED {bal:.2f}', 0, 1)
            pdf.ln(5)
            
            transactions.sort(key=lambda x: x['transaction_date'])
            
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(30, 8, 'Date', 1, 0, 'C', fill=True)
            pdf.cell(35, 8, 'Invoice No', 1, 0, 'C', fill=True)
            pdf.cell(35, 8, 'Inv Amount', 1, 0, 'R', fill=True)
            pdf.cell(35, 8, 'Pay Amount', 1, 0, 'R', fill=True)
            pdf.cell(55, 8, 'Remark', 1, 1, 'L', fill=True)
            
            pdf.set_font('Helvetica', '', 9)
            for tx in transactions:
                pdf.cell(30, 8, tx.get('transaction_date'), 1, 0, 'C')
                pdf.cell(35, 8, tx.get('invoice_no'), 1, 0, 'C')
                inv_amt = float(tx.get('invoice_amount') or 0)
                pay_amt = float(tx.get('payment_amount') or 0)
                pdf.cell(35, 8, f'AED {inv_amt:.2f}', 1, 0, 'R')
                pdf.cell(35, 8, f'AED {pay_amt:.2f}', 1, 0, 'R')
                remark_text = tx.get('remark') or ''
                remark = (remark_text[:30] + '..') if len(remark_text) > 30 else remark_text
                pdf.cell(55, 8, remark, 1, 1, 'L')
        else:
            pdf.set_font('Helvetica', 'B', 14)
            pdf.cell(0, 10, 'Outstanding Payments Report', 0, 1)
            pdf.set_font('Helvetica', '', 10)
            date_str = f"From: {start_date or 'All Time'} To: {end_date or 'Present'}"
            pdf.cell(0, 6, f"Period: {date_str}", 0, 1)
            pdf.ln(5)
            
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(75, 8, 'Customer', 1, 0, 'L', fill=True)
            pdf.cell(40, 8, 'Total Invoiced', 1, 0, 'R', fill=True)
            pdf.cell(40, 8, 'Total Paid', 1, 0, 'R', fill=True)
            pdf.cell(35, 8, 'Balance', 1, 1, 'R', fill=True)
            
            pdf.set_font('Helvetica', '', 10)
            total_balance = 0
            for cust_name, data in outstanding_data.items():
                inv = data['tot_inv']
                pay = data['tot_pay']
                bal = data['balance']
                total_balance += bal
                
                pdf.cell(75, 8, cust_name, 1, 0, 'L')
                pdf.cell(40, 8, f'AED {inv:.2f}', 1, 0, 'R')
                pdf.cell(40, 8, f'AED {pay:.2f}', 1, 0, 'R')
                pdf.cell(35, 8, f'AED {bal:.2f}', 1, 1, 'R')
                
            pdf.ln(5)
            pdf.set_font('Helvetica', 'B', 11)
            pdf.cell(0, 8, f'Total System Outstanding: AED {total_balance:.2f}', 0, 1, 'R')

        output = io.BytesIO()
        pdf.output(output)
        output.seek(0)
        return send_file(output, download_name='outstanding_report.pdf', mimetype='application/pdf', as_attachment=True)

    elif export_format == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if mode == 'single' and customer_name:
                cust_name = list(outstanding_data.keys())[0]
                data = outstanding_data[cust_name]
                summary_data = [{
                    'Customer': cust_name,
                    'Total Invoiced': data['tot_inv'],
                    'Total Paid': data['tot_pay'],
                    'Outstanding Balance': data['balance'],
                    'Period Start': start_date or 'Start',
                    'Period End': end_date or 'Today'
                }]
                pd.DataFrame(summary_data).to_excel(writer, index=False, sheet_name='Summary')
                
                transactions.sort(key=lambda x: x['transaction_date'])
                tx_data = []
                for tx in transactions:
                    inv_amt = float(tx.get('invoice_amount') or 0)
                    pay_amt = float(tx.get('payment_amount') or 0)
                    tx_data.append({
                        'Date': tx.get('transaction_date'),
                        'Invoice Number': tx.get('invoice_no'),
                        'Invoice Amount': inv_amt,
                        'Payment Amount': pay_amt,
                        'Remark': tx.get('remark') or ''
                    })
                pd.DataFrame(tx_data).to_excel(writer, index=False, sheet_name='Transactions')
                
            else:
                all_data = []
                for cust_name, data in outstanding_data.items():
                    all_data.append({
                        'Customer': cust_name,
                        'Total Invoiced': data['tot_inv'],
                        'Total Paid': data['tot_pay'],
                        'Outstanding Balance': data['balance']
                    })
                pd.DataFrame(all_data).to_excel(writer, index=False, sheet_name='Outstanding Balances')

        output.seek(0)
        return send_file(output, download_name='outstanding_report.xlsx', as_attachment=True)

# ==========================================
# PHASE 2: MASTER DATA MANAGEMENT ROUTES
# ==========================================

# --- CUSTOMERS ---
@routes_bp.route('/master/customers')
@login_required
@admin_required
def master_customers():
    customers = sc.get_customers()
    items = [{'id': c.get('id'), 'display_name': c.get('name')} for c in customers]
    return render_template('master_list.html', 
                           title='Manage Customers', 
                           items=items,
                           add_url=url_for('routes.add_customer'),
                           edit_endpoint='routes.edit_customer',
                           delete_endpoint='routes.delete_customer')

@routes_bp.route('/master/customers/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_customer():
    if request.method == 'POST':
        name = request.form.get('name_field').strip()
        existing = sc.supabase.table("customers").select("*").ilike("name", name).execute().data
        if existing:
            flash(f'Customer "{name}" already exists.', 'danger')
        else:
            sc.supabase.table("customers").insert({"name": name}).execute()
            flash('Customer added successfully.', 'success')
            return redirect(url_for('routes.master_customers'))
            
    return render_template('master_form.html', 
                           title='Add Customer', 
                           field_label='Customer Name', 
                           current_value='',
                           submit_url=url_for('routes.add_customer'),
                           back_url=url_for('routes.master_customers'))

@routes_bp.route('/master/customers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_customer(id):
    customer = sc.get_customer_by_id(id)
    if not customer:
        flash('Customer not found.', 'danger')
        return redirect(url_for('routes.master_customers'))
        
    if request.method == 'POST':
        new_name = request.form.get('name_field').strip()
        
        # Edit blocking logic
        if sc.get_transactions({'customer': customer['name']}) and new_name != customer['name']:
            flash(f'Cannot edit Customer "{customer["name"]}" because they are linked to existing transactions.', 'danger')
            return redirect(url_for('routes.master_customers'))
            
        existing = sc.supabase.table("customers").select("*").ilike("name", new_name).neq("id", id).execute().data
        if existing:
            flash(f'Customer "{new_name}" already exists.', 'danger')
        else:
            sc.update_customer(id, new_name)
            flash('Customer updated successfully.', 'success')
            return redirect(url_for('routes.master_customers'))
            
    return render_template('master_form.html', 
                           title='Edit Customer', 
                           field_label='Customer Name', 
                           current_value=customer['name'],
                           submit_url=url_for('routes.edit_customer', id=id),
                           back_url=url_for('routes.master_customers'))

@routes_bp.route('/master/customers/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_customer(id):
    customer = sc.get_customer_by_id(id)
    if not customer:
        flash('Customer not found.', 'danger')
        return redirect(url_for('routes.master_customers'))
        
    if sc.get_transactions({'customer': customer['name']}):
        flash(f'Cannot delete this customer because it is linked to existing transactions.', 'danger')
    else:
        sc.delete_customer(id)
        flash('Customer deleted successfully.', 'success')
    return redirect(url_for('routes.master_customers'))

# --- SALESPERSONS ---
@routes_bp.route('/master/salespersons')
@login_required
@admin_required
def master_salespersons():
    salespersons = sc.get_salespersons()
    items = [{'id': s.get('id'), 'display_name': s.get('name')} for s in salespersons]
    return render_template('master_list.html', 
                           title='Manage Salespersons', 
                           items=items,
                           add_url=url_for('routes.add_salesperson'),
                           edit_endpoint='routes.edit_salesperson',
                           delete_endpoint='routes.delete_salesperson')

@routes_bp.route('/master/salespersons/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_salesperson():
    if request.method == 'POST':
        name = request.form.get('name_field').strip()
        existing = sc.supabase.table("salespersons").select("*").ilike("name", name).execute().data
        if existing:
            flash(f'Salesperson "{name}" already exists.', 'danger')
        else:
            sc.supabase.table("salespersons").insert({"name": name}).execute()
            flash('Salesperson added successfully.', 'success')
            return redirect(url_for('routes.master_salespersons'))
            
    return render_template('master_form.html', 
                           title='Add Salesperson', 
                           field_label='Salesperson Name', 
                           current_value='',
                           submit_url=url_for('routes.add_salesperson'),
                           back_url=url_for('routes.master_salespersons'))

@routes_bp.route('/master/salespersons/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_salesperson(id):
    salesperson = sc.get_salesperson_by_id(id)
    if not salesperson:
        flash('Salesperson not found.', 'danger')
        return redirect(url_for('routes.master_salespersons'))
        
    if request.method == 'POST':
        new_name = request.form.get('name_field').strip()
        
        if sc.get_transactions({'salesperson': salesperson['name']}) and new_name != salesperson['name']:
            flash(f'Cannot edit Salesperson "{salesperson["name"]}" because they are linked to existing transactions.', 'danger')
            return redirect(url_for('routes.master_salespersons'))
            
        existing = sc.supabase.table("salespersons").select("*").ilike("name", new_name).neq("id", id).execute().data
        if existing:
            flash(f'Salesperson "{new_name}" already exists.', 'danger')
        else:
            sc.update_salesperson(id, new_name)
            flash('Salesperson updated successfully.', 'success')
            return redirect(url_for('routes.master_salespersons'))
            
    return render_template('master_form.html', 
                           title='Edit Salesperson', 
                           field_label='Salesperson Name', 
                           current_value=salesperson['name'],
                           submit_url=url_for('routes.edit_salesperson', id=id),
                           back_url=url_for('routes.master_salespersons'))

@routes_bp.route('/master/salespersons/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_salesperson(id):
    salesperson = sc.get_salesperson_by_id(id)
    if not salesperson:
        flash('Salesperson not found.', 'danger')
        return redirect(url_for('routes.master_salespersons'))
        
    if sc.get_transactions({'salesperson': salesperson['name']}):
        flash(f'Cannot delete this salesperson because it is linked to existing transactions.', 'danger')
    else:
        sc.delete_salesperson(id)
        flash('Salesperson deleted successfully.', 'success')
    return redirect(url_for('routes.master_salespersons'))

# --- PAYMENT TYPES ---
@routes_bp.route('/master/payment_types')
@login_required
@admin_required
def master_payment_types():
    payment_types = PaymentType.query.order_by(PaymentType.type_name).all()
    items = [{'id': pt.id, 'display_name': pt.type_name} for pt in payment_types]
    return render_template('master_list.html', 
                           title='Manage Payment Types', 
                           items=items,
                           add_url=url_for('routes.add_payment_type'),
                           edit_endpoint='routes.edit_payment_type',
                           delete_endpoint='routes.delete_payment_type')

@routes_bp.route('/master/payment_types/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_payment_type():
    if request.method == 'POST':
        name = request.form.get('name_field').strip()
        if PaymentType.query.filter(func.lower(PaymentType.type_name) == func.lower(name)).first():
            flash(f'Payment Type "{name}" already exists.', 'danger')
        else:
            db.session.add(PaymentType(type_name=name))
            db.session.commit()
            flash('Payment Type added successfully.', 'success')
            return redirect(url_for('routes.master_payment_types'))
            
    return render_template('master_form.html', 
                           title='Add Payment Type', 
                           field_label='Payment Type Name', 
                           current_value='',
                           submit_url=url_for('routes.add_payment_type'),
                           back_url=url_for('routes.master_payment_types'))

@routes_bp.route('/master/payment_types/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_payment_type(id):
    pt = PaymentType.query.get_or_404(id)
    if request.method == 'POST':
        new_name = request.form.get('name_field').strip()
        
        existing = PaymentType.query.filter(func.lower(PaymentType.type_name) == func.lower(new_name), PaymentType.id != id).first()
        if existing:
            flash(f'Payment Type "{new_name}" already exists.', 'danger')
        else:
            pt.type_name = new_name
            db.session.commit()
            flash('Payment Type updated successfully.', 'success')
            return redirect(url_for('routes.master_payment_types'))
            
    return render_template('master_form.html', 
                           title='Edit Payment Type', 
                           field_label='Payment Type Name', 
                           current_value=pt.type_name,
                           submit_url=url_for('routes.edit_payment_type', id=pt.id),
                           back_url=url_for('routes.master_payment_types'))

@routes_bp.route('/master/payment_types/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_payment_type(id):
    pt = PaymentType.query.get_or_404(id)
    if any(tx.get('payment_type') == pt.type_name for tx in sc.get_transactions()):
        flash(f'Cannot delete Payment Type "{pt.type_name}" because it is linked to existing transactions.', 'danger')
    else:
        db.session.delete(pt)
        db.session.commit()
        flash('Payment Type deleted successfully.', 'success')
    return redirect(url_for('routes.master_payment_types'))

# --- BANK ACCOUNTS ---
@routes_bp.route('/master/bank_accounts')
@login_required
@admin_required
def master_bank_accounts():
    bank_accounts = BankAccount.query.order_by(BankAccount.account_name).all()
    items = [{'id': b.id, 'display_name': b.account_name} for b in bank_accounts]
    return render_template('master_list.html', 
                           title='Manage Bank Accounts', 
                           items=items,
                           add_url=url_for('routes.add_bank_account'),
                           edit_endpoint='routes.edit_bank_account',
                           delete_endpoint='routes.delete_bank_account')

@routes_bp.route('/master/bank_accounts/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_bank_account():
    if request.method == 'POST':
        name = request.form.get('name_field').strip()
        if BankAccount.query.filter(func.lower(BankAccount.account_name) == func.lower(name)).first():
            flash(f'Bank Account "{name}" already exists.', 'danger')
        else:
            db.session.add(BankAccount(account_name=name))
            db.session.commit()
            flash('Bank Account added successfully.', 'success')
            return redirect(url_for('routes.master_bank_accounts'))
            
    return render_template('master_form.html', 
                           title='Add Bank Account', 
                           field_label='Account Name', 
                           current_value='',
                           submit_url=url_for('routes.add_bank_account'),
                           back_url=url_for('routes.master_bank_accounts'))

@routes_bp.route('/master/bank_accounts/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_bank_account(id):
    ba = BankAccount.query.get_or_404(id)
    if request.method == 'POST':
        new_name = request.form.get('name_field').strip()
        
        existing = BankAccount.query.filter(func.lower(BankAccount.account_name) == func.lower(new_name), BankAccount.id != id).first()
        if existing:
            flash(f'Bank Account "{new_name}" already exists.', 'danger')
        else:
            ba.account_name = new_name
            db.session.commit()
            flash('Bank Account updated successfully.', 'success')
            return redirect(url_for('routes.master_bank_accounts'))
            
    return render_template('master_form.html', 
                           title='Edit Bank Account', 
                           field_label='Account Name', 
                           current_value=ba.account_name,
                           submit_url=url_for('routes.edit_bank_account', id=ba.id),
                           back_url=url_for('routes.master_bank_accounts'))

@routes_bp.route('/master/bank_accounts/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_bank_account(id):
    ba = BankAccount.query.get_or_404(id)
    if any(tx.get('bank_account') == ba.account_name for tx in sc.get_transactions()):
        flash(f'Cannot delete Bank Account "{ba.account_name}" because it is linked to existing transactions.', 'danger')
    else:
        db.session.delete(ba)
        db.session.commit()
        flash('Bank Account deleted successfully.', 'success')
    return redirect(url_for('routes.master_bank_accounts'))

# ==========================================
# PHASE 3: ADMIN USER MANAGEMENT ROUTES (REMOVED)
# Note: User management is now handled via Supabase Auth dashboard or Admin API.
# ==========================================
