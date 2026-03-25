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

