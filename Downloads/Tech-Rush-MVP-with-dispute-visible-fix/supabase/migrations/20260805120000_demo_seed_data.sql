-- =========================================================================
-- MIGRATION 20260805120000: KAAMSETU DEMO SEED DATA (Name & Full Name Compatibility)
-- Re-runnable script to seed realistic Indian MVP demo data into Supabase
-- =========================================================================

BEGIN;

-- 0A. ENSURE ALL TABLES & COLUMNS EXIST (Auto-Patch Remote Schema)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS full_name TEXT DEFAULT 'User';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'employer';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS street_address TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS locality TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS city TEXT DEFAULT 'BLR';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS pincode TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS photo_url TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS skills TEXT[] DEFAULT '{}';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS daily_rate NUMERIC DEFAULT 650.0;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS dispatch_radius_km NUMERIC DEFAULT 15.0;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS availability_status TEXT DEFAULT 'available';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

ALTER TABLE public.profiles ALTER COLUMN name DROP NOT NULL;

CREATE TABLE IF NOT EXISTS public.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS employer_id UUID;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS price NUMERIC DEFAULT 0;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS original_price NUMERIC;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'open';
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS rating NUMERIC DEFAULT 5.0;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS review_count INTEGER DEFAULT 0;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS location TEXT;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS date TEXT DEFAULT 'Today';
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS scheduled_date TIMESTAMPTZ DEFAULT now();
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS employer_name TEXT DEFAULT 'Employer';
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS worker_name TEXT;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT true;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS urgent BOOLEAN DEFAULT false;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS image_url TEXT;

CREATE TABLE IF NOT EXISTS public.applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.applications ADD COLUMN IF NOT EXISTS job_id UUID;
ALTER TABLE public.applications ADD COLUMN IF NOT EXISTS worker_id UUID;
ALTER TABLE public.applications ADD COLUMN IF NOT EXISTS worker_name TEXT DEFAULT 'Worker';
ALTER TABLE public.applications ADD COLUMN IF NOT EXISTS worker_phone TEXT DEFAULT '';
ALTER TABLE public.applications ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'interested';

CREATE TABLE IF NOT EXISTS public.reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS job_id UUID;
ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS worker_id UUID;
ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS employer_id UUID;
ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS rating INTEGER DEFAULT 5;
ALTER TABLE public.reviews ADD COLUMN IF NOT EXISTS comment TEXT;

CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS user_id UUID;
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'system';
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS body TEXT;
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS related_job_id UUID;
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS is_read BOOLEAN DEFAULT false;


-- 0B. CLEANUP PREVIOUS DEMO SEED DATA
DELETE FROM public.notifications 
WHERE id::text LIKE 'c0000000%' 
   OR user_id::text LIKE 'e0000000%' 
   OR user_id::text LIKE 'f0000000%';

DELETE FROM public.reviews 
WHERE id::text LIKE 'b0000000%' 
   OR employer_id::text LIKE 'e0000000%' 
   OR worker_id::text LIKE 'f0000000%';

DELETE FROM public.applications 
WHERE id::text LIKE 'a0000000%' 
   OR worker_id::text LIKE 'f0000000%';

DELETE FROM public.jobs 
WHERE id::text LIKE 'd0000000%' 
   OR employer_id::text LIKE 'e0000000%';

DELETE FROM public.profiles 
WHERE id::text LIKE 'e0000000%' 
   OR id::text LIKE 'f0000000%';

DO $$ BEGIN
    DELETE FROM auth.users WHERE id::text LIKE 'e0000000%' OR id::text LIKE 'f0000000%';
EXCEPTION WHEN OTHERS THEN
END $$;

-- 1. AUTH USERS PROVISIONING
INSERT INTO auth.users (
    id, instance_id, aud, role, email, encrypted_password, 
    email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at
) VALUES 
('e0000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'sharma.household@kaamsetu.app', '$2a$10$abcdefghijklmnopqrstuv', now(), '{"provider":"email","providers":["email"]}', '{"name":"Sharma Household"}', now(), now()),
('e0000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000002', 'authenticated', 'authenticated', 'ananya.rao@kaamsetu.app', '$2a$10$abcdefghijklmnopqrstuv', now(), '{"provider":"email","providers":["email"]}', '{"name":"Ananya Rao"}', now(), now()),
('e0000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000003', 'authenticated', 'authenticated', 'rajesh.varma@kaamsetu.app', '$2a$10$abcdefghijklmnopqrstuv', now(), '{"provider":"email","providers":["email"]}', '{"name":"Rajesh Varma"}', now(), now()),
('e0000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000004', 'authenticated', 'authenticated', 'sunita.mehta@kaamsetu.app', '$2a$10$abcdefghijklmnopqrstuv', now(), '{"provider":"email","providers":["email"]}', '{"name":"Sunita Mehta"}', now(), now()),

('f0000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000005', 'authenticated', 'authenticated', 'ramesh.painter@kaamsetu.app', '$2a$10$abcdefghijklmnopqrstuv', now(), '{"provider":"email","providers":["email"]}', '{"name":"Ramesh Kumar"}', now(), now()),
('f0000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000006', 'authenticated', 'authenticated', 'suresh.electrician@kaamsetu.app', '$2a$10$abcdefghijklmnopqrstuv', now(), '{"provider":"email","providers":["email"]}', '{"name":"Suresh Patel"}', now(), now()),
('f0000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000007', 'authenticated', 'authenticated', 'lakshmi.cleaner@kaamsetu.app', '$2a$10$abcdefghijklmnopqrstuv', now(), '{"provider":"email","providers":["email"]}', '{"name":"Lakshmi Devi"}', now(), now()),
('f0000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000008', 'authenticated', 'authenticated', 'vikram.plumber@kaamsetu.app', '$2a$10$abcdefghijklmnopqrstuv', now(), '{"provider":"email","providers":["email"]}', '{"name":"Vikram Singh"}', now(), now()),
('f0000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000009', 'authenticated', 'authenticated', 'priya.gardener@kaamsetu.app', '$2a$10$abcdefghijklmnopqrstuv', now(), '{"provider":"email","providers":["email"]}', '{"name":"Priya Nair"}', now(), now())
ON CONFLICT (id) DO NOTHING;

-- 2. PUBLIC PROFILES POPULATION
INSERT INTO public.profiles (
    id, name, full_name, phone, email, role, street_address, locality, city, pincode, photo_url
) VALUES
('e0000000-0000-0000-0000-000000000001', 'Sharma Household', 'Sharma Household', '+919876543210', 'sharma.household@kaamsetu.app', 'employer', 'Flat 302, Green Acres', 'Indiranagar', 'BLR', '560038', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150'),
('e0000000-0000-0000-0000-000000000002', 'Ananya Rao', 'Ananya Rao', '+919876543211', 'ananya.rao@kaamsetu.app', 'employer', 'Villa 14, Palm Grove', 'Koramangala 4th Block', 'BLR', '560034', 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150'),
('e0000000-0000-0000-0000-000000000003', 'Rajesh Varma', 'Rajesh Varma', '+919876543212', 'rajesh.varma@kaamsetu.app', 'employer', 'No. 88, 27th Main', 'HSR Layout Sector 1', 'BLR', '560102', 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150'),
('e0000000-0000-0000-0000-000000000004', 'Sunita Mehta', 'Sunita Mehta', '+919876543213', 'sunita.mehta@kaamsetu.app', 'employer', 'Apt 4B, Heritage Enclave', 'Jayanagar 9th Block', 'BLR', '560069', 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, full_name = EXCLUDED.full_name, locality = EXCLUDED.locality;

INSERT INTO public.profiles (
    id, name, full_name, phone, email, role, street_address, locality, city, pincode, photo_url,
    skills, daily_rate, dispatch_radius_km, availability_status
) VALUES
('f0000000-0000-0000-0000-000000000001', 'Ramesh Kumar', 'Ramesh Kumar', '+919123456780', 'ramesh.painter@kaamsetu.app', 'worker', 'No. 12, Old Airport Rd', 'Murugeshpalya', 'BLR', '560017', 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150', ARRAY['House Painting', 'Wall Tiling', 'Waterproofing'], 850.0, 12.0, 'available'),
('f0000000-0000-0000-0000-000000000002', 'Suresh Patel', 'Suresh Patel', '+919123456781', 'suresh.electrician@kaamsetu.app', 'worker', 'No. 45, Tavarekere Main', 'BTM Layout', 'BLR', '560029', 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150', ARRAY['Wiring', 'MCB Repairs', 'Appliance Servicing'], 950.0, 15.0, 'available'),
('f0000000-0000-0000-0000-000000000003', 'Lakshmi Devi', 'Lakshmi Devi', '+919123456782', 'lakshmi.cleaner@kaamsetu.app', 'worker', 'Slum Tenement 18', 'Ejipura', 'BLR', '560047', 'https://images.unsplash.com/photo-1567532939604-b6b5b0db2604?w=150', ARRAY['Kitchen Deep Clean', 'South Indian Cooking', 'Carpet Steam Wash'], 700.0, 10.0, 'available'),
('f0000000-0000-0000-0000-000000000004', 'Vikram Singh', 'Vikram Singh', '+919123456783', 'vikram.plumber@kaamsetu.app', 'worker', 'Block C, Madiwala Rd', 'Madiwala', 'BLR', '560068', 'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150', ARRAY['Pipe Leak Repairs', 'Sanitary Fitting', 'Tap Repair'], 900.0, 18.0, 'available'),
('f0000000-0000-0000-0000-000000000005', 'Priya Nair', 'Priya Nair', '+919123456784', 'priya.gardener@kaamsetu.app', 'worker', 'No. 77, Bellandur Rd', 'Bellandur', 'BLR', '560103', 'https://images.unsplash.com/photo-1580489944761-15a19d654956?w=150', ARRAY['Lawn Mowing', 'Hedge Trimming', 'Plant Care'], 750.0, 15.0, 'available')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, full_name = EXCLUDED.full_name, skills = EXCLUDED.skills;

-- 3. DEMO JOBS DISPATCH REGISTRY
INSERT INTO public.jobs (
    id, employer_id, title, category, description, price, original_price,
    status, rating, review_count, location, date, scheduled_date, employer_name, worker_name, verified, urgent
) VALUES
('d0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Living Room Wall Painting & Asian Paints Touchup', 'Painting', 'Looking for an experienced painter to complete two accent wall coats using Asian Paints Royal. Primer included.', 1800.0, 2200.0, 'open', 4.9, 14, 'Indiranagar 100ft Rd', 'Today, 2:00 PM', now() + interval '2 hours', 'Sharma Household', NULL, true, true),
('d0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-000000000002', 'Balcony Waterproofing & Texture Coating', 'Painting', 'Balcony ceiling has minor dampness. Need crack filling & Dr. Fixit waterproof coating.', 2200.0, 2500.0, 'assigned', 4.8, 9, 'Koramangala 4th Block', 'Tomorrow, 10:00 AM', now() + interval '1 day', 'Ananya Rao', 'Ramesh Kumar', true, false),
('d0000000-0000-0000-0000-000000000003', 'e0000000-0000-0000-0000-000000000003', 'Full 2BHK Flat Wall Primer & Wood Polish', 'Painting', 'Completed complete interior primer coat and door varnish polish.', 3500.0, 4000.0, 'completed', 5.0, 22, 'HSR Layout Sector 1', 'Yesterday', now() - interval '1 day', 'Rajesh Varma', 'Ramesh Kumar', true, false),

('d0000000-0000-0000-0000-000000000004', 'e0000000-0000-0000-0000-000000000001', '3BHK Post-Renovation Deep Cleaning', 'Cleaning', 'Urgent post-renovation dust cleanup. Includes window glass wiping, balcony scrubbing & floor mopping.', 1200.0, 1500.0, 'open', 4.9, 18, 'Indiranagar 12th Main', 'Today, 4:00 PM', now() + interval '4 hours', 'Sharma Household', NULL, true, true),
('d0000000-0000-0000-0000-000000000005', 'e0000000-0000-0000-0000-000000000004', 'Modular Kitchen & Chimney Degreasing', 'Cleaning', 'Deep oil stain removal from kitchen tiles, chimney filters, and cabinet exteriors.', 850.0, 1000.0, 'assigned', 4.7, 11, 'Jayanagar 9th Block', 'Tomorrow, 11:30 AM', now() + interval '1 day', 'Sunita Mehta', 'Lakshmi Devi', true, false),
('d0000000-0000-0000-0000-000000000006', 'e0000000-0000-0000-0000-000000000002', 'Sofa Fabric & Carpet Steam Clean', 'Cleaning', 'Steam wash for 5-seater L-shaped sofa and 6x4 carpet.', 900.0, 1100.0, 'completed', 5.0, 15, 'Koramangala 4th Block', '2 days ago', now() - interval '2 days', 'Ananya Rao', 'Lakshmi Devi', true, false),

('d0000000-0000-0000-0000-000000000007', 'e0000000-0000-0000-0000-000000000003', 'Overhead Water Tank Leakage Fix', 'Plumbing', 'Water tank overflow sensor and valve leak needs immediate repair before evening.', 650.0, 800.0, 'open', 4.8, 12, 'HSR Layout Sector 1', 'Today, Urgent', now() + interval '1 hour', 'Rajesh Varma', NULL, true, true),
('d0000000-0000-0000-0000-000000000008', 'e0000000-0000-0000-0000-000000000001', 'Under-Sink Pipe & Tap Replacement', 'Plumbing', 'Replaced leaking kitchen sink trap pipe and installed fresh Jaquar chrome tap.', 1400.0, 1600.0, 'completed', 4.7, 8, 'Indiranagar', '3 days ago', now() - interval '3 days', 'Sharma Household', 'Vikram Singh', true, false),

('d0000000-0000-0000-0000-000000000009', 'e0000000-0000-0000-0000-000000000004', 'Weekend House Gathering Banquet Chef', 'Cooking', 'Prepare traditional South Indian feast (Biryani, Starters, Payasam) for 15 guests.', 1500.0, 1800.0, 'open', 5.0, 20, 'Jayanagar 9th Block', 'Saturday, 12:00 PM', now() + interval '3 days', 'Sunita Mehta', NULL, true, false),
('d0000000-0000-0000-0000-000000000010', 'e0000000-0000-0000-0000-000000000002', 'Daily Dinner Meal Prep & Chapati Making', 'Cooking', 'Prepare healthy dinner meals (Roti, Sabzi, Dal, Salad) for family of 4.', 800.0, 950.0, 'assigned', 4.9, 16, 'Koramangala 4th Block', 'Today, 6:00 PM', now() + interval '6 hours', 'Ananya Rao', 'Lakshmi Devi', true, false),

('d0000000-0000-0000-0000-000000000011', 'e0000000-0000-0000-0000-000000000001', 'Terrace Organic Garden Setup & Pruning', 'Gardening', 'Trimming potted plants, adding Vermicompost, and setting up drip drip lines.', 750.0, 900.0, 'open', 4.9, 7, 'Indiranagar 100ft Rd', 'Tomorrow, 8:00 AM', now() + interval '1 day', 'Sharma Household', NULL, true, false),
('d0000000-0000-0000-0000-000000000012', 'e0000000-0000-0000-0000-000000000003', 'Lawn Trimming & Hedge Shaping', 'Gardening', 'Mowed 500 sq ft front lawn and shaped perimeter hedges neatly.', 1100.0, 1300.0, 'completed', 5.0, 13, 'HSR Layout Sector 1', 'Yesterday', now() - interval '1 day', 'Rajesh Varma', 'Priya Nair', true, false),

('d0000000-0000-0000-0000-000000000013', 'e0000000-0000-0000-0000-000000000002', 'Main Switchboard & MCB Tripping Diagnostic', 'Electrical', 'Power trips whenever AC is turned on. Need licensed electrician to inspect distribution box.', 1100.0, 1400.0, 'open', 4.8, 19, 'Koramangala 4th Block', 'Today, Urgent', now() + interval '1 hour', 'Ananya Rao', NULL, true, true),
('d0000000-0000-0000-0000-000000000014', 'e0000000-0000-0000-0000-000000000004', 'Decorative Chandelier & Ceiling Fan Assembly', 'Electrical', 'Assemble and safely mount heavy crystal chandelier in living room hall.', 700.0, 850.0, 'assigned', 4.8, 10, 'Jayanagar 9th Block', 'Tomorrow, 3:00 PM', now() + interval '1 day', 'Sunita Mehta', 'Suresh Patel', true, false)
ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, status = EXCLUDED.status;

-- 4. APPLICATIONS SEEDING
INSERT INTO public.applications (
    id, job_id, worker_id, worker_name, worker_phone, status, created_at
) VALUES
('a0000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000001', 'Ramesh Kumar', '+919123456780', 'interested', now() - interval '2 hours'),
('a0000000-0000-0000-0000-000000000002', 'd0000000-0000-0000-0000-000000000002', 'f0000000-0000-0000-0000-000000000001', 'Ramesh Kumar', '+919123456780', 'assigned', now() - interval '5 hours'),
('a0000000-0000-0000-0000-000000000003', 'd0000000-0000-0000-0000-000000000004', 'f0000000-0000-0000-0000-000000000003', 'Lakshmi Devi', '+919123456782', 'interested', now() - interval '1 hour'),
('a0000000-0000-0000-0000-000000000004', 'd0000000-0000-0000-0000-000000000005', 'f0000000-0000-0000-0000-000000000003', 'Lakshmi Devi', '+919123456782', 'assigned', now() - interval '4 hours'),
('a0000000-0000-0000-0000-000000000005', 'd0000000-0000-0000-0000-000000000007', 'f0000000-0000-0000-0000-000000000004', 'Vikram Singh', '+919123456783', 'interested', now() - interval '30 minutes'),
('a0000000-0000-0000-0000-000000000006', 'd0000000-0000-0000-0000-000000000010', 'f0000000-0000-0000-0000-000000000003', 'Lakshmi Devi', '+919123456782', 'assigned', now() - interval '1 day'),
('a0000000-0000-0000-0000-000000000007', 'd0000000-0000-0000-0000-000000000013', 'f0000000-0000-0000-0000-000000000002', 'Suresh Patel', '+919123456781', 'interested', now() - interval '15 minutes'),
('a0000000-0000-0000-0000-000000000008', 'd0000000-0000-0000-0000-000000000014', 'f0000000-0000-0000-0000-000000000002', 'Suresh Patel', '+919123456781', 'assigned', now() - interval '3 hours')
ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status;

-- 5. REVIEWS SEEDING
INSERT INTO public.reviews (
    id, job_id, worker_id, employer_id, rating, comment, created_at
) VALUES
('b0000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000003', 'f0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000003', 5, 'Flawless primer and wall finish! Arrived on time and cleaned up completely.', now() - interval '1 day'),
('b0000000-0000-0000-0000-000000000002', 'd0000000-0000-0000-0000-000000000006', 'f0000000-0000-0000-0000-000000000003', 'e0000000-0000-0000-0000-000000000002', 5, 'Amazing steam wash, sofa looks brand new. Highly recommended!', now() - interval '2 days'),
('b0000000-0000-0000-0000-000000000003', 'd0000000-0000-0000-0000-000000000008', 'f0000000-0000-0000-0000-000000000004', 'e0000000-0000-0000-0000-000000000001', 4, 'Fixed the leaking pipe under the sink quickly. Professional work.', now() - interval '3 days'),
('b0000000-0000-0000-0000-000000000004', 'd0000000-0000-0000-0000-000000000012', 'f0000000-0000-0000-0000-000000000005', 'e0000000-0000-0000-0000-000000000003', 5, 'Transformed our terrace garden. Soil fertilizing made plants bloom in days.', now() - interval '1 day')
ON CONFLICT (id) DO UPDATE SET rating = EXCLUDED.rating;

-- 6. NOTIFICATIONS SEEDING
INSERT INTO public.notifications (
    id, user_id, type, title, body, related_job_id, is_read, created_at
) VALUES
('c0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'application_received', 'New Application Received', 'Ramesh Kumar submitted interest for "Living Room Wall Painting"', 'd0000000-0000-0000-0000-000000000001', false, now() - interval '2 hours'),
('c0000000-0000-0000-0000-000000000002', 'f0000000-0000-0000-0000-000000000001', 'job_accepted', 'Job Dispatch Assigned!', 'Ananya Rao accepted your bid for "Balcony Waterproofing"', 'd0000000-0000-0000-0000-000000000002', false, now() - interval '5 hours'),
('c0000000-0000-0000-0000-000000000003', 'f0000000-0000-0000-0000-000000000001', 'review_received', 'New 5-Star Review Received ★★★★★', 'Rajesh Varma posted a 5-star review: "Flawless primer and wall finish!"', 'd0000000-0000-0000-0000-000000000003', true, now() - interval '1 day'),
('c0000000-0000-0000-0000-000000000004', 'e0000000-0000-0000-0000-000000000001', 'application_received', 'New Application Received', 'Lakshmi Devi applied for "3BHK Post-Renovation Deep Clean"', 'd0000000-0000-0000-0000-000000000004', false, now() - interval '1 hour'),
('c0000000-0000-0000-0000-000000000005', 'f0000000-0000-0000-0000-000000000002', 'job_accepted', 'Dispatch Assigned', 'Sunita Mehta assigned "Ceiling Fan & Chandelier Installation" to you.', 'd0000000-0000-0000-0000-000000000014', false, now() - interval '3 hours'),
('c0000000-0000-0000-0000-000000000006', 'f0000000-0000-0000-0000-000000000003', 'job_completed', 'Job Completed & Payout Verified', 'Your job "Carpet Steam Clean" was marked completed. ₹900 added.', 'd0000000-0000-0000-0000-000000000006', true, now() - interval '2 days'),
('c0000000-0000-0000-0000-000000000007', 'e0000000-0000-0000-0000-000000000001', 'system', 'KaamSetu Trust Guarantee Active', 'Your employer account is verified for instant 60-second dispatches.', NULL, true, now() - interval '3 days')
ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;

COMMIT;
