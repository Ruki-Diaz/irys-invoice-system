from app import create_app
from models import db, User, PaymentType, BankAccount, Customer, Salesperson
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    db.create_all()

    # Create admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin123'), role='admin', is_active=True)
        db.session.add(admin)
        print("Admin user created: admin / admin123")
    
    # Populate default payment types
    if not PaymentType.query.first():
        for pt in ['Cash', 'Credit Card', 'Bank Transfer', 'Cheque']:
            db.session.add(PaymentType(type_name=pt))
            
    # Populate a default bank account
    if not BankAccount.query.first():
        db.session.add(BankAccount(account_name='Main Operating Account'))

    # Populate dummy customers and salespersons so dropdowns aren't empty
    if not Customer.query.first():
        for c in ['Acme Corp', 'Globex Corporation', 'Soylent Corp', 'Initech']:
            db.session.add(Customer(name=c))
            
    if not Salesperson.query.first():
        for s in ['Dwight Schrute', 'Jim Halpert', 'Michael Scott', 'Stanley Hudson']:
            db.session.add(Salesperson(name=s))

    db.session.commit()
    print("Database initialized successfully!")
