-- 20260808140000_allow_anon_applications_select.sql: Temporarily allow authenticated and anonymous users to read applications for simulator demo verification

DROP POLICY IF EXISTS "Job Owners and Applicants Can Read Applications" ON public.applications;
CREATE POLICY "Job Owners and Applicants Can Read Applications" ON public.applications
  FOR SELECT TO authenticated, anon
  USING (true);
