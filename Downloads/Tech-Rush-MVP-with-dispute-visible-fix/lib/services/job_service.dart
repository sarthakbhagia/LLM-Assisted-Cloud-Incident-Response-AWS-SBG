import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/job.dart';
import 'supabase_service.dart';
import 'notification_service.dart';

class JobService {
  final SupabaseClient _client = SupabaseService().client;
  static final RegExp _uuidRegExp = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  /// Creates a new job in Supabase jobs table with session verification.
  Future<Job> createJob(Job job, {String? activeUserId}) async {
    final String? supabaseUserId = _client.auth.currentUser?.id;
    final String userId = activeUserId ?? supabaseUserId ?? 'e0000000-0000-0000-0000-000000000001';

    if (userId.isEmpty) {
      throw Exception('Session expired. Please log out and log back in.');
    }

    if (kDebugMode) {
      print('🔍 [JobService] Pre-insert session check:');
      print('   -> currentUser id: $supabaseUserId');
      print('   -> activeUserId override: $activeUserId');
      print('   -> final resolved userId: $userId');
    }

    // 2. Build insertion payload
    final payload = <String, dynamic>{
      'employer_id': userId,
      'household_id': userId,
      'title': job.title,
      'category': job.category,
      'description': job.description.isNotEmpty ? job.description : '.',
      'price': job.wage,
      'budget': job.wage,
      'status': 'open',
      'location': job.location,
      'employer_name': job.employerName.isNotEmpty ? job.employerName : 'Employer',
      'urgent': job.urgent,
      if (job.originalWage != null) 'original_price': job.originalWage,
      if (job.imageUrl != null) 'image_url': job.imageUrl,
      if (job.workerName != null) 'worker_name': job.workerName,
    };

    if (kDebugMode) {
      print('🔄 [JobService] createJob insert payload: $payload');
    }

    // Will throw PostgrestException on any DB error.
    final res = await _client.from('jobs').insert(payload).select().single();

    if (kDebugMode) {
      print('✅ [JobService] Created job in Supabase: ${res['id']}');
    }
    final createdJob = Job.fromJson(res);
    unawaited(_notifyWorkersOfNewJob(createdJob));
    return createdJob;
  }

  /// Listens to real-time changes on the `jobs` table in Supabase
  RealtimeChannel subscribeToJobs(void Function() onDataChange) {
    final channel = _client.channel('public:jobs');
    channel.onPostgresChanges(
      event: PostgresChangeEvent.all,
      schema: 'public',
      table: 'jobs',
      callback: (payload) {
        if (kDebugMode) {
          print('⚡ [JobService] Realtime DB change detected on jobs table');
        }
        onDataChange();
      },
    ).subscribe();
    return channel;
  }

  /// Main multi-criteria query runner for Supabase `jobs` table
  Future<List<Job>> fetchJobs({
    String category = 'All',
    String status = 'ALL',
    double? minPrice,
    double? maxPrice,
    String? searchQuery,
    String? sortBy,
  }) async {
    try {
      var query = _client.from('jobs').select();

      // 1. Category Filter
      if (category != 'All' && category.isNotEmpty) {
        query = query.eq('category', category);
      }

      // 2. Status Filter ('open', 'assigned', 'completed')
      if (status != 'ALL' && status.isNotEmpty) {
        query = query.eq('status', status.toLowerCase());
      }

      // 3. Price Filter Range
      if (minPrice != null && minPrice > 0) {
        query = query.gte('price', minPrice);
      }
      if (maxPrice != null && maxPrice < 10000) {
        query = query.lte('price', maxPrice);
      }

      // 4. Search Query Filter (ilike on title, category, location, description)
      if (searchQuery != null && searchQuery.trim().isNotEmpty) {
        final q = searchQuery.trim();
        query = query.or('title.ilike.%$q%,category.ilike.%$q%,location.ilike.%$q%,description.ilike.%$q%');
      }

      // 5. Sort Ordering
      var orderColumn = 'created_at';
      var ascending = false;

      if (sortBy == 'price_low') {
        orderColumn = 'price';
        ascending = true;
      } else if (sortBy == 'price_high') {
        orderColumn = 'price';
        ascending = false;
      } else if (sortBy == 'rating') {
        orderColumn = 'rating';
        ascending = false;
      }

      final res = await query.order(orderColumn, ascending: ascending);
      final List data = res as List;
      final jobs = data.map((json) {
        final job = Job.fromJson(json);
        return _localJobsOverrides[job.id] ?? job;
      }).toList();
      return jobs;
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [JobService] Error fetching jobs: $e');
      }
      return [];
    }
  }

  /// Legacy helper for category fetching
  Future<List<Job>> fetchJobsByCategory(String category) async {
    return fetchJobs(category: category);
  }

  /// Search jobs in Supabase with ilike matching
  Future<List<Job>> searchJobs(String searchQuery) async {
    return fetchJobs(searchQuery: searchQuery);
  }

  /// Fetches jobs posted by a specific employer
  Future<List<Job>> fetchJobsByEmployer(String employerId) async {
    try {
      if (!_uuidRegExp.hasMatch(employerId)) {
        return [];
      }

      final res = await _client
          .from('jobs')
          .select()
          .eq('employer_id', employerId)
          .order('created_at', ascending: false);
      final List data = res as List;
      return data.map((json) {
        final job = Job.fromJson(json);
        return _localJobsOverrides[job.id] ?? job;
      }).toList();
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [JobService] Error fetching jobs for employer ($employerId): $e');
      }
      return [];
    }
  }

  /// Fetches single job details by ID from Supabase
  Future<Job?> fetchJobById(String jobId) async {
    if (_localJobsOverrides.containsKey(jobId)) {
      return _localJobsOverrides[jobId];
    }

    if (!_uuidRegExp.hasMatch(jobId)) {
      try {
        return mockJobs.firstWhere((j) => j.id == jobId);
      } catch (_) {
        return null;
      }
    }

    try {
      final res =
          await _client.from('jobs').select().eq('id', jobId).maybeSingle();
      if (res == null) return null;
      return Job.fromJson(res);
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [JobService] Error fetching job ($jobId): $e');
      }
      return null;
    }
  }

  static final Map<String, Job> _localJobsOverrides = {};

  Future<bool> updateJobStatus({
    required String jobId,
    required String status,
    String? workerName,
    String? assignedWorkerId,
  }) async {
    // Update local override
    final existingJob = await fetchJobById(jobId);
    if (existingJob != null) {
      final updated = existingJob.copyWith(
        status: status,
        workerName: workerName ?? existingJob.workerName,
      );
      _localJobsOverrides[jobId] = updated;
    }

    if (!_uuidRegExp.hasMatch(jobId)) {
      return true;
    }

    try {
      final payload = <String, dynamic>{
        'status': status,
        if (workerName != null && workerName.isNotEmpty) 'worker_name': workerName,
        if (assignedWorkerId != null && assignedWorkerId.isNotEmpty) 'assigned_worker_id': assignedWorkerId,
      };

      await _client.from('jobs').update(payload).eq('id', jobId);
      if (kDebugMode) {
        print('✅ [JobService] Updated job $jobId status to $status');
      }

      // ── Completion notifications ────────────────────────────────────────
      if (status == 'completed') {
        _sendCompletionNotifications(jobId);
      }

      return true;
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [JobService] Error updating job status ($jobId): $e');
      }
      return false;
    }
  }

  /// Fetches the job context and fires two notifications for job completion.
  /// Runs asynchronously and swallows errors.
  Future<void> _sendCompletionNotifications(String jobId) async {
    final notif = NotificationService();
    try {
      final res = await _client
          .from('jobs')
          .select('employer_id, title')
          .eq('id', jobId)
          .maybeSingle();
      if (res == null) return;

      final employerId = res['employer_id']?.toString();
      final jobTitle = res['title']?.toString() ?? 'your job';

      // Fetch assigned worker via applications table
      final appRes = await _client
          .from('applications')
          .select('worker_id')
          .eq('job_id', jobId)
          .eq('status', 'assigned')
          .maybeSingle();

      final workerId = appRes?['worker_id']?.toString();

      if (workerId != null && _uuidRegExp.hasMatch(workerId)) {
        await notif.insertNotification(
          userId: workerId,
          type: 'job_completed',
          title: 'Job Marked Complete ✅',
          body: '"$jobTitle" has been marked as completed. Great work!',
          relatedJobId: jobId,
        );
      }

      if (employerId != null && _uuidRegExp.hasMatch(employerId)) {
        await notif.insertNotification(
          userId: employerId,
          type: 'rate_worker',
          title: 'Rate Your Worker',
          body: '"$jobTitle" is complete. Leave a rating for your worker!',
          relatedJobId: jobId,
        );
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [JobService] _sendCompletionNotifications error: $e');
      }
    }
  }

  Future<void> _notifyWorkersOfNewJob(Job job) async {
    try {
      final notif = NotificationService();
      final res = await _client.from('profiles').select('id, skills').eq('role', 'worker');
      final List workers = res as List;

      bool matchesCategory(List<String> skills, String category) {
        final catLower = category.toLowerCase();
        for (final skill in skills) {
          final skillLower = skill.toLowerCase();
          if (skillLower.contains(catLower) || catLower.contains(skillLower)) {
            return true;
          }
          if (catLower == 'painting' && (skillLower.contains('paint') || skillLower.contains('wall'))) return true;
          if (catLower == 'cleaning' && (skillLower.contains('clean') || skillLower.contains('wash'))) return true;
          if (catLower == 'plumbing' && (skillLower.contains('plumb') || skillLower.contains('leak'))) return true;
          if (catLower == 'cooking' && (skillLower.contains('cook') || skillLower.contains('chef') || skillLower.contains('meal'))) return true;
          if (catLower == 'gardening' && (skillLower.contains('garden') || skillLower.contains('lawn') || skillLower.contains('prun'))) return true;
          if (catLower == 'electrical' && (skillLower.contains('elect') || skillLower.contains('wiring') || skillLower.contains('mcb'))) return true;
        }
        return false;
      }

      for (final worker in workers) {
        final workerId = worker['id'] as String;
        final List skillsRaw = worker['skills'] as List? ?? [];
        final skills = skillsRaw.map((s) => s.toString()).toList();
        if (matchesCategory(skills, job.category)) {
          await notif.insertNotification(
            userId: workerId,
            type: 'new_job',
            title: 'New Matching Job!',
            body: 'New "${job.title}" posted under "${job.category}".',
            relatedJobId: job.id,
          );
        }
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [_notifyWorkersOfNewJob] Error: $e');
      }
    }
  }
}

/// Fire-and-forget helper.
void unawaited(Future<void> future) {}
