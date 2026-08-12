-- =========================================================================
-- KAAMSETU MIGRATION: Mutual Thumbs-up/down Ratings Table + Aggregate View
-- =========================================================================

-- 1. Create job_ratings table
CREATE TABLE IF NOT EXISTS public.job_ratings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      UUID NOT NULL REFERENCES public.jobs(id)     ON DELETE CASCADE,
    rater_id    UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    ratee_id    UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    rater_role  TEXT NOT NULL CHECK (rater_role IN ('employer', 'worker')),
    thumbs_up   BOOLEAN NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Each person can only rate once per job
    CONSTRAINT unique_job_rater UNIQUE (job_id, rater_id)
);

CREATE INDEX IF NOT EXISTS idx_job_ratings_job_id   ON public.job_ratings(job_id);
CREATE INDEX IF NOT EXISTS idx_job_ratings_rater_id ON public.job_ratings(rater_id);
CREATE INDEX IF NOT EXISTS idx_job_ratings_ratee_id ON public.job_ratings(ratee_id);

-- 2. Enable Row Level Security
ALTER TABLE public.job_ratings ENABLE ROW LEVEL SECURITY;

-- 3. SELECT Policy: Publicly readable
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'job_ratings' AND policyname = 'Job ratings are publicly readable'
    ) THEN
        CREATE POLICY "Job ratings are publicly readable"
            ON public.job_ratings FOR SELECT
            TO public
            USING (true);
    END IF;
END $$;

-- 4. INSERT Policy: Restricted to genuine participants of a completed job
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'job_ratings' AND policyname = 'Users can insert their own job ratings'
    ) THEN
        CREATE POLICY "Users can insert their own job ratings"
            ON public.job_ratings FOR INSERT
            TO authenticated
            WITH CHECK (
                auth.uid() = rater_id
                AND EXISTS (
                    SELECT 1 FROM public.jobs j
                    WHERE j.id = job_id
                      AND j.status = 'completed'
                      AND (
                          j.employer_id = rater_id
                          OR EXISTS (
                              SELECT 1 FROM public.applications a
                              WHERE a.job_id = j.id
                                AND a.worker_id = rater_id
                                AND a.status = 'assigned'
                          )
                      )
                )
            );
    END IF;
END $$;

-- 5. Create aggregate view for rating summary
CREATE OR REPLACE VIEW public.mutual_rating_summary AS
SELECT
    p.id AS user_id,
    COALESCE(COUNT(jr.id), 0) AS total_ratings,
    COALESCE(COUNT(CASE WHEN jr.thumbs_up = true THEN 1 END), 0) AS thumbs_up_count,
    CASE 
        WHEN COUNT(jr.id) > 0 THEN 
            ROUND((COUNT(CASE WHEN jr.thumbs_up = true THEN 1 END)::numeric / COUNT(jr.id)::numeric) * 100)
        ELSE NULL 
    END AS thumbs_up_percentage
FROM
    public.profiles p
LEFT JOIN
    public.job_ratings jr ON p.id = jr.ratee_id
GROUP BY
    p.id;
