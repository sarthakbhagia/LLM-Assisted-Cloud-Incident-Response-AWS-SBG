-- =========================================================================
-- KAAMSETU COMPLETE BACKEND MIGRATION: STAGES 1 & 2 + SCHEMA ALTERS
-- =========================================================================

-- -------------------------------------------------------------------------
-- 1. BASE SCHEMAS: profiles, jobs, applications (with Column Alters)
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL DEFAULT 'User',
    phone TEXT,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'employer',
    street_address TEXT,
    locality TEXT,
    city TEXT DEFAULT 'BLR',
    pincode TEXT,
    photo_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS full_name TEXT DEFAULT 'User';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'employer';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS photo_url TEXT;

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'profiles' AND policyname = 'Public Read Profiles') THEN
        CREATE POLICY "Public Read Profiles" ON public.profiles FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'profiles' AND policyname = 'Users Can Insert Own Profile') THEN
        CREATE POLICY "Users Can Insert Own Profile" ON public.profiles FOR INSERT TO authenticated WITH CHECK (auth.uid() = id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'profiles' AND policyname = 'Users Can Update Own Profile') THEN
        CREATE POLICY "Users Can Update Own Profile" ON public.profiles FOR UPDATE TO authenticated USING (auth.uid() = id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employer_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    price NUMERIC NOT NULL,
    original_price NUMERIC,
    status TEXT NOT NULL DEFAULT 'open',
    rating NUMERIC DEFAULT 5.0,
    review_count INTEGER DEFAULT 0,
    location TEXT NOT NULL,
    date TEXT DEFAULT 'Today',
    employer_name TEXT NOT NULL DEFAULT 'Employer',
    worker_name TEXT,
    verified BOOLEAN DEFAULT true,
    urgent BOOLEAN DEFAULT false,
    image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS employer_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS original_price NUMERIC;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS review_count INTEGER DEFAULT 0;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS employer_name TEXT DEFAULT 'Employer';
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS worker_name TEXT;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT true;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS urgent BOOLEAN DEFAULT false;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS image_url TEXT;

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'jobs' AND policyname = 'Anyone Authenticated Can Read Jobs') THEN
        CREATE POLICY "Anyone Authenticated Can Read Jobs" ON public.jobs FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'jobs' AND policyname = 'Employers Can Insert Jobs') THEN
        CREATE POLICY "Employers Can Insert Jobs" ON public.jobs FOR INSERT TO authenticated WITH CHECK (auth.uid() = employer_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'jobs' AND policyname = 'Employers Can Update Own Jobs') THEN
        CREATE POLICY "Employers Can Update Own Jobs" ON public.jobs FOR UPDATE TO authenticated USING (auth.uid() = employer_id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES public.jobs(id) ON DELETE CASCADE,
    worker_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    worker_name TEXT NOT NULL,
    worker_phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'interested',
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'applications' AND policyname = 'Anyone Authenticated Can Read Applications') THEN
        CREATE POLICY "Anyone Authenticated Can Read Applications" ON public.applications FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'applications' AND policyname = 'Workers Can Apply To Jobs') THEN
        CREATE POLICY "Workers Can Apply To Jobs" ON public.applications FOR INSERT TO authenticated WITH CHECK (auth.uid() = worker_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'applications' AND policyname = 'Users Can Update Applications') THEN
        CREATE POLICY "Users Can Update Applications" ON public.applications FOR UPDATE TO authenticated USING (true);
    END IF;
END $$;

-- -------------------------------------------------------------------------
-- 2. STAGE 1: Reviews Table & Asymmetric RLS (Employer -> Worker ONLY)
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
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'reviews' AND policyname = 'Authenticated users can read reviews') THEN
        CREATE POLICY "Authenticated users can read reviews"
        ON public.reviews FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'reviews' AND policyname = 'Employers can insert review for completed jobs') THEN
        CREATE POLICY "Employers can insert review for completed jobs"
        ON public.reviews FOR INSERT TO authenticated
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
-- 3. STAGE 2: Storage Buckets & Policies
-- -------------------------------------------------------------------------

INSERT INTO storage.buckets (id, name, public)
VALUES ('profile-photos', 'profile-photos', true)
ON CONFLICT (id) DO UPDATE SET public = true;

INSERT INTO storage.buckets (id, name, public)
VALUES ('job-images', 'job-images', true)
ON CONFLICT (id) DO UPDATE SET public = true;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Public Read for profile-photos') THEN
        CREATE POLICY "Public Read for profile-photos"
        ON storage.objects FOR SELECT TO public USING (bucket_id = 'profile-photos');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Owner write for profile-photos') THEN
        CREATE POLICY "Owner write for profile-photos"
        ON storage.objects FOR INSERT TO authenticated
        WITH CHECK (
            bucket_id = 'profile-photos'
            AND (storage.foldername(name))[1] = auth.uid()::text
        );
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Public Read for job-images') THEN
        CREATE POLICY "Public Read for job-images"
        ON storage.objects FOR SELECT TO public USING (bucket_id = 'job-images');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Employer write for job-images') THEN
        CREATE POLICY "Employer write for job-images"
        ON storage.objects FOR INSERT TO authenticated
        WITH CHECK (
            bucket_id = 'job-images'
            AND EXISTS (
                SELECT 1 FROM public.profiles
                WHERE id = auth.uid()
                AND role = 'employer'
            )
        );
    END IF;
END $$;

-- -------------------------------------------------------------------------
-- 4. STAGE 3: Work Samples Gallery Table & Policies
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
        CREATE POLICY "Public Read for work_samples"
        ON public.work_samples FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'work_samples' AND policyname = 'Worker insert for work_samples') THEN
        CREATE POLICY "Worker insert for work_samples"
        ON public.work_samples FOR INSERT TO authenticated WITH CHECK (auth.uid() = worker_id);
    END IF;
END $$;
