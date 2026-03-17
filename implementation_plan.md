# Phase 1: Review + Plan

## Current State Review
**What is already working:**
- Secure Login & Session Management (` Flask-Login `)
- Dashboard overview with real-time aggregate metrics
- Transaction Management (View, Add, Edit, Delete) with search & filters
- Dropdowns dynamically populated from the database
- Duplicate invoice number prevention and form validation
- Confirmation prompts before deletion
- Document generation: PDF (Customer Statement, Outstanding Payments, Summary) and Excel Exports

**What is missing / Application Next Steps:**
- The original requirements are fully met, but currently the core entities (Customers, Salespeople, Payment Types, Bank Accounts) can only be added via the [init_db.py](file:///d:/Webapp/init_db.py) seed script or direct DB access.
- We need Master Data Management to allow staff to add, rename, and disable these entities via the UI safely.

## Phase 2 Upgrade Plan: Master Data Management

To introduce this without breaking any working feature, I propose adding incremental, isolated components.

1. **Routing Additions ([d:\Webapp\routes.py](file:///d:/Webapp/routes.py))**:
   We will strictly append new routes to the bottom of the file. No existing routes will be modified.
   - `/customers` (List, Add, Edit, Delete)
   - `/salespersons` (List, Add, Edit, Delete)
   - `/payment_types` (List, Add, Edit, Delete)
   - `/bank_accounts` (List, Add, Edit, Delete)
   
   **Safety measure**: Before deleting any record, the route will explicitly query [Transaction](file:///d:/Webapp/models.py#34-51) to see if the ID is in use. If it is, a Flask flash message will gracefully stop the deletion: `"Cannot delete this Customer because they are associated with existing transactions."` We will also enforce uniqueness on the names/types during creation and modification.

2. **Frontend Navigation ([d:\Webapp\templates\base.html](file:///d:/Webapp/templates/base.html))**:
   - We will append a "Master Data" header in the existing sidebar.
   - Add navigation active-state logic for the 4 new list pages.

3. **New Master Data Templates**:
   - [templates/master_list.html](file:///d:/Webapp/templates/master_list.html): A flexible, generic template to display a table of records for any of the 4 entities, featuring "Edit" and "Delete" action buttons.
   - [templates/master_form.html](file:///d:/Webapp/templates/master_form.html): A generic form template with a single text input to handle adding and renaming records.
   *Using generic templates reduces code duplication and the risk of breaking UI components.*

## Phase 3 Upgrade Plan: Admin-Managed User Accounts

To introduce role-based user management safely on top of the existing schema:

1. **Safe Database Migration**:
   - Instead of breaking the existing `app.db`, I will run a raw SQLite query script ([migrate_users.py](file:///d:/Webapp/migrate_users.py)) to execute `ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'staff'` and `ADD COLUMN is_active BOOLEAN DEFAULT 1`.
   - Update [models.py](file:///d:/Webapp/models.py) to include `role` and `is_active` fields.
   - Update [init_db.py](file:///d:/Webapp/init_db.py) to ensure the original admin user gets the [admin](file:///d:/Webapp/routes.py#14-22) role explicitly.

2. **Access Control ([d:\Webapp\routes.py](file:///d:/Webapp/routes.py))**:
   - Update `/login` to check if `user.is_active`. If false, flash a message "Account is deactivated" and deny login.
   - Create an `@admin_required` decorator that wraps existing `@login_required`. It will inspect `current_user.role`.
   - Append new protected endpoints: `/master/users`, `/master/users/add`, `/master/users/edit/<id>`.

3. **User Interfaces and Templates**:
   - Modify [d:\Webapp\templates\base.html](file:///d:/Webapp/templates/base.html) sidebar: wrap the new "Manage Users" link in an `{% if current_user.role == 'admin' %}` block so standard staff cannot see it.
   - Create [d:\Webapp\templates\user_list.html](file:///d:/Webapp/templates/user_list.html): Table displaying username, role, and active status.
   - Create [d:\Webapp\templates\user_form.html](file:///d:/Webapp/templates/user_form.html): Form handling creation and editing. Includes password setting only on creation (or specific explicit reset), and dropdowns for Role (Admin/Staff) and Status (Active/Inactive).

## Phase 4 Upgrade Plan: Polish, Hardening & Deployment Prep

To prepare this application for a real-company pilot release, we step through a comprehensive polish, hardening, and deployment phase.

1. **Phase 4.1: UI/UX & UX Improvements**:
   - Refactor [base.html](file:///d:/Webapp/templates/base.html) navigation to include branding "Invoice Management System" & "Finance Dashboard", highlight active tabs.
   - Refactor [dashboard.html](file:///d:/Webapp/templates/dashboard.html) making the metric cards more professional.
   - Sweep all tables (`transaction_list.html`, [master_list.html](file:///d:/Webapp/templates/master_list.html), [user_list.html](file:///d:/Webapp/templates/user_list.html)) to ensure they have `table-striped table-hover` and empty states ("No transactions yet").
   - Enhance forms ([add_transaction.html](file:///d:/Webapp/templates/add_transaction.html), [master_form.html](file:///d:/Webapp/templates/master_form.html), etc.) for optimal spacing and [required](file:///d:/Webapp/routes.py#14-22) indicators.

2. **Phase 4.2: PDF Improvements ([d:\Webapp\routes.py](file:///d:/Webapp/routes.py))**:
   - Use `reportlab` or existing `fpdf2` logic to cleanly format PDF headers (Company Name / System Name) and format tables with proper alignment and totals at the bottom.
   - Validate Excel generation ensuring filtered data maps correctly.

3. **Phase 4.3: Security & Production Hardening**:
   - Adjust [app.py](file:///d:/Webapp/app.py) / [routes.py](file:///d:/Webapp/routes.py) to pull `SECRET_KEY` from `os.environ` fallback logic.
   - Disable Flask debug mode in production bindings (i.e., when deployed).
   - Validation checks to ensure dropdowns cannot be bypassed with missing required fields.

4. **Phase 4.4: Deployment Preparation**:
   - Make [app.py](file:///d:/Webapp/app.py) bind to `0.0.0.0` and utilize `PORT` env var.
   - Add `gunicorn` to [requirements.txt](file:///d:/Webapp/requirements.txt).
   - Revise [README.md](file:///d:/Webapp/README.md) to cleanly map out steps for local running vs deploying to Render (PaaS).

## User Review Required

> [!IMPORTANT]  
> Please review the Phase 4 upgrade plan. It covers UI/UX, PDF refinement, security hardening, and deployment prep (like Render/gunicorn instructions) without fundamentally rebuilding the internal Flask setup. Does this align with your expectations for the pilot?
