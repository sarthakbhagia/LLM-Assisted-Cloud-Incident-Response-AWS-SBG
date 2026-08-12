-- =========================================================================
-- HOTFIX: Ensure all jobs table columns exist and RLS is correct
-- Run in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/movsaslnwjqbtdynvcwb/sql/new
-- =========================================================================

-- Ensure jobs table exists with all required columns
CREATE TABLE IF NOT EXISTS public.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employer_id UUID,
    title TEXT,
    category TEXT,
    description TEXT,
    price NUMERIC DEFAULT 0,
    original_price NUMERIC,
    status TEXT DEFAULT 'open',
    rating NUMERIC DEFAULT 5.0,
    review_count INTEGER DEFAULT 0,
    location TEXT,
    date TEXT DEFAULT 'Today',
    scheduled_date TIMESTAMPTZ DEFAULT now(),
    employer_name TEXT DEFAULT 'Employer',
    worker_name TEXT,
    verified BOOLEAN DEFAULT true,
    urgent BOOLEAN DEFAULT false,
    image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Add any missing columns safely
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
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS employer_name TEXT DEFAULT 'Employer';
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS worker_name TEXT;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT true;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS urgent BOOLEAN DEFAULT false;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS image_url TEXT;

-- Enable RLS
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

-- Drop existing RLS policies and recreate cleanly
DROP POLICY IF EXISTS "Anyone Can Read Jobs" ON public.jobs;
DROP POLICY IF EXISTS "Employers Can Insert Jobs" ON public.jobs;
DROP POLICY IF EXISTS "Employers and Workers Can Update Jobs" ON public.jobs;

-- SELECT: anyone can read
CREATE POLICY "Anyone Can Read Jobs" ON public.jobs
  FOR SELECT TO authenticated, anon USING (true);

-- INSERT: authenticated user's auth.uid() must match employer_id
CREATE POLICY "Employers Can Insert Jobs" ON public.jobs
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = employer_id);

-- UPDATE: employer or assigned worker can update
CREATE POLICY "Employers and Workers Can Update Jobs" ON public.jobs
  FOR UPDATE TO authenticated
  USING (
    auth.uid() = employer_id OR
    EXISTS (
      SELECT 1 FROM public.applications
      WHERE applications.job_id = jobs.id
        AND applications.worker_id = auth.uid()
        AND applications.status = 'assigned'
    )
  );

-- Also fix profiles table missing columns (from migration 000001)
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS full_name TEXT DEFAULT 'User';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'employer';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS city TEXT DEFAULT 'BLR';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS street_address TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS locality TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS pincode TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS skills TEXT[] DEFAULT '{}';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS daily_rate NUMERIC DEFAULT 650.0;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS dispatch_radius_km NUMERIC DEFAULT 15.0;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS availability_status TEXT DEFAULT 'available';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS photo_url TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

