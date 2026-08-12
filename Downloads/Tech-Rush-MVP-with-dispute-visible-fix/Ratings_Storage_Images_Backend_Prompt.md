We're completing the full backend today. This builds on the jobs/applications schema and auth system from earlier — do this in stages, confirm each before moving to the next.

---

## STAGE 1 — Ratings & Reviews System (household → worker only, one-directional)

### Schema
Create a `reviews` table in Supabase:
- id (uuid, pk)
- job_id (uuid, references jobs.id)
- worker_id (uuid, references profiles.id) — who is being rated
- employer_id (uuid, references profiles.id) — who is rating
- rating (integer, 1-5, with a check constraint enforcing this range)
- comment (text, nullable)
- created_at (timestamp default now())
- Add a unique constraint on (job_id, employer_id) so an employer can only review a given job once.

### Row Level Security (this is the important part — enforce the asymmetry at the database level, not just in the UI)
- INSERT: only allowed where `auth.uid() = employer_id` AND the requesting user's `profiles.role = 'employer'` AND the job referenced is `status = 'completed'` AND the job's `employer_id` matches the reviewer. This means even if someone tampers with the app's frontend, a worker account literally cannot insert a review — the database rejects it regardless of what the client sends.
- SELECT: reviews should be publicly readable (any authenticated user can see a worker's reviews, since that's the trust signal a future employer needs).
- No UPDATE/DELETE policy for now (reviews are immutable once submitted) — flag this as a deliberate choice, not an oversight.
- Show me the exact policy SQL before applying it, and explain in plain English what each one blocks.

### App flow
1. Add a "Rate this worker" prompt that appears for the Employer only after they mark a job as `completed` — a simple 1-5 star selector + optional comment, submitted via a new `review_service.dart`.
2. On the Worker profile screen, replace the hardcoded "4.8 (24)" with a real computed average: `fetchWorkerRatingSummary(workerId)` that queries reviews for that worker, returns average rating + total count. Use our existing RatingBreakdown widget, now fed real data (average, count, and the star-distribution breakdown computed from actual review rows).
3. If a worker has zero reviews yet, show a clear "No reviews yet" state instead of a fake number or a broken 0.0/0.
4. Confirm there is NO rating UI exposed anywhere in the Worker mode of the app — a worker should never see a "rate this household" option anywhere, by design, not just by omission.

---

## STAGE 2 — Supabase Storage for images

1. Create two Storage buckets: `profile-photos` (public read, authenticated write — a user can only write to their own path, e.g. `profile-photos/{user_id}/photo.jpg`) and `job-images` (public read, employer write for their own job postings).
2. Set up the storage RLS policies matching that ownership rule for each bucket.
3. Build a reusable `lib/services/storage_service.dart` with `uploadProfilePhoto(File image)` and `uploadJobImage(File image, String jobId)` methods using supabase_flutter's storage API, returning the public URL to store in the relevant table row (add a `photo_url` column to `profiles` and an `image_url` column to `jobs` if not already present).

---

## STAGE 3 — Worker profile photo + work-sample gallery

1. On the Worker's own Profile/Settings screen, add a tappable avatar that opens the device image picker (use `image_picker` package), uploads via `uploadProfilePhoto`, and updates `profiles.photo_url`.
2. Replace the "RK" initials circle everywhere it appears (Dashboard, Job Detail's provider card, Profile screen) with the real photo when available, falling back to initials only when no photo has been uploaded yet — never show a broken image icon.
3. Add a simple "Work Samples" section to the worker profile — a horizontal scrollable row allowing the worker to upload 3-5 photos of past work (same storage flow, a `work_samples` table: id, worker_id, image_url, created_at). This is a real trust-building feature Urban Company-style apps rely on heavily — a painter's profile with actual photos of painted rooms is dramatically more convincing than a star rating alone.

---

## STAGE 4 — Representative imagery for job categories/postings

1. For the six category tiles (Painting, Cleaning, Plumbing, Cooking, Gardening, Electrical), replace the current generic icon-only tiles with a small representative image alongside or instead of the icon — e.g. a paint roller for Painting, a mop/broom for Cleaning, a wrench for Plumbing, a cooking pot for Cooking, a plant for Gardening, a light bulb/wire for Electrical. Source these as free-to-use flat icon/illustration assets (e.g. from a package like `flutter_svg` with bundled SVGs, or Iconify/unDraw-style free illustration sets) — do not use copyrighted stock photography. List exactly which asset source you're using so I can confirm licensing is fine for a hackathon submission.
2. For individual job postings specifically, add an `image_url` field usage on the job card/detail (already added to schema in Stage 2) so an employer posting "Sofa Cleaning" can optionally attach a representative photo (e.g. of a sofa) at creation time, using the same image picker + upload flow as the profile photo. If no image is attached, fall back to a generic category-based placeholder image (e.g. any "Cleaning" job with no custom photo shows the generic cleaning illustration) rather than a blank space.

---

## STAGE 5 — Final integration check

Once all four stages are done, walk through this full scenario yourself and confirm each step against the real database (not cached data):
1. Employer signs up, uploads a profile photo, posts a "Sofa Cleaning" job with a photo attached.
2. Worker signs up, uploads a profile photo and 2 work-sample images, browses to Cleaning category, sees the job with its real image and real employer info.
3. Worker applies. Employer sees the real application with the worker's real photo and current (zero, since new) rating.
4. Employer accepts, marks the job completed.
5. Employer rates the worker 5 stars with a comment.
6. Worker's profile now shows a real 5.0 (1) rating instead of a hardcoded number.
7. Confirm the worker's account has no path anywhere in the UI to submit a rating themselves.

Report back exactly what you tested and confirm each step passed against the live Supabase database.
