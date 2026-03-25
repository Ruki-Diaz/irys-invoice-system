# Plan: Dynamic Dropdowns from Supabase

## Goal Description
The objective is to connect the Customer and Salesperson dropdowns in the transaction form directly to the [customers](file:///d:/Webapp/routes.py#676-689) and [salespersons](file:///d:/Webapp/routes.py#751-763) tables in Supabase. This will replace the current SQLAlchemy/SQLite queries. Additionally, we need to allow users to input new customer or salesperson names directly in the transaction form, which should automatically insert them into Supabase if they are missing.

## User Review Required
> [!IMPORTANT]
> To allow users to type a *new* customer or salesperson name while keeping the dropdown functionality (as per the requirement: "when a user submits a transaction with a new customer name, it inserts that name into customers if missing"), we will convert the `<select>` elements into `<input class="form-control" list="...">` elements with `<datalist>`s. This behaves exactly like a dropdown but allows typing arbitrary text without changing the fundamental Bootstrap UI design. Does this approach work for you?

## Proposed Changes

### Supabase Client
#### [MODIFY] supabase_client.py
- Add `get_customers()` and `get_salespersons()` to fetch records from Supabase and return them sorted alphabetically by name.
- Add `ensure_customer(name)` and `ensure_salesperson(name)`. These functions will accept a string name, trim whitespace, check if it already exists (case-insensitive) in the respective table, and perform an insert if it doesn't exist. This prevents duplicate master records.

---
### Backend Routes
#### [MODIFY] routes.py
- **[add_transaction](file:///d:/Webapp/routes.py#68-146) and [edit_transaction](file:///d:/Webapp/routes.py#216-282) (GET):** Replace `Customer.query...` and `Salesperson.query...` with `sc.get_customers()` and `sc.get_salespersons()`.
- **[add_transaction](file:///d:/Webapp/routes.py#68-146) and [edit_transaction](file:///d:/Webapp/routes.py#216-282) (POST):**
  - Read `customer_name` and `salesperson_name` from the form instead of `customer_id` and `salesperson_id`.
  - Pass these names through the `ensure_customer` and `ensure_salesperson` functions to insert them if they are new.
  - Remove all current `Customer.query.get(...)` and `Salesperson.query.get(...)` calls for fetching names.
- **`/api/invoice_details`:** Stop doing SQLAlchemy lookup for `customer_id`. Just pass back the string [customer](file:///d:/Webapp/routes.py#690-710) name from `original_tx` to auto-fill the form correctly.

---
### Frontend Form Templates
#### [MODIFY] templates/add_transaction.html
- Convert `customer_id` `<select>` block to an `<input list="customers_list" name="customer_name" id="customer_name" class="form-control">` along with a `<datalist>` of options.
- Convert `salesperson_id` `<select>` to `<input list="salespersons_list" name="salesperson_name" id="salesperson_name" class="form-control">`.
- Update the javascript that locks the dropdown for follow-up payments: it should set `custSelect.value = data.customer;` (using the name) and lock the field.

#### [MODIFY] templates/edit_transaction.html
- Apply the same `<input list="...">` conversions for Customer and Salesperson fields.
- Make sure to pre-fill the `value="..."` correctly with the existing transaction's name.

## Verification Plan

### Automated Tests
*No existing automated tests were found for this functional change.*

### Manual Verification
1. **Empty State Handling**: Ensure the transaction form loads without crashing if Supabase [customers](file:///d:/Webapp/routes.py#676-689) and [salespersons](file:///d:/Webapp/routes.py#751-763) tables are initially empty.
2. **Dropdown Render**: Check the transaction form UI. It should display the names from the Supabase tables in alphabetical order.
3. **Add Existing**: Select an existing customer and existing salesperson, set an amount, and save. Verify the transaction creates successfully without duplicating the master records.
4. **Add New**: Type a completely new customer name (e.g., "New Acme Corp") and a new salesperson name. Add leading/trailing spaces to test trimming. Submit the form.
   - Verify transaction was created.
   - Verify Supabase [customers](file:///d:/Webapp/routes.py#676-689) and [salespersons](file:///d:/Webapp/routes.py#751-763) tables now contain these new trimmed entries.
5. **Follow up payment**: Type an existing invoice number in the form. Verify the customer input field auto-fills with the correct string name, and becomes read-only (locked).
6. **Edit transaction flow**: Open an existing transaction in edit mode. Verify the customer and salesperson fields are pre-filled correctly with their names, update the salesperson to a new one, save, and verify.
