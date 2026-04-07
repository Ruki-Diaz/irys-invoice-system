-- 1. Add user_id column with ForeignKey reference to Supabase Auth
--    We allow NULL initially so existing table data doesn't block the alter.
ALTER TABLE transactions 
  ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users(id) DEFAULT auth.uid();

ALTER TABLE customers 
  ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users(id) DEFAULT auth.uid();

ALTER TABLE salespersons 
  ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users(id) DEFAULT auth.uid();

-- 2. Backfill existing data with the first user's UUID
--    This ensures existing data remains accessible to this user under RLS.
UPDATE transactions 
  SET user_id = 'eea809b7-53d5-43ee-8d73-0d570403001b' 
  WHERE user_id IS NULL;

UPDATE customers 
  SET user_id = 'eea809b7-53d5-43ee-8d73-0d570403001b' 
  WHERE user_id IS NULL;

UPDATE salespersons 
  SET user_id = 'eea809b7-53d5-43ee-8d73-0d570403001b' 
  WHERE user_id IS NULL;

-- 3. Enforce NOT NULL for future production safety
--    Since all rows now have a user_id, we can safely enforce this rule.
ALTER TABLE transactions ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE customers ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE salespersons ALTER COLUMN user_id SET NOT NULL;

-- 4. Enable Row Level Security (RLS)
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE salespersons ENABLE ROW LEVEL SECURITY;

-- 5. Create strict RLS Policies for Transactions
-- Drop existing policies if they exist so this script is cleanly replayable
DROP POLICY IF EXISTS "View own transactions" ON transactions;
DROP POLICY IF EXISTS "Insert own transactions" ON transactions;
DROP POLICY IF EXISTS "Update own transactions" ON transactions;
DROP POLICY IF EXISTS "Delete own transactions" ON transactions;

CREATE POLICY "View own transactions" ON transactions 
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Insert own transactions" ON transactions 
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Update own transactions" ON transactions 
  FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Delete own transactions" ON transactions 
  FOR DELETE USING (auth.uid() = user_id);

-- 6. Create strict RLS Policies for Customers
DROP POLICY IF EXISTS "View own customers" ON customers;
DROP POLICY IF EXISTS "Insert own customers" ON customers;
DROP POLICY IF EXISTS "Update own customers" ON customers;
DROP POLICY IF EXISTS "Delete own customers" ON customers;

CREATE POLICY "View own customers" ON customers 
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Insert own customers" ON customers 
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Update own customers" ON customers 
  FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Delete own customers" ON customers 
  FOR DELETE USING (auth.uid() = user_id);

-- 7. Create strict RLS Policies for Salespersons
DROP POLICY IF EXISTS "View own salespersons" ON salespersons;
DROP POLICY IF EXISTS "Insert own salespersons" ON salespersons;
DROP POLICY IF EXISTS "Update own salespersons" ON salespersons;
DROP POLICY IF EXISTS "Delete own salespersons" ON salespersons;

CREATE POLICY "View own salespersons" ON salespersons 
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Insert own salespersons" ON salespersons 
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Update own salespersons" ON salespersons 
  FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Delete own salespersons" ON salespersons 
  FOR DELETE USING (auth.uid() = user_id);
