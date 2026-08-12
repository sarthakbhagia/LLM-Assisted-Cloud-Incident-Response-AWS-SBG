import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/job.dart';
import '../models/application.dart';
import '../services/job_service.dart';
import '../services/application_service.dart';
import '../services/dashboard_stats_service.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

final jobServiceProvider = Provider<JobService>((ref) => JobService());
final applicationServiceProvider = Provider<ApplicationService>((ref) => ApplicationService());

/// Parameter object for parameterized job queries in Riverpod
class JobQueryParams {
  final String category;
  final String status;
  final double minPrice;
  final double maxPrice;
  final String searchQuery;
  final String sortBy;

  const JobQueryParams({
    this.category = 'All',
    this.status = 'ALL',
    this.minPrice = 0.0,
    this.maxPrice = 10000.0,
    this.searchQuery = '',
    this.sortBy = 'most_recent',
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is JobQueryParams &&
          runtimeType == other.runtimeType &&
          category == other.category &&
          status == other.status &&
          minPrice == other.minPrice &&
          maxPrice == other.maxPrice &&
          searchQuery == other.searchQuery &&
          sortBy == other.sortBy;

  @override
  int get hashCode =>
      category.hashCode ^
      status.hashCode ^
      minPrice.hashCode ^
      maxPrice.hashCode ^
      searchQuery.hashCode ^
      sortBy.hashCode;
}

/// Provider to fetch filtered jobs from Supabase using JobQueryParams
final filteredJobsProvider =
    FutureProvider.family<List<Job>, JobQueryParams>((ref, params) async {
  final jobService = ref.watch(jobServiceProvider);
  return await jobService.fetchJobs(
    category: params.category,
    status: params.status,
    minPrice: params.minPrice,
    maxPrice: params.maxPrice,
    searchQuery: params.searchQuery,
    sortBy: params.sortBy,
  );
});

/// Provider for searching jobs in Supabase with ilike matching
final searchJobsProvider =
    FutureProvider.family<List<Job>, String>((ref, query) async {
  if (query.trim().isEmpty) return [];
  final jobService = ref.watch(jobServiceProvider);
  return await jobService.searchJobs(query.trim());
});

/// Provider to fetch jobs by category (from Supabase)
final jobsByCategoryProvider =
    FutureProvider.family<List<Job>, String>((ref, category) async {
  final jobService = ref.watch(jobServiceProvider);
  return await jobService.fetchJobsByCategory(category);
});

/// Provider for single job detail by ID from Supabase
final jobDetailProvider =
    FutureProvider.family<Job?, String>((ref, jobId) async {
  final jobService = ref.watch(jobServiceProvider);
  return await jobService.fetchJobById(jobId);
});

/// Provider for employer to view applications submitted for a job
final jobApplicationsProvider =
    FutureProvider.family<List<Application>, String>((ref, jobId) async {
  final appService = ref.watch(applicationServiceProvider);
  return await appService.fetchApplicationsForJob(jobId);
});

/// Provider for worker to view their own application history
final workerApplicationsProvider =
    FutureProvider.family<List<Application>, String>((ref, workerId) async {
  final appService = ref.watch(applicationServiceProvider);
  return await appService.fetchApplicationsForWorker(workerId);
});

/// Provider to fetch jobs posted by a specific employer from Supabase
final jobsByEmployerProvider =
    FutureProvider.family<List<Job>, String>((ref, employerId) async {
  final jobService = ref.watch(jobServiceProvider);
  return await jobService.fetchJobsByEmployer(employerId);
});

/// Provider to fetch all applications received across all jobs of an employer
final employerApplicationsProvider =
    FutureProvider.family<List<Application>, String>((ref, employerId) async {
  final appService = ref.watch(applicationServiceProvider);

  // Fetch employer's active job IDs once to filter incoming realtime applications
  final jobs = await ref.watch(jobsByEmployerProvider(employerId).future);
  final jobIds = jobs.map((j) => j.id).toSet();

  // Subscribe to realtime insert events on applications table
  final channel = appService.subscribeToApplications((payload) {
    final newRow = payload.newRecord;
    final jobId = newRow['job_id']?.toString();
    if (jobId != null && jobIds.contains(jobId)) {
      // Invalidate stats to update dashboard counts
      ref.invalidate(dashboardStatsProvider(DashboardStatsParams(
        userId: employerId,
        role: 'employer',
      )));
      // Invalidate ourselves to fetch the latest applications list
      ref.invalidateSelf();
    }
  });

  // Clean up and unsubscribe on dispose
  ref.onDispose(() {
    channel.unsubscribe();
  });

  return await appService.fetchApplicationsForEmployer(employerId);
});

/// Parameter object for dashboardStatsProvider — keyed on user ID + role.
class DashboardStatsParams {
  final String userId;
  final String role; // 'employer' or 'worker'

  const DashboardStatsParams({required this.userId, required this.role});

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is DashboardStatsParams &&
          runtimeType == other.runtimeType &&
          userId == other.userId &&
          role == other.role;

  @override
  int get hashCode => userId.hashCode ^ role.hashCode;
}

/// Fetches real aggregate stats from Supabase for the Dashboard stat grid.
/// Keyed on (userId, role) so it re-fetches when the user switches modes.
final dashboardStatsProvider =
    FutureProvider.family<DashboardStats, DashboardStatsParams>(
  (ref, params) async {
    if (params.userId.isEmpty) return const DashboardStats();
    final service = DashboardStatsService();
    if (params.role == 'employer') {
      return service.fetchEmployerStats(params.userId);
    } else {
      return service.fetchWorkerStats(params.userId);
    }
  },
);

/// Fetches all active distinct custom category names from the database (not in standard six).
final customCategoriesProvider = FutureProvider<List<String>>((ref) async {
  try {
    final client = Supabase.instance.client;
    final res = await client.from('jobs').select('category');
    final data = res as List;
    final allCats = data.map((json) => json['category']?.toString() ?? '').toList();
    final fixedCats = {'Painting', 'Cleaning', 'Plumbing', 'Cooking', 'Gardening', 'Electrical'};
    final customCats = allCats
        .where((c) => c.isNotEmpty && !fixedCats.contains(c))
        .toSet()
        .toList();
    return customCats;
  } catch (_) {
    return [];
  }
});
