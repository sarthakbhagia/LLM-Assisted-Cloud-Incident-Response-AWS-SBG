# Supabase Backend Connection Plan & TODOs

This document outlines the step-by-step technical requirements for wiring the frontend Job Listings & Dispatch features to the Supabase PostgreSQL backend.

---

## 1. Supabase Database Schema (`jobs` table)

Execute the following DDL SQL script in the Supabase SQL Editor:

```sql
-- Create jobs table
CREATE TABLE public.jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('Painting', 'Cleaning', 'Plumbing', 'Cooking', 'Gardening', 'Electrical')),
  description TEXT NOT NULL,
  price NUMERIC(10, 2) NOT NULL,
  original_price NUMERIC(10, 2),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'assigned', 'completed')),
  rating NUMERIC(3, 2) DEFAULT 5.00,
  review_count INT DEFAULT 0,
  location TEXT NOT NULL,
  posted_by UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  employer_name TEXT NOT NULL,
  worker_name TEXT,
  verified BOOLEAN DEFAULT true,
  urgent BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for high-performance category filtering
CREATE INDEX idx_jobs_category ON public.jobs(category);
CREATE INDEX idx_jobs_status ON public.jobs(status);
```

---

## 2. Row Level Security (RLS) Policies

```sql
-- Enable RLS
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

-- Allow all authenticated users to view job listings
CREATE POLICY "Allow authenticated read access to jobs"
  ON public.jobs
  FOR SELECT
  TO authenticated
  USING (true);

-- Allow employers to create new job listings under their user id
CREATE POLICY "Allow employers to insert own jobs"
  ON public.jobs
  FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = posted_by);

-- Allow employers or assigned workers to update job status
CREATE POLICY "Allow update for job owners"
  ON public.jobs
  FOR UPDATE
  TO authenticated
  USING (auth.uid() = posted_by);
```

---

## 3. Service Layer Architecture (`lib/services/job_service.dart`)

Implement the API client service methods:

```dart
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/job.dart';

class JobService {
  final SupabaseClient _client = Supabase.instance.client;

  /// Fetch jobs filtered by category (or all if category is 'All')
  Future<List<Job>> fetchJobsByCategory(String category) async {
    var query = _client.from('jobs').select();
    if (category != 'All') {
      query = query.eq('category', category);
    }
    final data = await query.order('created_at', ascending: false);
    return (data as List).map((json) => Job.fromJson(json)).toList();
  }

  /// Create a new job listing
  Future<void> createJob(Job job) async {
    await _client.from('jobs').insert(job.toJson());
  }
}
```

---

## 4. Frontend Integration Plan

1. **Replace Static Mock Data**:
   - Update `JobListingScreen` to replace direct `mockJobs` reference with `ref.watch(jobsByCategoryProvider(category))`.
2. **Skeleton & Loading States**:
   - Keep the existing `SkeletonList` loader while Supabase `FutureProvider` is loading.
3. **Error Handling**:
   - Display a user-friendly `EmptyState` retry UI when API fails.

---

## 5. Realtime Supabase Streams (Phase 2)

Use Supabase `.stream()` API for real-time live updates on the job board:

```dart
Stream<List<Job>> streamJobsByCategory(String category) {
  var stream = _client.from('jobs').stream(primaryKey: ['id']);
  if (category != 'All') {
    return stream.eq('category', category).map(
      (list) => list.map((json) => Job.fromJson(json)).toList(),
    );
  }
  return stream.map((list) => list.map((json) => Job.fromJson(json)).toList());
}
```
