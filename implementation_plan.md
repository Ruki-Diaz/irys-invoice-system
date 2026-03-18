# Multi-Payment Invoice Logic - Implementation Plan

This document outlines the strategy for safely adapting the Irys Invoice Management System to support multiple staggered payments against a single invoice number. 

The core mathematical principle for this update is simple: When an additional payment is recorded for an existing invoice, its `invoice_amount` will cleanly process as `0.0`. This guarantees that existing [sum(invoice_amount)](file:///d:/Webapp/routes.py#407-446) database calls powering your Dashboards, PDF reports, and Excel sheets will instantly aggregate the exact correct totals without any code rewrites.

## Proposed Changes

### 1. Database Schema Modification
Currently, `Transaction.invoice_number` enforces SQL uniqueness (`unique=True`). We need to drop this constraint to allow a single invoice number to have multiple transaction row entries.

#### [MODIFY] [models.py](file:///d:/Webapp/models.py)
- Remove `unique=True` from the `invoice_number` column definition in the [Transaction](file:///d:/Webapp/models.py#34-51) class.

#### [NEW] `migrate_db.py`
- Since SQLite does not natively support `ALTER TABLE ... DROP CONSTRAINT`, I will write a completely safe python script that uses `sqlite3` to:
  1. Rename the existing [transactions](file:///d:/Webapp/routes.py#118-153) table to `transactions_old`.
  2. Create a fresh [transactions](file:///d:/Webapp/routes.py#118-153) table identical to the original but without the `UNIQUE` index on the `invoice_number`.
  3. `INSERT INTO transactions SELECT * FROM transactions_old`.
  4. Drop the old table.
- This guarantees zero data loss and takes less than a second to execute.

### 2. Transaction Backend Logic
We need to safeguard user entry so that adding multiple payments is intuitive and mathematically sound.

#### [MODIFY] [routes.py](file:///d:/Webapp/routes.py)
- **In [add_transaction](file:///d:/Webapp/routes.py#66-117)**: 
  - When the user submits the form, query if the `invoice_number` already exists.
  - **Validation**: If it exists, verify the user selected the same [Customer](file:///d:/Webapp/models.py#14-18) as the original invoice. Deny entry if there is a mismatch.
  - **Deduplication**: Automatically set `invoice_amount = 0.0` and flash a warning informing the user that the invoice amount was zeroed out to prevent skewing the global dashboard totals.

### 3. User Interface Enhancements
To properly represent the overall status of an invoice that may span several transaction rows.

#### [MODIFY] [routes.py](file:///d:/Webapp/routes.py)
- **In [view_transactions](file:///d:/Webapp/routes.py#118-153)**: Run a grouped SQLAlchemy query to calculate the `total_invoice_amount` and `total_payment_amount` explicitly grouped *by* `invoice_number` for all visible rows. Pass this dictionary to the template as `invoice_totals`.

#### [MODIFY] [templates/view_transactions.html](file:///d:/Webapp/templates/view_transactions.html)
- Update the looping logic displaying the Status badge (Paid/Pending/Other).
- Instead of calculating status based on the singular transaction row amount (`tx.invoice_amount > tx.payment_amount`), it will lookup the aggregated totals injected from the backend (`invoice_totals[tx.invoice_number]`) to show the true, accurate status of the entire invoice life-cycle.

## Verification Plan
1. **Migration Verification**: Run the migration script and verify the application boots successfully without database errors.
2. **Transaction Insertion**: Add a "Test Invoice" for $1,000 to "Acme Corp" with a $500 payment. Status should be `Pending`.
3. **Subsequent Payment**: Add another record using the same "Test Invoice" number for "Acme Corp". Put Invoice Amount as $1,000 and Payment as $500. Upon saving, verify a flash message indicates the invoice amount was zeroed.
4. **Visual Verification**: Check the View Transactions table; both rows should now confidently declare the status as `Paid` because the system detected the aggregated sums matching ($1,000 invoiced, $1,000 heavily paid).
5. **Report Verification**: Check the Dashboard to verify total outstanding balances were not artificially inflated.
