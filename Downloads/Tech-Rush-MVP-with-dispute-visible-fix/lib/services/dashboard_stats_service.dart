import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'supabase_service.dart';

/// Holds all computed stat values for the Dashboard stat grid.
/// Both employer and worker stats live here; the dashboard picks which to show.
class DashboardStats {
  // ── Employer stats ────────────────────────────────────────────────────────
  final int activePostings;       // jobs WHERE status='open'  AND employer_id=me
  final int totalApplications;    // applications on any of my jobs
  final int totalDispatches;      // jobs WHERE status='completed' AND employer_id=me
  final double avgDailyPayout;    // AVG(price) on completed jobs

  // ── Worker stats ──────────────────────────────────────────────────────────
  final double dailyRate;         // profiles.daily_rate
  final double workerRating;      // AVG(rating) from reviews WHERE worker_id=me
  final int workerReviewCount;    // COUNT of reviews WHERE worker_id=me
  final int jobsCompleted;        // jobs WHERE status='completed' AND assigned to me via applications
  final int applicationsSent;     // applications WHERE worker_id=me (all statuses)
  final int applicationsPending;  // applications WHERE worker_id=me AND status='interested'

  const DashboardStats({
    this.activePostings = 0,
    this.totalApplications = 0,
    this.totalDispatches = 0,
    this.avgDailyPayout = 0.0,
    this.dailyRate = 650.0,
    this.workerRating = 0.0,
    this.workerReviewCount = 0,
    this.jobsCompleted = 0,
    this.applicationsSent = 0,
    this.applicationsPending = 0,
  });
}

class DashboardStatsService {
  final SupabaseClient _client = SupabaseService().client;

  /// Fetches all employer-mode stats for [employerId].
  ///
  /// Queries fired:
  ///   1. SELECT count(*) FROM jobs WHERE employer_id=$1 AND status='open'
  ///   2. SELECT count(*) FROM jobs WHERE employer_id=$1 AND status='completed'
  ///   3. SELECT avg(price)  FROM jobs WHERE employer_id=$1 AND status='completed'
  ///   4. SELECT count(applications.*) via join: applications.job_id IN
  ///         (SELECT id FROM jobs WHERE employer_id=$1)
  Future<DashboardStats> fetchEmployerStats(String employerId) async {
    try {
      // 1 + 2 + 3: single query returning all job rows so we can aggregate in Dart
      //   (Supabase PostgREST doesn't support multi-aggregate in one call without a view,
      //    so we fetch the price column for completed jobs and count open/completed
      //    in a single broad SELECT — only fetching two tiny columns.)
      final jobsRes = await _client
          .from('jobs')
          .select('id, status, price')
          .eq('employer_id', employerId);

      final List jobRows = jobsRes as List;

      int openCount = 0;
      int completedCount = 0;
      double priceSum = 0.0;

      for (final row in jobRows) {
        final status = row['status'] as String? ?? '';
        final price = (row['price'] as num?)?.toDouble() ?? 0.0;
        if (status == 'open') openCount++;
        if (status == 'completed') {
          completedCount++;
          priceSum += price;
        }
      }

      final avgPayout = completedCount > 0 ? priceSum / completedCount : 0.0;

      // 4. Count applications on employer's jobs using Supabase join filter
      //    applications?job_id=in.(SELECT id FROM jobs WHERE employer_id=...)
      //    We use a PostgREST embedded resource count trick:
      //    GET /applications?job_id=in.(subquery) — but PostgREST doesn't support
      //    subqueries in filter values. Instead we fetch job IDs then count applications.
      int appCount = 0;
      if (jobRows.isNotEmpty) {
        try {
          final appRes = await _client
              .from('applications')
              .select('id, jobs!inner(employer_id)')
              .eq('jobs.employer_id', employerId);
          appCount = (appRes as List).length;
        } catch (e) {
          if (kDebugMode) {
            print('⚠️ [DashboardStatsService] Error querying applications count: $e');
          }
        }
      }

      return DashboardStats(
        activePostings: jobRows.length,
        totalApplications: appCount,
        totalDispatches: completedCount,
        avgDailyPayout: avgPayout,
      );
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [DashboardStatsService] fetchEmployerStats error: $e');
      }
      return const DashboardStats();
    }
  }

  /// Fetches all worker-mode stats for [workerId].
  ///
  /// Queries fired:
  ///   1. SELECT daily_rate FROM profiles WHERE id=$1
  ///   2. SELECT avg(rating), count(*) FROM reviews WHERE worker_id=$1
  ///   3. SELECT count(*) FROM applications WHERE worker_id=$1 (all + pending)
  ///   4. SELECT count(*) FROM applications WHERE worker_id=$1 AND status='assigned'/'completed'
  ///      cross-referenced with job status=completed
  Future<DashboardStats> fetchWorkerStats(String workerId) async {
    try {
      // 1. Daily rate from profile
      double dailyRate = 650.0;
      try {
        final profileRes = await _client
            .from('profiles')
            .select('daily_rate')
            .eq('id', workerId)
            .maybeSingle();
        if (profileRes != null) {
          dailyRate = (profileRes['daily_rate'] as num?)?.toDouble() ?? 650.0;
        }
      } catch (_) {}

      // 2. Rating & review count from reviews table
      double workerRating = 0.0;
      int reviewCount = 0;
      try {
        final reviewsRes = await _client
            .from('reviews')
            .select('rating')
            .eq('worker_id', workerId);
        final List reviewRows = reviewsRes as List;
        reviewCount = reviewRows.length;
        if (reviewCount > 0) {
          final sum = reviewRows.fold<double>(
            0.0,
            (acc, r) => acc + ((r['rating'] as num?)?.toDouble() ?? 0.0),
          );
          workerRating = sum / reviewCount;
        }
      } catch (_) {}

      // 3 + 4. Applications: total sent and pending
      int appsSent = 0;
      int appsPending = 0;
      int jobsCompleted = 0;
      try {
        final appsRes = await _client
            .from('applications')
            .select('status')
            .eq('worker_id', workerId);
        final List appRows = appsRes as List;
        appsSent = appRows.length;
        for (final row in appRows) {
          final s = row['status'] as String? ?? '';
          if (s == 'interested') appsPending++;
          if (s == 'completed' || s == 'assigned') jobsCompleted++;
        }
      } catch (_) {}

      int openJobsCount = 0;
      try {
        final openJobsRes = await _client
            .from('jobs')
            .select('id')
            .eq('status', 'open');
        openJobsCount = (openJobsRes as List).length;
      } catch (_) {}

      return DashboardStats(
        activePostings: openJobsCount,
        dailyRate: dailyRate,
        workerRating: double.parse(workerRating.toStringAsFixed(1)),
        workerReviewCount: reviewCount,
        jobsCompleted: jobsCompleted,
        applicationsSent: appsSent,
        applicationsPending: appsPending,
      );
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [DashboardStatsService] fetchWorkerStats error: $e');
      }
      return const DashboardStats();
    }
  }
}
