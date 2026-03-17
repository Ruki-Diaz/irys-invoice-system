from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='staff')
    is_active = db.Column(db.Boolean, default=True)

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)

class Salesperson(db.Model):
    __tablename__ = 'salespersons'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)

class PaymentType(db.Model):
    __tablename__ = 'payment_types'
    id = db.Column(db.Integer, primary_key=True)
    type_name = db.Column(db.String(100), nullable=False)

class BankAccount(db.Model):
    __tablename__ = 'bank_accounts'
    id = db.Column(db.Integer, primary_key=True)
    account_name = db.Column(db.String(150), nullable=False)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    salesperson_id = db.Column(db.Integer, db.ForeignKey('salespersons.id'), nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False, unique=True)
    date = db.Column(db.Date, nullable=False)
    invoice_amount = db.Column(db.Float, default=0.0)
    payment_amount = db.Column(db.Float, default=0.0)
    payment_type_id = db.Column(db.Integer, db.ForeignKey('payment_types.id'), nullable=True)
    bank_account_id = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'), nullable=True)
    remark = db.Column(db.Text, nullable=True)

    customer = db.relationship('Customer', backref=db.backref('transactions', lazy=True))
    salesperson = db.relationship('Salesperson', backref=db.backref('transactions', lazy=True))
    payment_type = db.relationship('PaymentType', backref=db.backref('transactions', lazy=True))
    bank_account = db.relationship('BankAccount', backref=db.backref('transactions', lazy=True))
