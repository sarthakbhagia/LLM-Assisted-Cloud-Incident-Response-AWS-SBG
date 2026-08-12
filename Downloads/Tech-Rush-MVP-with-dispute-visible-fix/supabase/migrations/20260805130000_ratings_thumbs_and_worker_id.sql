-- =========================================================================
-- KAAMSETU MIGRATION: Thumbs-up/down Ratings Table + Profile Counters
-- + assigned_worker_id column on jobs table
-- =========================================================================

-- -------------------------------------------------------------------------
-- 1. Add rating_thumbs_up / rating_thumbs_down counters to profiles
-- -------------------------------------------------------------------------
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS rating_thumbs_up   INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS rating_thumbs_down INTEGER NOT NULL DEFAULT 0;

-- -------------------------------------------------------------------------
-- 2. Add assigned_worker_id to jobs (tracks selected worker UUID)
-- -------------------------------------------------------------------------
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS assigned_worker_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_assigned_worker ON public.jobs(assigned_worker_id);

-- -------------------------------------------------------------------------
-- 3. Create ratings table (thumbs-up / thumbs-down per completed job)
-- -------------------------------------------------------------------------
DROP TABLE IF EXISTS public.ratings CASCADE;

CREATE TABLE public.ratings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID NOT NULL REFERENCES public.jobs(id)     ON DELETE CASCADE,
    evaluator_id    UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    target_id       UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    rating_type     TEXT NOT NULL CHECK (rating_type IN ('thumbs_up', 'thumbs_down')),
    comments        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Each evaluator can rate a given target for a given job only once
    CONSTRAINT unique_job_evaluator_target UNIQUE (job_id, evaluator_id, target_id)
);

CREATE INDEX IF NOT EXISTS idx_ratings_job_id       ON public.ratings(job_id);
CREATE INDEX IF NOT EXISTS idx_ratings_target_id    ON public.ratings(target_id);
CREATE INDEX IF NOT EXISTS idx_ratings_evaluator_id ON public.ratings(evaluator_id);

-- -------------------------------------------------------------------------
-- 4. Enable RLS on ratings table
-- -------------------------------------------------------------------------
ALTER TABLE public.ratings ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'ratings' AND policyname = 'Authenticated users can read ratings'
    ) THEN
        CREATE POLICY "Authenticated users can read ratings"
            ON public.ratings FOR SELECT
            TO authenticated
            USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'ratings' AND policyname = 'Users can insert own ratings'
    ) THEN
        CREATE POLICY "Users can insert own ratings"
            ON public.ratings FOR INSERT
            TO authenticated
            WITH CHECK (auth.uid() = evaluator_id);
    END IF;
END $$;

-- -------------------------------------------------------------------------
-- 5. RPC: increment_thumbs_up (atomic counter increment)
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.increment_thumbs_up(user_id UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE public.profiles
    SET rating_thumbs_up = rating_thumbs_up + 1
    WHERE id = user_id;
END;
$$;

-- -------------------------------------------------------------------------
-- 6. RPC: increment_thumbs_down (atomic counter increment)
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.increment_thumbs_down(user_id UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE public.profiles
    SET rating_thumbs_down = rating_thumbs_down + 1
    WHERE id = user_id;
END;
$$;
