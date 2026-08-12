-- 1. Fix applications RLS update policy to only allow the job owner (employer) to update status
DROP POLICY IF EXISTS "Job Owners and Applicants Can Update Applications" ON public.applications;
CREATE POLICY "Job Owners Can Update Applications" ON public.applications 
  FOR UPDATE TO authenticated 
  USING (
    EXISTS (
      SELECT 1 FROM public.jobs 
      WHERE jobs.id = applications.job_id 
      AND jobs.employer_id = auth.uid()
    )
  );

-- 2. Drop and recreate applications RLS SELECT policy to ensure job owners and applicants can read
DROP POLICY IF EXISTS "Job Owners and Applicants Can Read Applications" ON public.applications;
CREATE POLICY "Job Owners and Applicants Can Read Applications" ON public.applications
  FOR SELECT TO authenticated
  USING (
    auth.uid() = worker_id OR EXISTS (
      SELECT 1 FROM public.jobs 
      WHERE jobs.id = applications.job_id 
      AND jobs.employer_id = auth.uid()
    )
  );

-- 3. Fix notifications RLS insert policy to allow any authenticated user to insert notifications
DROP POLICY IF EXISTS "Users or System Can Insert Notifications" ON public.notifications;
CREATE POLICY "Users or System Can Insert Notifications"
  ON public.notifications FOR INSERT TO authenticated
  WITH CHECK (true);
