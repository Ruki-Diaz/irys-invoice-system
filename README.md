# Irys Invoice Management System

A simple web application to manage invoices and payments built with Flask.

## Features
- Secure Login
- Dashboard with aggregated stats
- Add/View/Edit/Delete Transactions
- Generate PDF Reports (Customer Statements, Outstanding Payments, Summary)
- Export to Excel

## Setup Instructions (Local Deployment)

1. **Clone the repository / navigate to the folder:**
   ```bash
   cd Webapp
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - On Windows: `venv\Scripts\activate`
   - On macOS/Linux: `source venv/bin/activate`

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Initialize the Database (First time only):**
   ```bash
   python init_db.py
   ```
   *This will create the SQLite database and insert default dummy data, including an admin user.*
   *Default Login:*
   - **Username:** admin
   - **Password:** admin123

6. **Run the Application:**
   ```bash
   python app.py
   ```

7. **Access the App:**
   Open a browser and go to `http://127.0.0.1:5000`

## Production Deployment (Render)

This application is ready to be deployed to Render or similar Platform-as-a-Service (PaaS) providers out-of-the-box using Gunicorn.

1. **Push your code** to a GitHub/GitLab repository.
2. Log into [Render](https://render.com) and create a new **Web Service**.
3. Connect your repository.
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `gunicorn app:create_app()`
6. **Environment Variables**:
   - `SECRET_KEY`: Generate a random secure string (e.g. `python -c "import secrets; print(secrets.token_hex(16))"`)
   - `FLASK_DEBUG`: `False`
7. Click **Deploy**. Render will automatically assign a `PORT` and build your application.
