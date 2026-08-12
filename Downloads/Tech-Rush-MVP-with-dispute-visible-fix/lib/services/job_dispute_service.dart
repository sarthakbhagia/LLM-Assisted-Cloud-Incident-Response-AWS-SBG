import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/job_dispute.dart';
import 'notification_service.dart';
import 'supabase_service.dart';

class JobDisputeService {
  final SupabaseClient _client = SupabaseService().client;
  final NotificationService _notifications = NotificationService();

  static final List<JobDispute> _localStore = [];
  static final RegExp _uuidRegExp = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  Future<JobDispute?> fetchMyDispute({
    required String jobId,
    required String reporterId,
  }) async {
    final local = _localStore.where(
      (d) => d.jobId == jobId && d.reporterId == reporterId,
    );
    if (local.isNotEmpty) return local.last;

    if (!_uuidRegExp.hasMatch(jobId) || !_uuidRegExp.hasMatch(reporterId)) {
      return null;
    }

    try {
      final res = await _client
          .from('job_disputes')
          .select()
          .eq('job_id', jobId)
          .eq('reporter_id', reporterId)
          .maybeSingle();
      return res == null ? null : JobDispute.fromJson(res);
    } catch (e) {
      if (kDebugMode) print('⚠️ [JobDisputeService] Fetch error: $e');
      return null;
    }
  }

  Future<JobDispute?> submitDispute({
    required String jobId,
    required String reporterId,
    required String reporterRole,
    required String category,
    required String description,
    String? otherPartyId,
    String? jobTitle,
  }) async {
    final now = DateTime.now();
    final local = JobDispute(
      id: 'dispute_${now.millisecondsSinceEpoch}',
      jobId: jobId,
      reporterId: reporterId,
      reporterRole: reporterRole,
      category: category,
      description: description.trim(),
      status: 'under_review',
      createdAt: now,
    );

    _localStore.removeWhere(
      (d) => d.jobId == jobId && d.reporterId == reporterId,
    );
    _localStore.add(local);

    if (!_uuidRegExp.hasMatch(jobId) || !_uuidRegExp.hasMatch(reporterId)) {
      return local;
    }

    try {
      final payload = {
        'job_id': jobId,
        'reporter_id': reporterId,
        'reporter_role': reporterRole,
        'category': category,
        'description': description.trim(),
      };

      final res = await _client
          .from('job_disputes')
          .insert(payload)
          .select()
          .single();
      final dispute = JobDispute.fromJson(res);

      if (otherPartyId != null && _uuidRegExp.hasMatch(otherPartyId)) {
        await _notifications.insertNotification(
          userId: otherPartyId,
          type: 'job_dispute_reported',
          title: 'Issue Reported on a Completed Job',
          body: 'A dispute was submitted for "${jobTitle ?? 'your completed job'}" and is under review.',
          relatedJobId: jobId,
        );
      }

      return dispute;
    } catch (e) {
      if (kDebugMode) print('⚠️ [JobDisputeService] Submit error: $e');
      // Keep the local result so the demo still shows the reported state if
      // the backend migration has not been applied yet.
      return local;
    }
  }

  Future<List<JobDispute>> fetchDisputesForJob({required String jobId}) async {
    final local = _localStore.where((d) => d.jobId == jobId).toList();
    if (!_uuidRegExp.hasMatch(jobId)) {
      return local;
    }

    try {
      final res = await _client
          .from('job_disputes')
          .select()
          .eq('job_id', jobId);
      final List data = res as List;
      final remote = data.map((json) => JobDispute.fromJson(json)).toList();
      
      // Merge unique entries prioritizing database ones, but keeping local ones
      final Map<String, JobDispute> merged = {};
      for (final dispute in local) {
        merged[dispute.reporterId] = dispute;
      }
      for (final dispute in remote) {
        merged[dispute.reporterId] = dispute;
      }
      return merged.values.toList();
    } catch (e) {
      if (kDebugMode) print('⚠️ [JobDisputeService] Fetch disputes for job error: $e');
      return local;
    }
  }
}
