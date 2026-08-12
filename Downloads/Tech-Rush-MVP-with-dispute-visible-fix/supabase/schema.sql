-- KaamSetu Complete & Bulletproof Database Schema for Supabase (PostgreSQL)
-- IMPORTANT: Run this ENTIRE file from top to bottom in the Supabase SQL Editor.

-- ==========================================
-- STEP 1: CREATE TABLES
-- ==========================================

-- 1. PROFILES TABLE
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    phone TEXT,
    role TEXT NOT NULL CHECK (role IN ('worker', 'household')),
    photo_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. WORKER PROFILES TABLE
CREATE TABLE IF NOT EXISTS public.worker_profiles (
    id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    skills TEXT[] NOT NULL DEFAULT '{}',
    expected_wage NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    availability TEXT NOT NULL DEFAULT 'available' CHECK (availability IN ('available', 'busy')),
    bio TEXT,
    rating_avg NUMERIC(3, 2) NOT NULL DEFAULT 0.00,
    rating_count INT NOT NULL DEFAULT 0,
    location TEXT
);

-- 3. JOBS TABLE
CREATE TABLE IF NOT EXISTS public.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    location TEXT NOT NULL,
    budget NUMERIC(10, 2) NOT NULL,
    job_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'assigned', 'completed', 'cancelled')),
    assigned_worker_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. JOB INTERESTS TABLE
CREATE TABLE IF NOT EXISTS public.job_interests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    worker_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'selected', 'not_selected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_job_worker_interest UNIQUE (job_id, worker_id)
);

-- 5. RATINGS TABLE
CREATE TABLE IF NOT EXISTS public.ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    from_user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    to_user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    value TEXT NOT NULL CHECK (value IN ('up', 'down')),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ==========================================
-- STEP 2: CREATE INDEXES
-- ==========================================
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);
CREATE INDEX IF NOT EXISTS idx_jobs_household ON public.jobs(household_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON public.jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_assigned_worker ON public.jobs(assigned_worker_id);
CREATE INDEX IF NOT EXISTS idx_job_interests_job ON public.job_interests(job_id);
CREATE INDEX IF NOT EXISTS idx_job_interests_worker ON public.job_interests(worker_id);
CREATE INDEX IF NOT EXISTS idx_ratings_job ON public.ratings(job_id);
CREATE INDEX IF NOT EXISTS idx_ratings_to_user ON public.ratings(to_user_id);

-- ==========================================
-- STEP 3: ENABLE ROW LEVEL SECURITY (RLS)
-- ==========================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.worker_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_interests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ratings ENABLE ROW LEVEL SECURITY;

-- ==========================================
-- STEP 4: SAFE POLICY CLEANUP & RECREATION
-- ==========================================

-- Clean up existing policies safely
DO $$
BEGIN
    -- Profiles
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'profiles') THEN
        DROP POLICY IF EXISTS "Public profiles are readable by authenticated users" ON public.profiles;
        DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
        DROP POLICY IF EXISTS "Users can insert own profile" ON public.profiles;
    END IF;

    -- Worker Profiles
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'worker_profiles') THEN
        DROP POLICY IF EXISTS "Worker profiles are readable by authenticated users" ON public.worker_profiles;
        DROP POLICY IF EXISTS "Workers can update own worker profile" ON public.worker_profiles;
        DROP POLICY IF EXISTS "Workers can insert own worker profile" ON public.worker_profiles;
    END IF;

    -- Jobs
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'jobs') THEN
        DROP POLICY IF EXISTS "Jobs are readable by authenticated users" ON public.jobs;
        DROP POLICY IF EXISTS "Households can insert jobs" ON public.jobs;
        DROP POLICY IF EXISTS "Households can update own jobs" ON public.jobs;
    END IF;

    -- Job Interests
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'job_interests') THEN
        DROP POLICY IF EXISTS "Job interests readable by involved parties" ON public.job_interests;
        DROP POLICY IF EXISTS "Workers can express interest" ON public.job_interests;
        DROP POLICY IF EXISTS "Households and workers can update interest status" ON public.job_interests;
    END IF;

    -- Ratings
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'ratings') THEN
        DROP POLICY IF EXISTS "Ratings are readable by authenticated users" ON public.ratings;
        DROP POLICY IF EXISTS "Users can create ratings" ON public.ratings;
    END IF;
END $$;

-- Create Policies

-- Profiles Policies
CREATE POLICY "Public profiles are readable by authenticated users" 
    ON public.profiles FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Users can update own profile" 
    ON public.profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "Users can insert own profile" 
    ON public.profiles FOR INSERT WITH CHECK (auth.uid() = id);

-- Worker Profiles Policies
CREATE POLICY "Worker profiles are readable by authenticated users" 
    ON public.worker_profiles FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Workers can update own worker profile" 
    ON public.worker_profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "Workers can insert own worker profile" 
    ON public.worker_profiles FOR INSERT WITH CHECK (auth.uid() = id);

-- Jobs Policies
CREATE POLICY "Jobs are readable by authenticated users" 
    ON public.jobs FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Households can insert jobs" 
    ON public.jobs FOR INSERT WITH CHECK (auth.uid() = household_id);
CREATE POLICY "Households can update own jobs" 
    ON public.jobs FOR UPDATE USING (auth.uid() = household_id);

-- Job Interests Policies
CREATE POLICY "Job interests readable by involved parties" 
    ON public.job_interests FOR SELECT USING (
        auth.uid() = worker_id OR 
        EXISTS (SELECT 1 FROM public.jobs WHERE jobs.id = job_interests.job_id AND jobs.household_id = auth.uid())
    );
CREATE POLICY "Workers can express interest" 
    ON public.job_interests FOR INSERT WITH CHECK (auth.uid() = worker_id);
CREATE POLICY "Households and workers can update interest status" 
    ON public.job_interests FOR UPDATE USING (
        auth.uid() = worker_id OR 
        EXISTS (SELECT 1 FROM public.jobs WHERE jobs.id = job_interests.job_id AND jobs.household_id = auth.uid())
    );

-- Ratings Policies
CREATE POLICY "Ratings are readable by authenticated users" 
    ON public.ratings FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Users can create ratings" 
    ON public.ratings FOR INSERT WITH CHECK (auth.uid() = from_user_id);

