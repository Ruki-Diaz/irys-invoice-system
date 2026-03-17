from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from models import db, User, Customer, Salesperson, PaymentType, BankAccount, Transaction
from sqlalchemy import func
import pandas as pd
import io
from fpdf import FPDF
from datetime import datetime
from functools import wraps

routes_bp = Blueprint('routes', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You do not have permission to access that page.', 'danger')
            return redirect(url_for('routes.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@routes_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            if not user.is_active:
                flash('This account has been deactivated. Please contact an administrator.', 'danger')
                return redirect(url_for('routes.login'))
            login_user(user)
            return redirect(url_for('routes.dashboard'))
        else:
            flash('Invalid username or password', 'danger')
            
    return render_template('login.html')

@routes_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('routes.login'))

@routes_bp.route('/')
@routes_bp.route('/dashboard')
@login_required
def dashboard():
    # Calculate summary metrics
    total_tx = Transaction.query.count()
    total_invoice = db.session.query(func.sum(Transaction.invoice_amount)).scalar() or 0.0
    total_payment = db.session.query(func.sum(Transaction.payment_amount)).scalar() or 0.0
    total_outstanding = total_invoice - total_payment
    
    return render_template('dashboard.html', 
                           total_tx=total_tx, 
                           total_invoice=total_invoice, 
                           total_payment=total_payment, 
                           total_outstanding=total_outstanding)

@routes_bp.route('/transactions/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    customers = Customer.query.order_by(Customer.name).all()
    salespersons = Salesperson.query.order_by(Salesperson.name).all()
    payment_types = PaymentType.query.order_by(PaymentType.type_name).all()
    bank_accounts = BankAccount.query.order_by(BankAccount.account_name).all()
    
    if request.method == 'POST':
        try:
            date_str = request.form.get('date')
            tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            invoice_amount = float(request.form.get('invoice_amount') or 0.0)
            payment_amount = float(request.form.get('payment_amount') or 0.0)
            
            # Check for duplicate invoice
            invoice_number = request.form.get('invoice_number')
            existing_tx = Transaction.query.filter_by(invoice_number=invoice_number).first()
            if existing_tx:
                flash(f'Invoice number {invoice_number} already exists.', 'danger')
                return redirect(request.url)
            
            tx = Transaction(
                customer_id=request.form.get('customer_id'),
                salesperson_id=request.form.get('salesperson_id'),
                invoice_number=invoice_number,
                date=tx_date,
                invoice_amount=invoice_amount,
                payment_amount=payment_amount,
                payment_type_id=request.form.get('payment_type_id') or None,
                bank_account_id=request.form.get('bank_account_id') or None,
                remark=request.form.get('remark')
            )
            db.session.add(tx)
            db.session.commit()
            flash('Transaction added successfully.', 'success')
            return redirect(url_for('routes.view_transactions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding transaction: {str(e)}', 'danger')
            
    return render_template('add_transaction.html', 
                           customers=customers, 
                           salespersons=salespersons, 
                           payment_types=payment_types, 
                           bank_accounts=bank_accounts)

@routes_bp.route('/transactions', methods=['GET'])
@login_required
def view_transactions():
    query = Transaction.query.join(Customer).join(Salesperson)
    
    # Search / Filters
    search_cust = request.args.get('customer_name', '')
    search_inv = request.args.get('invoice_number', '')
    filter_start = request.args.get('start_date', '')
    filter_end = request.args.get('end_date', '')
    filter_sp = request.args.get('salesperson_id', '')
    filter_pt = request.args.get('payment_type_id', '')
    
    if search_cust:
        query = query.filter(Customer.name.ilike(f'%{search_cust}%'))
    if search_inv:
        query = query.filter(Transaction.invoice_number.ilike(f'%{search_inv}%'))
    if filter_start:
        query = query.filter(Transaction.date >= datetime.strptime(filter_start, '%Y-%m-%d').date())
    if filter_end:
        query = query.filter(Transaction.date <= datetime.strptime(filter_end, '%Y-%m-%d').date())
    if filter_sp:
        query = query.filter(Transaction.salesperson_id == filter_sp)
    if filter_pt:
        query = query.filter(Transaction.payment_type_id == filter_pt)
        
    transactions = query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    
    salespersons = Salesperson.query.order_by(Salesperson.name).all()
    payment_types = PaymentType.query.order_by(PaymentType.type_name).all()
    
    return render_template('view_transactions.html', 
                           transactions=transactions,
                           salespersons=salespersons,
                           payment_types=payment_types)

@routes_bp.route('/transactions/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(id):
    tx = Transaction.query.get_or_404(id)
    customers = Customer.query.order_by(Customer.name).all()
    salespersons = Salesperson.query.order_by(Salesperson.name).all()
    payment_types = PaymentType.query.order_by(PaymentType.type_name).all()
    bank_accounts = BankAccount.query.order_by(BankAccount.account_name).all()
    
    if request.method == 'POST':
        try:
            date_str = request.form.get('date')
            tx.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            tx.invoice_amount = float(request.form.get('invoice_amount') or 0.0)
            tx.payment_amount = float(request.form.get('payment_amount') or 0.0)
            
            new_invoice_number = request.form.get('invoice_number')
            if new_invoice_number != tx.invoice_number:
                existing_tx = Transaction.query.filter_by(invoice_number=new_invoice_number).first()
                if existing_tx:
                    flash(f'Invoice number {new_invoice_number} already exists.', 'danger')
                    return redirect(request.url)
            
            tx.invoice_number = new_invoice_number
            tx.customer_id = request.form.get('customer_id')
            tx.salesperson_id = request.form.get('salesperson_id')
            tx.payment_type_id = request.form.get('payment_type_id') or None
            tx.bank_account_id = request.form.get('bank_account_id') or None
            tx.remark = request.form.get('remark')
            
            db.session.commit()
            flash('Transaction updated successfully.', 'success')
            return redirect(url_for('routes.view_transactions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating transaction: {str(e)}', 'danger')

    return render_template('edit_transaction.html', 
                           tx=tx, 
                           customers=customers, 
                           salespersons=salespersons, 
                           payment_types=payment_types, 
                           bank_accounts=bank_accounts)

@routes_bp.route('/transactions/delete/<int:id>', methods=['POST'])
@login_required
def delete_transaction(id):
    tx = Transaction.query.get_or_404(id)
    try:
        db.session.delete(tx)
        db.session.commit()
        flash('Transaction deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting transaction: {str(e)}', 'danger')
    return redirect(url_for('routes.view_transactions'))

@routes_bp.route('/reports', methods=['GET'])
@login_required
def reports():
    customers = Customer.query.order_by(Customer.name).all()
    return render_template('reports.html', customers=customers)

@routes_bp.route('/export/excel')
@login_required
def export_excel():
    transactions = Transaction.query.order_by(Transaction.date.desc()).all()
    
    data = []
    for tx in transactions:
        data.append({
            'Date': tx.date.strftime('%Y-%m-%d'),
            'Invoice Number': tx.invoice_number,
            'Customer': tx.customer.name,
            'Salesperson': tx.salesperson.name,
            'Invoice Amount': tx.invoice_amount,
            'Payment Amount': tx.payment_amount,
            'Outstanding': tx.invoice_amount - tx.payment_amount,
            'Payment Type': tx.payment_type.type_name if tx.payment_type else '',
            'Bank Account': tx.bank_account.account_name if tx.bank_account else '',
            'Remark': tx.remark or ''
        })
        
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Transactions')
    
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

@routes_bp.route('/export/pdf/customer_statement/<int:customer_id>')
@login_required
def pdf_customer_statement(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    transactions = Transaction.query.filter_by(customer_id=customer_id).order_by(Transaction.date).all()
    
    total_inv = sum(tx.invoice_amount for tx in transactions)
    total_pay = sum(tx.payment_amount for tx in transactions)
    balance = total_inv - total_pay
    
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, f'Customer Statement: {customer.name}', 0, 1)
    
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, f'Total Invoiced: ${total_inv:.2f}', 0, 1)
    pdf.cell(0, 8, f'Total Paid: ${total_pay:.2f}', 0, 1)
    pdf.cell(0, 8, f'Outstanding Balance: ${balance:.2f}', 0, 1)
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
        pdf.cell(30, 8, tx.date.strftime('%Y-%m-%d'), 1, 0, 'C')
        pdf.cell(35, 8, tx.invoice_number, 1, 0, 'C')
        pdf.cell(35, 8, f'${tx.invoice_amount:.2f}', 1, 0, 'R')
        pdf.cell(35, 8, f'${tx.payment_amount:.2f}', 1, 0, 'R')
        # truncate remark
        remark = (tx.remark[:30] + '..') if tx.remark and len(tx.remark) > 30 else (tx.remark or '')
        pdf.cell(55, 8, remark, 1, 1, 'L')
        
    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    return send_file(output, download_name=f'statement_{customer.name.replace(" ", "_")}.pdf', mimetype='application/pdf', as_attachment=True)

@routes_bp.route('/export/pdf/outstanding')
@login_required
def pdf_outstanding():
    # aggregate by customer
    results = db.session.query(
        Customer.name,
        func.sum(Transaction.invoice_amount).label('tot_inv'),
        func.sum(Transaction.payment_amount).label('tot_pay')
    ).join(Transaction).group_by(Customer.id).having(func.sum(Transaction.invoice_amount) - func.sum(Transaction.payment_amount) > 0).all()
    
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
    for row in results:
        inv = row.tot_inv or 0.0
        pay = row.tot_pay or 0.0
        bal = inv - pay
        total_balance += bal
        
        pdf.cell(75, 8, row.name, 1, 0, 'L')
        pdf.cell(40, 8, f'${inv:.2f}', 1, 0, 'R')
        pdf.cell(40, 8, f'${pay:.2f}', 1, 0, 'R')
        pdf.cell(35, 8, f'${bal:.2f}', 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, f'Total System Outstanding: ${total_balance:.2f}', 0, 1, 'R')
    
    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    return send_file(output, download_name='outstanding_payments.pdf', mimetype='application/pdf', as_attachment=True)

@routes_bp.route('/export/pdf/summary')
@login_required
def pdf_summary():
    total_tx = Transaction.query.count()
    total_inv = db.session.query(func.sum(Transaction.invoice_amount)).scalar() or 0.0
    total_pay = db.session.query(func.sum(Transaction.payment_amount)).scalar() or 0.0
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
        ('Total Invoiced Amount', f'${total_inv:.2f}'),
        ('Total Payment Amount', f'${total_pay:.2f}'),
        ('Total Outstanding Balance', f'${balance:.2f}')
    ]
    
    for k, v in metrics:
        pdf.cell(90, 10, k, 1, 0, 'L')
        pdf.cell(90, 10, v, 1, 1, 'R')
        
    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    return send_file(output, download_name='summary_report.pdf', mimetype='application/pdf', as_attachment=True)


# ==========================================
# PHASE 2: MASTER DATA MANAGEMENT ROUTES
# ==========================================

# --- CUSTOMERS ---
@routes_bp.route('/master/customers')
@login_required
def master_customers():
    customers = Customer.query.order_by(Customer.name).all()
    # map to generic generic item structure
    items = [{'id': c.id, 'display_name': c.name} for c in customers]
    return render_template('master_list.html', 
                           title='Manage Customers', 
                           items=items,
                           add_url=url_for('routes.add_customer'),
                           edit_endpoint='routes.edit_customer',
                           delete_endpoint='routes.delete_customer')

@routes_bp.route('/master/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        name = request.form.get('name_field').strip()
        if Customer.query.filter(func.lower(Customer.name) == func.lower(name)).first():
            flash(f'Customer "{name}" already exists.', 'danger')
        else:
            db.session.add(Customer(name=name))
            db.session.commit()
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
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    if request.method == 'POST':
        new_name = request.form.get('name_field').strip()
        
        # Check for duplicates excluding self
        existing = Customer.query.filter(func.lower(Customer.name) == func.lower(new_name), Customer.id != id).first()
        if existing:
            flash(f'Customer "{new_name}" already exists.', 'danger')
        else:
            customer.name = new_name
            db.session.commit()
            flash('Customer updated successfully.', 'success')
            return redirect(url_for('routes.master_customers'))
            
    return render_template('master_form.html', 
                           title='Edit Customer', 
                           field_label='Customer Name', 
                           current_value=customer.name,
                           submit_url=url_for('routes.edit_customer', id=customer.id),
                           back_url=url_for('routes.master_customers'))

@routes_bp.route('/master/customers/delete/<int:id>', methods=['POST'])
@login_required
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    # Protection against deleting referenced data
    if Transaction.query.filter_by(customer_id=id).first():
        flash(f'Cannot delete Customer "{customer.name}" because they are linked to existing transactions.', 'danger')
    else:
        db.session.delete(customer)
        db.session.commit()
        flash('Customer deleted successfully.', 'success')
    return redirect(url_for('routes.master_customers'))

# --- SALESPERSONS ---
@routes_bp.route('/master/salespersons')
@login_required
def master_salespersons():
    salespersons = Salesperson.query.order_by(Salesperson.name).all()
    items = [{'id': s.id, 'display_name': s.name} for s in salespersons]
    return render_template('master_list.html', 
                           title='Manage Salespersons', 
                           items=items,
                           add_url=url_for('routes.add_salesperson'),
                           edit_endpoint='routes.edit_salesperson',
                           delete_endpoint='routes.delete_salesperson')

@routes_bp.route('/master/salespersons/add', methods=['GET', 'POST'])
@login_required
def add_salesperson():
    if request.method == 'POST':
        name = request.form.get('name_field').strip()
        if Salesperson.query.filter(func.lower(Salesperson.name) == func.lower(name)).first():
            flash(f'Salesperson "{name}" already exists.', 'danger')
        else:
            db.session.add(Salesperson(name=name))
            db.session.commit()
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
def edit_salesperson(id):
    salesperson = Salesperson.query.get_or_404(id)
    if request.method == 'POST':
        new_name = request.form.get('name_field').strip()
        
        existing = Salesperson.query.filter(func.lower(Salesperson.name) == func.lower(new_name), Salesperson.id != id).first()
        if existing:
            flash(f'Salesperson "{new_name}" already exists.', 'danger')
        else:
            salesperson.name = new_name
            db.session.commit()
            flash('Salesperson updated successfully.', 'success')
            return redirect(url_for('routes.master_salespersons'))
            
    return render_template('master_form.html', 
                           title='Edit Salesperson', 
                           field_label='Salesperson Name', 
                           current_value=salesperson.name,
                           submit_url=url_for('routes.edit_salesperson', id=salesperson.id),
                           back_url=url_for('routes.master_salespersons'))

@routes_bp.route('/master/salespersons/delete/<int:id>', methods=['POST'])
@login_required
def delete_salesperson(id):
    salesperson = Salesperson.query.get_or_404(id)
    if Transaction.query.filter_by(salesperson_id=id).first():
        flash(f'Cannot delete Salesperson "{salesperson.name}" because they are linked to existing transactions.', 'danger')
    else:
        db.session.delete(salesperson)
        db.session.commit()
        flash('Salesperson deleted successfully.', 'success')
    return redirect(url_for('routes.master_salespersons'))

# --- PAYMENT TYPES ---
@routes_bp.route('/master/payment_types')
@login_required
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
def delete_payment_type(id):
    pt = PaymentType.query.get_or_404(id)
    if Transaction.query.filter_by(payment_type_id=id).first():
        flash(f'Cannot delete Payment Type "{pt.type_name}" because it is linked to existing transactions.', 'danger')
    else:
        db.session.delete(pt)
        db.session.commit()
        flash('Payment Type deleted successfully.', 'success')
    return redirect(url_for('routes.master_payment_types'))

# --- BANK ACCOUNTS ---
@routes_bp.route('/master/bank_accounts')
@login_required
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
def delete_bank_account(id):
    ba = BankAccount.query.get_or_404(id)
    if Transaction.query.filter_by(bank_account_id=id).first():
        flash(f'Cannot delete Bank Account "{ba.account_name}" because it is linked to existing transactions.', 'danger')
    else:
        db.session.delete(ba)
        db.session.commit()
        flash('Bank Account deleted successfully.', 'success')
    return redirect(url_for('routes.master_bank_accounts'))

# ==========================================
# PHASE 3: ADMIN USER MANAGEMENT ROUTES
# ==========================================

@routes_bp.route('/master/users')
@login_required
@admin_required
def master_users():
    users = User.query.all()
    return render_template('user_list.html', users=users)

@routes_bp.route('/master/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        role = request.form.get('role')
        
        if User.query.filter(func.lower(User.username) == func.lower(username)).first():
            flash(f'Username "{username}" already exists.', 'danger')
        else:
            from werkzeug.security import generate_password_hash
            new_user = User(
                username=username, 
                password=generate_password_hash(password),
                role=role,
                is_active=True
            )
            db.session.add(new_user)
            db.session.commit()
            flash('User created successfully.', 'success')
            return redirect(url_for('routes.master_users'))
            
    return render_template('user_form.html', user=None)

@routes_bp.route('/master/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)
    
    # Prevent editing the super admin role unless logging in as them
    if user.username == 'admin' and current_user.username != 'admin':
         flash('Only the master admin can edit this account.', 'danger')
         return redirect(url_for('routes.master_users'))

    if request.method == 'POST':
        new_username = request.form.get('username').strip()
        
        # Check duplicate
        existing = User.query.filter(func.lower(User.username) == func.lower(new_username), User.id != id).first()
        if existing:
            flash(f'Username "{new_username}" already exists.', 'danger')
        else:
            user.username = new_username
            user.role = request.form.get('role')
            user.is_active = request.form.get('is_active') == 'true'
            
            # Optional password reset
            new_password = request.form.get('password')
            if new_password:
                from werkzeug.security import generate_password_hash
                user.password = generate_password_hash(new_password)
                
            db.session.commit()
            flash('User updated successfully.', 'success')
            return redirect(url_for('routes.master_users'))
            
    return render_template('user_form.html', user=user)
