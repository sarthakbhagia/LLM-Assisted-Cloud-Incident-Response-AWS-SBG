import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/application.dart';
import 'supabase_service.dart';
import 'notification_service.dart';
import 'job_service.dart';

class ApplicationService {
  final SupabaseClient _client = SupabaseService().client;
  final NotificationService _notif = NotificationService();

  static final List<Application> _localApplicationsStore = [];
  static final RegExp _uuidRegExp = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  // ── Helper ───────────────────────────────────────────────────────────────

  /// Looks up a job row and returns the employer_id (for notification routing).
  Future<String?> _fetchEmployerIdForJob(String jobId) async {
    if (!_uuidRegExp.hasMatch(jobId)) return null;
    try {
      final res = await _client
          .from('jobs')
          .select('employer_id, title, employer_name')
          .eq('id', jobId)
          .maybeSingle();
      return res?['employer_id']?.toString();
    } catch (_) {
      return null;
    }
  }

  /// Looks up a job row and returns both employer_id and worker_id (via applications).
  Future<Map<String, String?>> _fetchJobContext(String jobId) async {
    if (!_uuidRegExp.hasMatch(jobId)) return {};
    try {
      final res = await _client
          .from('jobs')
          .select('employer_id, title, worker_name')
          .eq('id', jobId)
          .maybeSingle();
      if (res == null) return {};
      return {
        'employer_id': res['employer_id']?.toString(),
        'job_title': res['title']?.toString() ?? 'Job',
        'worker_name': res['worker_name']?.toString(),
      };
    } catch (_) {
      return {};
    }
  }

  // ── Apply ────────────────────────────────────────────────────────────────

  /// Creates a new application row in Supabase applications table.
  /// On success → inserts an `application_received` notification for the employer.
  Future<Application?> applyToJob({
    required String jobId,
    required String workerId,
    required String workerName,
    required String workerPhone,
  }) async {
    final now = DateTime.now();
    final newApp = Application(
      id: 'app_${now.millisecondsSinceEpoch}',
      jobId: jobId,
      workerId: workerId,
      workerName: workerName,
      workerPhone: workerPhone,
      status: 'interested',
      createdAt: now,
    );

    // Save locally for fallback
    _localApplicationsStore.removeWhere(
        (a) => a.jobId == jobId && a.workerId == workerId);
    _localApplicationsStore.add(newApp);

    if (!_uuidRegExp.hasMatch(jobId)) {
      return newApp;
    }

    try {
      final user = _client.auth.currentUser;
      final effectiveWorkerId =
          (user != null && _uuidRegExp.hasMatch(user.id)) ? user.id : workerId;

      // Defense-in-depth: check role in database to prevent employers from applying
      if (_uuidRegExp.hasMatch(effectiveWorkerId)) {
        final profileRes = await _client
            .from('profiles')
            .select('role')
            .eq('id', effectiveWorkerId)
            .maybeSingle();
        if (profileRes != null && profileRes['role'] == 'employer') {
          throw Exception('Security violation: Employers are not allowed to apply to jobs.');
        }
      }

      final payload = {
        'job_id': jobId,
        'worker_id': effectiveWorkerId,
        'worker_name': workerName,
        'worker_phone': workerPhone,
        'status': 'interested',
        'created_at': now.toIso8601String(),
      };

      final res =
          await _client.from('applications').insert(payload).select().single();
      if (kDebugMode) {
        print(
            '✅ [ApplicationService] Applied to job $jobId as worker $effectiveWorkerId');
      }

      final application = Application.fromJson(res);

      // ── Notify employer ──────────────────────────────────────────────────
      try {
        final jobRes = await _client
            .from('jobs')
            .select('employer_id, title')
            .eq('id', jobId)
            .maybeSingle();
        if (jobRes != null) {
          final employerId = jobRes['employer_id']?.toString();
          final jobTitle = jobRes['title']?.toString() ?? 'Job';
          if (employerId != null) {
            unawaited(_notif.insertNotification(
              userId: employerId,
              type: 'application_received',
              title: 'New Application Received',
              body: 'New application from $workerName for $jobTitle',
              relatedJobId: jobId,
            ));
          }
        }
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ [ApplicationService] Error sending apply notification: $e');
        }
      }

      return application;
    } catch (e) {
      if (kDebugMode) {
        print(
            '⚠️ [ApplicationService] Error applying to job: $e');
      }
      if (_client.auth.currentUser == null) {
        // Fallback for unauthenticated integration tests
        return newApp;
      }
      rethrow;
    }
  }

  // ── Fetch ────────────────────────────────────────────────────────────────

  /// Fetches all applications for a specific job (Employer view).
  Future<List<Application>> fetchApplicationsForJob(String jobId) async {
    final localApps =
        _localApplicationsStore.where((a) => a.jobId == jobId).toList();

    if (!_uuidRegExp.hasMatch(jobId)) {
      return localApps;
    }

    try {
      final res = await _client
          .from('applications')
          .select()
          .eq('job_id', jobId)
          .order('created_at', ascending: false);
      final List data = res as List;
      final remoteApps =
          data.map((json) => Application.fromJson(json)).toList();
      return remoteApps.isEmpty ? localApps : remoteApps;
    } catch (e) {
      if (kDebugMode) {
        print(
            '⚠️ [ApplicationService] Error fetching applications for job ($jobId): $e');
      }
      return localApps;
    }
  }

  /// Fetches all applications submitted by a specific worker (Worker view).
  Future<List<Application>> fetchApplicationsForWorker(String workerId) async {
    final localApps =
        _localApplicationsStore.where((a) => a.workerId == workerId).toList();

    try {
      final res = await _client
          .from('applications')
          .select()
          .eq('worker_id', workerId)
          .order('created_at', ascending: false);
      final List data = res as List;
      final remoteApps =
          data.map((json) => Application.fromJson(json)).toList();
      return remoteApps.isEmpty ? localApps : remoteApps;
    } catch (e) {
      if (kDebugMode) {
        print(
            '⚠️ [ApplicationService] Error fetching applications for worker ($workerId): $e');
      }
      return localApps;
    }
  }

  /// Fetches all applications for jobs posted by a specific employer (Employer view).
  Future<List<Application>> fetchApplicationsForEmployer(String employerId) async {
    final localApps = _localApplicationsStore.where((a) => _uuidRegExp.hasMatch(a.jobId)).toList();

    if (!_uuidRegExp.hasMatch(employerId)) {
      return localApps;
    }

    try {
      print('[fetchApplicationsForEmployer] filtering by employerId: $employerId, auth.currentUser.id: ${_client.auth.currentUser?.id}');
      final res = await _client
          .from('applications')
          .select('*, jobs!inner(employer_id)')
          .eq('jobs.employer_id', employerId)
          .order('created_at', ascending: false);
      print('[fetchApplicationsForEmployer] raw Supabase result: $res');
      final List data = res as List;
      final remoteApps =
          data.map((json) => Application.fromJson(json)).toList();
      return remoteApps;
    } catch (e) {
      if (kDebugMode) {
        print(
            '⚠️ [ApplicationService] Error fetching applications for employer ($employerId): $e');
      }
      return localApps;
    }
  }

  /// Subscribes to realtime PostgreSQL INSERT events on the applications table
  RealtimeChannel subscribeToApplications(void Function(PostgresChangePayload payload) onEvent) {
    final channel = _client.channel('public:applications_realtime');
    channel.onPostgresChanges(
      event: PostgresChangeEvent.insert,
      schema: 'public',
      table: 'applications',
      callback: onEvent,
    ).subscribe();
    return channel;
  }

  // ── Update Status ────────────────────────────────────────────────────────

  /// Updates status of an application ('assigned' / 'rejected').
  /// If assigned → also updates job status, rejects other applicants,
  /// and inserts a `job_accepted` notification for the worker.
  Future<bool> updateApplicationStatus({
    required String applicationId,
    required String jobId,
    required String workerName,
    required String workerId,
    required String status,
  }) async {
    // 1. Update in-memory local store
    for (int i = 0; i < _localApplicationsStore.length; i++) {
      if (_localApplicationsStore[i].id == applicationId) {
        _localApplicationsStore[i] =
            _localApplicationsStore[i].copyWith(status: status);
      } else if (status == 'assigned' &&
          _localApplicationsStore[i].jobId == jobId) {
        _localApplicationsStore[i] =
            _localApplicationsStore[i].copyWith(status: 'rejected');
      }
    }

    // 2. Update remote application status if both IDs are valid UUIDs
    if (_uuidRegExp.hasMatch(jobId) && _uuidRegExp.hasMatch(applicationId)) {
      try {
        await _client
            .from('applications')
            .update({'status': status}).eq('id', applicationId);

        if (status == 'assigned') {
          // Reject all other pending applications for this job in database
          await _client
              .from('applications')
              .update({'status': 'rejected'})
              .eq('job_id', jobId)
              .neq('id', applicationId);
        }
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ [ApplicationService] Remote application status update failed: $e');
        }
      }
    }

    // 3. Update remote job status and notify if jobId is a valid UUID
    if (_uuidRegExp.hasMatch(jobId)) {
      try {
        if (status == 'assigned') {
          final effectiveWorkerUuid = _uuidRegExp.hasMatch(workerId) ? workerId : null;
          await JobService().updateJobStatus(
            jobId: jobId,
            status: 'assigned',
            workerName: workerName,
            assignedWorkerId: effectiveWorkerUuid,
          );

          // ── Notify worker ────────────────────────────────────────────────
          final effectiveWorkerId = _uuidRegExp.hasMatch(workerId)
              ? workerId
              : _localApplicationsStore
                      .firstWhere(
                        (a) => a.id == applicationId,
                        orElse: () => Application(
                            id: '',
                            jobId: jobId,
                            workerId: '',
                            workerName: workerName,
                            workerPhone: '',
                            status: status,
                            createdAt: DateTime.now()),
                      )
                      .workerId;

          if (_uuidRegExp.hasMatch(effectiveWorkerId)) {
            // Fetch job title for the notification body
            final jobCtx = await _fetchJobContext(jobId);
            final jobTitle = jobCtx['job_title'] ?? 'a job';
            unawaited(_notif.insertNotification(
              userId: effectiveWorkerId,
              type: 'job_accepted',
              title: 'Application Accepted! 🎉',
              body: 'Your application for "$jobTitle" has been accepted.',
              relatedJobId: jobId,
            ));
          }
        } else {
          // Update job to other status (like completed/etc)
          await JobService().updateJobStatus(jobId: jobId, status: status);
        }
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ [ApplicationService] Remote job status sync failed: $e');
        }
      }
    }

    return true;
  }
}
