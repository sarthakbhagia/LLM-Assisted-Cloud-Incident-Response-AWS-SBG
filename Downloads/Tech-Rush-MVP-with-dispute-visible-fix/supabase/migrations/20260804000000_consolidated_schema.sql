-- =========================================================================
-- KAAMSETU CONSOLIDATED BACKEND MIGRATION
-- Tables: profiles, jobs, applications, reviews, work_samples, notifications
-- =========================================================================

-- -------------------------------------------------------------------------
-- 1. PROFILES TABLE
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL DEFAULT 'User',
    phone TEXT,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'employer', -- 'employer' or 'worker'
    street_address TEXT,
    locality TEXT,
    city TEXT DEFAULT 'BLR',
    pincode TEXT,
    photo_url TEXT,
    skills TEXT[] DEFAULT '{}', -- worker only: skills array
    daily_rate NUMERIC DEFAULT 650.0, -- worker only
    dispatch_radius_km NUMERIC DEFAULT 15.0, -- worker only
    availability_status TEXT DEFAULT 'available', -- worker only: 'available' or 'busy'
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Schema Alters for existing tables
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS full_name TEXT DEFAULT 'User';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'employer';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS photo_url TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS skills TEXT[] DEFAULT '{}';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS daily_rate NUMERIC DEFAULT 650.0;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS dispatch_radius_km NUMERIC DEFAULT 15.0;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS availability_status TEXT DEFAULT 'available';

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'profiles' AND policyname = 'Public Read Profiles') THEN
        CREATE POLICY "Public Read Profiles" ON public.profiles FOR SELECT TO authenticated, anon USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'profiles' AND policyname = 'Users Can Insert Own Profile') THEN
        CREATE POLICY "Users Can Insert Own Profile" ON public.profiles FOR INSERT TO authenticated WITH CHECK (auth.uid() = id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'profiles' AND policyname = 'Users Can Update Own Profile') THEN
        CREATE POLICY "Users Can Update Own Profile" ON public.profiles FOR UPDATE TO authenticated USING (auth.uid() = id);
    END IF;
END $$;

-- -------------------------------------------------------------------------
-- 2. JOBS TABLE
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employer_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    price NUMERIC NOT NULL,
    original_price NUMERIC,
    status TEXT NOT NULL DEFAULT 'open', -- 'open', 'assigned', 'completed'
    rating NUMERIC DEFAULT 5.0,
    review_count INTEGER DEFAULT 0,
    location TEXT NOT NULL,
    date TEXT DEFAULT 'Today',
    scheduled_date TIMESTAMPTZ DEFAULT now(),
    employer_name TEXT NOT NULL DEFAULT 'Employer',
    worker_name TEXT,
    verified BOOLEAN DEFAULT true,
    urgent BOOLEAN DEFAULT false,
    image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS employer_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE;
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

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'jobs' AND policyname = 'Anyone Can Read Jobs') THEN
        CREATE POLICY "Anyone Can Read Jobs" ON public.jobs FOR SELECT TO authenticated, anon USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'jobs' AND policyname = 'Employers Can Insert Jobs') THEN
        CREATE POLICY "Employers Can Insert Jobs" ON public.jobs FOR INSERT TO authenticated WITH CHECK (auth.uid() = employer_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'jobs' AND policyname = 'Employers and Workers Can Update Jobs') THEN
        CREATE POLICY "Employers and Workers Can Update Jobs" ON public.jobs FOR UPDATE TO authenticated USING (
            auth.uid() = employer_id OR EXISTS (
                SELECT 1 FROM public.applications 
                WHERE applications.job_id = jobs.id 
                AND applications.worker_id = auth.uid() 
                AND applications.status = 'assigned'
            )
        );
    END IF;
END $$;

-- -------------------------------------------------------------------------
-- 3. APPLICATIONS TABLE
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    worker_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    worker_name TEXT NOT NULL DEFAULT 'Worker',
    worker_phone TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'interested', -- 'interested', 'assigned', 'rejected'
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'applications' AND policyname = 'Job Owners and Applicants Can Read Applications') THEN
        CREATE POLICY "Job Owners and Applicants Can Read Applications" ON public.applications FOR SELECT TO authenticated USING (
            auth.uid() = worker_id OR EXISTS (
                SELECT 1 FROM public.jobs WHERE jobs.id = applications.job_id AND jobs.employer_id = auth.uid()
            )
        );
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'applications' AND policyname = 'Workers Can Apply To Jobs') THEN
        CREATE POLICY "Workers Can Apply To Jobs" ON public.applications FOR INSERT TO authenticated WITH CHECK (auth.uid() = worker_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'applications' AND policyname = 'Job Owners and Applicants Can Update Applications') THEN
        CREATE POLICY "Job Owners and Applicants Can Update Applications" ON public.applications FOR UPDATE TO authenticated USING (
            auth.uid() = worker_id OR EXISTS (
                SELECT 1 FROM public.jobs WHERE jobs.id = applications.job_id AND jobs.employer_id = auth.uid()
            )
        );
    END IF;
END $$;

-- -------------------------------------------------------------------------
-- 4. REVIEWS TABLE
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    worker_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    employer_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT unique_job_employer_review UNIQUE (job_id, employer_id)
);

ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'reviews' AND policyname = 'Anyone can read reviews') THEN
        CREATE POLICY "Anyone can read reviews" ON public.reviews FOR SELECT TO authenticated, anon USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'reviews' AND policyname = 'Employers can insert review for completed jobs') THEN
        CREATE POLICY "Employers can insert review for completed jobs" ON public.reviews FOR INSERT TO authenticated
        WITH CHECK (
            auth.uid() = employer_id
            AND EXISTS (
                SELECT 1 FROM public.profiles
                WHERE id = auth.uid()
                AND role = 'employer'
            )
            AND EXISTS (
                SELECT 1 FROM public.jobs
                WHERE id = job_id
                AND employer_id = auth.uid()
                AND status = 'completed'
            )
        );
    END IF;
END $$;

-- -------------------------------------------------------------------------
-- 5. WORK SAMPLES TABLE
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.work_samples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.work_samples ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'work_samples' AND policyname = 'Public Read for work_samples') THEN
        CREATE POLICY "Public Read for work_samples" ON public.work_samples FOR SELECT TO authenticated, anon USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'work_samples' AND policyname = 'Worker insert for work_samples') THEN
        CREATE POLICY "Worker insert for work_samples" ON public.work_samples FOR INSERT TO authenticated WITH CHECK (auth.uid() = worker_id);
    END IF;
END $$;

-- -------------------------------------------------------------------------
-- 6. NOTIFICATIONS TABLE
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    type TEXT NOT NULL, -- 'application_received', 'job_accepted', 'status_update', 'system'
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    related_job_id UUID REFERENCES public.jobs(id) ON DELETE SET NULL,
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'notifications' AND policyname = 'Users Can Read Own Notifications') THEN
        CREATE POLICY "Users Can Read Own Notifications" ON public.notifications FOR SELECT TO authenticated USING (auth.uid() = user_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'notifications' AND policyname = 'Users or System Can Insert Notifications') THEN
        CREATE POLICY "Users or System Can Insert Notifications" ON public.notifications FOR INSERT TO authenticated WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'notifications' AND policyname = 'Users Can Update Own Notifications') THEN
        CREATE POLICY "Users Can Update Own Notifications" ON public.notifications FOR UPDATE TO authenticated USING (auth.uid() = user_id);
    END IF;
END $$;
