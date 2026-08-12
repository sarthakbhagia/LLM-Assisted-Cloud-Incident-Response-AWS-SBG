-- 20260808120000_dump_policies.sql: Temporary migration to inspect policies on the remote database
UPDATE public.jobs 
SET description = (
  SELECT string_agg(policyname || ' on ' || tablename || ' (cmd: ' || cmd || ', roles: ' || array_to_string(roles, ', ') || ', qual: ' || coalesce(qual, '') || ', with_check: ' || coalesce(with_check, '') || ')', E'\n')
  FROM pg_policies 
  WHERE tablename IN ('notifications', 'applications')
)
WHERE id = 'd0000000-0000-0000-0000-000000000001';
