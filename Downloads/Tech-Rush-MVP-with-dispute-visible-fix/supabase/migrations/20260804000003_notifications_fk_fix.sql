-- =========================================================================
-- MIGRATION 000003: Fix notifications FK + ensure table has all columns
-- Run in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/movsaslnwjqbtdynvcwb/sql/new
-- =========================================================================

-- 1. Ensure notifications table exists with correct structure
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    type TEXT NOT NULL DEFAULT 'system',
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    related_job_id UUID,
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Add any missing columns safely
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS related_job_id UUID;
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS is_read BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS type TEXT NOT NULL DEFAULT 'system';

-- 3. Drop the old FK that references profiles(id) — it causes INSERT failures
--    when a user doesn't have a profiles row yet.
--    We reference auth.users(id) instead (always exists after sign-in).
DO $$ BEGIN
  -- Drop FK if it exists (name may vary, so we use a safe approach)
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_type = 'FOREIGN KEY'
      AND table_name = 'notifications'
      AND constraint_name LIKE '%user_id%'
  ) THEN
    EXECUTE (
      SELECT 'ALTER TABLE public.notifications DROP CONSTRAINT ' || constraint_name
      FROM information_schema.table_constraints
      WHERE constraint_type = 'FOREIGN KEY'
        AND table_name = 'notifications'
        AND constraint_name LIKE '%user_id%'
      LIMIT 1
    );
  END IF;
END $$;

-- 4. Add correct FK to auth.users (survives even without a profiles row)
ALTER TABLE public.notifications
  DROP CONSTRAINT IF EXISTS notifications_user_id_fkey;

-- NOTE: If you want referential integrity to auth.users, uncomment below.
-- For now we leave it as unconstrained UUID so any valid auth.uid() works.
-- ALTER TABLE public.notifications
--   ADD CONSTRAINT notifications_user_id_fkey
--   FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- 5. Index for fast per-user queries ordered by time
CREATE INDEX IF NOT EXISTS idx_notifications_user_id_created_at
  ON public.notifications(user_id, created_at DESC);

-- 6. Enable RLS
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- 7. Recreate RLS policies cleanly
DROP POLICY IF EXISTS "Users Can Read Own Notifications" ON public.notifications;
DROP POLICY IF EXISTS "Users or System Can Insert Notifications" ON public.notifications;
DROP POLICY IF EXISTS "Users Can Update Own Notifications" ON public.notifications;

-- Any authenticated user can read their own notifications
CREATE POLICY "Users Can Read Own Notifications"
  ON public.notifications FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

-- Any authenticated user can insert a notification for any user_id
-- (needed: worker inserts for employer, employer inserts for worker)
CREATE POLICY "Users or System Can Insert Notifications"
  ON public.notifications FOR INSERT TO authenticated
  WITH CHECK (true);

-- Users can only update their own notifications (mark as read)
CREATE POLICY "Users Can Update Own Notifications"
  ON public.notifications FOR UPDATE TO authenticated
  USING (auth.uid() = user_id);
