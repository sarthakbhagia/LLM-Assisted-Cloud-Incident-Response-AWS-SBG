-- 20260808130000_fix_notifications_select_policy.sql: Drop restrictive SELECT policy and allow authenticated users to read notifications to support insert-returning flows

DROP POLICY IF EXISTS "Users Can Read Own Notifications" ON public.notifications;
CREATE POLICY "Users Can Read Own Notifications" ON public.notifications
  FOR SELECT TO authenticated
  USING (true);
