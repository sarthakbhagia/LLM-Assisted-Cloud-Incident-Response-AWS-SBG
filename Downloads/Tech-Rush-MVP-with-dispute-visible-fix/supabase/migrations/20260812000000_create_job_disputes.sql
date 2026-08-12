-- KaamSetu: Dispute / Complaint workflow for completed jobs.
-- Each participant can submit one issue per completed job.

CREATE TABLE IF NOT EXISTS public.job_disputes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    reporter_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    reporter_role TEXT NOT NULL CHECK (reporter_role IN ('employer', 'worker')),
    category TEXT NOT NULL CHECK (category IN ('Work quality', 'Payment', 'No-show', 'Misconduct', 'Other')),
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'under_review' CHECK (status IN ('under_review', 'resolved', 'rejected')),
    resolution_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    CONSTRAINT unique_job_dispute_reporter UNIQUE (job_id, reporter_id)
);

CREATE INDEX IF NOT EXISTS idx_job_disputes_job ON public.job_disputes(job_id);
CREATE INDEX IF NOT EXISTS idx_job_disputes_reporter ON public.job_disputes(reporter_id);
CREATE INDEX IF NOT EXISTS idx_job_disputes_status ON public.job_disputes(status);

ALTER TABLE public.job_disputes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Participants can read their job disputes" ON public.job_disputes;
CREATE POLICY "Participants can read their job disputes"
ON public.job_disputes FOR SELECT TO authenticated
USING (
    auth.uid() = reporter_id
    OR EXISTS (
        SELECT 1 FROM public.jobs j
        WHERE j.id = job_disputes.job_id
          AND j.employer_id = auth.uid()
    )
    OR EXISTS (
        SELECT 1 FROM public.applications a
        WHERE a.job_id = job_disputes.job_id
          AND a.worker_id = auth.uid()
          AND a.status = 'assigned'
    )
);

DROP POLICY IF EXISTS "Participants can report completed jobs" ON public.job_disputes;
CREATE POLICY "Participants can report completed jobs"
ON public.job_disputes FOR INSERT TO authenticated
WITH CHECK (
    auth.uid() = reporter_id
    AND EXISTS (
        SELECT 1 FROM public.jobs j
        WHERE j.id = job_disputes.job_id
          AND j.status = 'completed'
          AND (
              j.employer_id = auth.uid()
              OR EXISTS (
                  SELECT 1 FROM public.applications a
                  WHERE a.job_id = j.id
                    AND a.worker_id = auth.uid()
                    AND a.status = 'assigned'
              )
          )
    )
);
