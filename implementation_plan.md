# Migrate to Supabase and Implement Multi-Payment Invoices

This plan details how we will migrate the system to Supabase (focusing on transactions via the direct python client) and implement multi-payment support for invoices.

## Proposed Changes

### Configuration & Connections
#### [NEW] `supabase_client.py`
- Create a new file to initialize the Supabase client using `SUPABASE_URL` and `SUPABASE_KEY` env variables.
- Create helper functions to handle structured queries:
  - [add_transaction()](file:///d:/Webapp/routes.py#66-137)
  - `get_transactions(filters)`
  - `get_invoice_totals()`
  - `get_outstanding_by_customer()`

#### [MODIFY] [requirements.txt](file:///d:/Webapp/requirements.txt)
- Add `supabase` and `postgrest-py` to support the Python client.

### Models and Database
#### [MODIFY] [models.py](file:///d:/Webapp/models.py)
- Remove the SQLite [Transaction](file:///d:/Webapp/models.py#34-51) model. We will rely purely on the Supabase client for transactions.
- Remove the [transactions](file:///d:/Webapp/routes.py#158-217) relationship definitions from [Customer](file:///d:/Webapp/models.py#14-18), [Salesperson](file:///d:/Webapp/models.py#19-23), [PaymentType](file:///d:/Webapp/models.py#24-28), and [BankAccount](file:///d:/Webapp/models.py#29-33). 
*(Note: Master data like User and Customer can still live in SQLite/SQLAlchemy for local ease, or if you update `SQLALCHEMY_DATABASE_URI` to a Postgres connection string, they will perfectly translate. The implementation focuses strictly on moving Transactions to the direct python client as requested).*

### Flask Routes
#### [MODIFY] [routes.py](file:///d:/Webapp/routes.py)
- Update `/dashboard` to aggregate transaction amounts from Supabase.
- Update `/transactions/add` to implement the new multi-payment business logic:
  - Check if `invoice_number` exists in Supabase.
  - If First Payment: save `invoice_amount = full amount`, `payment_amount = first payment`.
  - If Follow-up Payment: Validate `customer_name` matches. Save `invoice_amount = 0`, `payment_amount = new payment`. Auto-calculate the remaining balance and prevent overpayment.
- Update `/transactions` (View):
  - Change to fetch transactions from Supabase.
  - Apply filters inside Supabase queries ([eq](file:///d:/Webapp/routes.py#14-22), `gte`, `lte`, `ilike`).
  - Calculate grouping (`invoice_totals`) by invoice number.
- Update [delete_transaction](file:///d:/Webapp/routes.py#269-282), [edit_transaction](file:///d:/Webapp/routes.py#218-268), and `/api/invoice_details` to interact directly with Supabase via the client.
- Update PDF & Excel export routes to format and rely on data fetched from Supabase.

### UI / Templates
#### [MODIFY] [templates/add_transaction.html](file:///d:/Webapp/templates/add_transaction.html)
- Show warnings using JavaScript/AJAX if an invoice already exists (to auto-calculate remaining balance and lock the invoice amount input to 0).
- Update forms to correctly handle new and follow-up payments seamlessly.

#### [MODIFY] [templates/view_transactions.html](file:///d:/Webapp/templates/view_transactions.html)
- Reorganize the transactions table to show grouped aggregated data:
  - Group by Invoice Number showing: Customer, Total Invoiced, Total Paid, Balance, Status Badge.
  - Expandable/Collapsible rows (or a nested list) showing individual payment history for that invoice.
- Add "Outstanding Only" filter button.
- Add "Export Outstanding" button as requested.

## Verification Plan
### Automated Tests
*None for this app, relies on manual testing via browser.*

### Manual Verification
1. **Adding First Payment**: Verify going to `/transactions/add` with a new invoice number creates a row with `invoice_amount` and `payment_amount`.
2. **Adding Follow-up Payment**: Use the same invoice number again. Confirm that the UI warns it already exists, auto-fills customer, lock `invoice_amount` to 0, and saves properly.
3. **Overpayment Prevention**: Verify adding a follow-up payment greater than the balance raises an error.
4. **Grouping & Display**: Go to `/transactions` and verify the invoice is grouped properly with correct Status (Paid vs Pending) and balances.
5. **Filters & Exports**: Test the "Outstanding Only" filter and "Export Outstanding" buttons to ensure accurate reporting.
