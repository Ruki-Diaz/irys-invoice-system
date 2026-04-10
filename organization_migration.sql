-- organization_migration.sql

-- 1. Create a new `organizations` table
CREATE TABLE organizations (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    created_at timestamptz default now()
);

-- 2. Create a new `profiles` table
CREATE TABLE profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text,
    full_name text,
    organization_id uuid references organizations(id) on delete cascade,
    role text default 'member',
    created_at timestamptz default now()
);

-- 3. Add `organization_id` to business tables
ALTER TABLE customers ADD COLUMN organization_id uuid REFERENCES organizations(id);
ALTER TABLE salespersons ADD COLUMN organization_id uuid REFERENCES organizations(id);
ALTER TABLE transactions ADD COLUMN organization_id uuid REFERENCES organizations(id);

-- 4. Migrate existing data safely
-- Create one default organization for legacy data
DO $$
DECLARE
    legacy_org_id uuid;
BEGIN
    INSERT INTO organizations (name) VALUES ('Default Legacy Organization') RETURNING id INTO legacy_org_id;
    
    -- Assign all existing rows to this default organization
    UPDATE customers SET organization_id = legacy_org_id WHERE organization_id IS NULL;
    UPDATE salespersons SET organization_id = legacy_org_id WHERE organization_id IS NULL;
    UPDATE transactions SET organization_id = legacy_org_id WHERE organization_id IS NULL;

    -- Ensure all existing auth.users have a profile linked to this org
    INSERT INTO profiles (id, email, organization_id, role)
    SELECT id, email, legacy_org_id, 'admin'
    FROM auth.users
    ON CONFLICT (id) DO UPDATE SET organization_id = EXCLUDED.organization_id;
END $$;

-- 4b. Enforce non-null constraints safely after backfill
ALTER TABLE customers ALTER COLUMN organization_id SET NOT NULL;
ALTER TABLE salespersons ALTER COLUMN organization_id SET NOT NULL;
ALTER TABLE transactions ALTER COLUMN organization_id SET NOT NULL;

-- 5. Add secure Supabase RLS policies
-- First, ensure RLS is enabled on all tables
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE salespersons ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

-- Profiles Policies
CREATE POLICY "Users can view users in same org" ON profiles
    FOR SELECT USING (organization_id IN (SELECT organization_id FROM profiles p WHERE p.id = auth.uid()));

CREATE POLICY "Users can edit own profile" ON profiles
    FOR UPDATE USING (id = auth.uid()) WITH CHECK (id = auth.uid());

-- Customers Policies
DROP POLICY IF EXISTS "View own customers" ON customers;
DROP POLICY IF EXISTS "Insert own customers" ON customers;
DROP POLICY IF EXISTS "Update own customers" ON customers;
DROP POLICY IF EXISTS "Delete own customers" ON customers;

CREATE POLICY "Shared view customers" ON customers
    FOR SELECT USING (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));
CREATE POLICY "Shared insert customers" ON customers
    FOR INSERT WITH CHECK (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));
CREATE POLICY "Shared update customers" ON customers
    FOR UPDATE USING (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));
CREATE POLICY "Shared delete customers" ON customers
    FOR DELETE USING (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));

-- Salespersons Policies
DROP POLICY IF EXISTS "View own salespersons" ON salespersons;
DROP POLICY IF EXISTS "Insert own salespersons" ON salespersons;
DROP POLICY IF EXISTS "Update own salespersons" ON salespersons;
DROP POLICY IF EXISTS "Delete own salespersons" ON salespersons;

CREATE POLICY "Shared view salespersons" ON salespersons
    FOR SELECT USING (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));
CREATE POLICY "Shared insert salespersons" ON salespersons
    FOR INSERT WITH CHECK (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));
CREATE POLICY "Shared update salespersons" ON salespersons
    FOR UPDATE USING (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));
CREATE POLICY "Shared delete salespersons" ON salespersons
    FOR DELETE USING (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));

-- Transactions Policies
DROP POLICY IF EXISTS "View own transactions" ON transactions;
DROP POLICY IF EXISTS "Insert own transactions" ON transactions;
DROP POLICY IF EXISTS "Update own transactions" ON transactions;
DROP POLICY IF EXISTS "Delete own transactions" ON transactions;

CREATE POLICY "Shared view transactions" ON transactions
    FOR SELECT USING (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));
CREATE POLICY "Shared insert transactions" ON transactions
    FOR INSERT WITH CHECK (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));
CREATE POLICY "Shared update transactions" ON transactions
    FOR UPDATE USING (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));
CREATE POLICY "Shared delete transactions" ON transactions
    FOR DELETE USING (organization_id IN (SELECT organization_id FROM profiles WHERE id = auth.uid()));
