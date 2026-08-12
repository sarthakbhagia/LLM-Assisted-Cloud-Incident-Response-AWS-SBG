import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'supabase_service.dart';
import 'notification_service.dart';

/// Represents the result of a thumbs-up / thumbs-down rating submission.
class RatingResult {
  final bool success;
  final String? errorMessage;
  const RatingResult({required this.success, this.errorMessage});
}

/// Model representing aggregate rating summary from Supabase view or local store.
class MutualRatingSummary {
  final int totalRatings;
  final int thumbsUpCount;
  final int? thumbsUpPercentage;

  const MutualRatingSummary({
    required this.totalRatings,
    required this.thumbsUpCount,
    this.thumbsUpPercentage,
  });
}

/// Service for the dual 👍 / 👎 thumbs-based rating system.
///
class RatingService {
  SupabaseClient get _client => SupabaseService().client;
  NotificationService get _notif => NotificationService();

  static final RegExp _uuidRegExp = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  bool get _hasActiveSession {
    if (!SupabaseService.isInitialized) return false;
    try {
      return SupabaseService().client.auth.currentSession != null;
    } catch (_) {
      return false;
    }
  }

  // ── In-memory fallback store for demo / offline mode ────────────────────
  static final List<Map<String, dynamic>> _localStore = [];

  /// Submits a 👍 or 👎 rating.
  ///
  /// [jobId]       — UUID of the completed job.
  /// [raterId]     — UUID of the person giving the rating.
  /// [rateeId]     — UUID of the person being rated.
  /// [raterRole]   — Role of the rater ('employer' or 'worker').
  /// [isThumbsUp]  — true = 👍, false = 👎.
  Future<RatingResult> submitRating({
    required String jobId,
    required String raterId,
    required String rateeId,
    required String raterRole,
    required bool isThumbsUp,
  }) async {
    final ratingType = isThumbsUp ? 'thumbs_up' : 'thumbs_down';

    // Always persist locally for instant UI feedback
    _localStore.removeWhere((r) =>
        r['job_id'] == jobId &&
        r['rater_id'] == raterId &&
        r['ratee_id'] == rateeId);
    _localStore.add({
      'job_id': jobId,
      'rater_id': raterId,
      'ratee_id': rateeId,
      'rater_role': raterRole,
      'thumbs_up': isThumbsUp,
      'rating_type': ratingType,
      'created_at': DateTime.now().toIso8601String(),
    });

    // Skip DB writes when IDs are non-UUIDs or user is not logged in (demo/offline mode)
    if (!_hasActiveSession ||
        !_uuidRegExp.hasMatch(jobId) ||
        !_uuidRegExp.hasMatch(raterId) ||
        !_uuidRegExp.hasMatch(rateeId)) {
      if (kDebugMode) {
        print('ℹ️ [RatingService] Demo/Offline mode — rating stored locally only.');
      }
      return const RatingResult(success: true);
    }

    try {
      // Insert into new job_ratings table
      await _client.from('job_ratings').insert({
        'job_id': jobId,
        'rater_id': raterId,
        'ratee_id': rateeId,
        'rater_role': raterRole,
        'thumbs_up': isThumbsUp,
      });

      if (kDebugMode) {
        print(
            '✅ [RatingService] Submitted thumbs_up=$isThumbsUp for target $rateeId on job $jobId');
      }

      // Fetch rater name for personalized notification body
      String raterName = 'Someone';
      if (_uuidRegExp.hasMatch(raterId)) {
        try {
          final profileRes = await _client
              .from('profiles')
              .select('full_name')
              .eq('id', raterId)
              .maybeSingle();
          if (profileRes != null && profileRes['full_name'] != null) {
            raterName = profileRes['full_name'].toString();
          }
        } catch (_) {}
      }

      // Fire-and-forget notification to the target user
      final emoji = isThumbsUp ? '👍' : '👎';
      unawaited(_notif.insertNotification(
        userId: rateeId,
        type: 'rating_received',
        title: 'You Received a Rating $emoji',
        body: 'You received a new rating from $raterName',
        relatedJobId: jobId,
      ));

      return const RatingResult(success: true);
    } on PostgrestException catch (e) {
      // Code 23505 = unique constraint violation (already rated)
      if (e.code == '23505') {
        if (kDebugMode) {
          print('ℹ️ [RatingService] Already rated this job/rater combination.');
        }
        return const RatingResult(
          success: false,
          errorMessage: 'You have already submitted a rating for this job.',
        );
      }
      if (kDebugMode) {
        print('⚠️ [RatingService] PostgrestException: ${e.message}');
      }
      return RatingResult(success: false, errorMessage: e.message);
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [RatingService] Error submitting rating: $e');
      }
      // Return success true for network errors so UX isn't blocked
      return const RatingResult(success: true);
    }
  }

  /// Checks if [raterId] has already rated for [jobId].
  Future<bool> hasRated({
    required String jobId,
    required String raterId,
  }) async {
    // Check local store first
    final localMatch = _localStore.any((r) =>
        r['job_id'] == jobId &&
        r['rater_id'] == raterId);
    if (localMatch) return true;

    if (!_hasActiveSession ||
        !_uuidRegExp.hasMatch(jobId) ||
        !_uuidRegExp.hasMatch(raterId)) {
      return false;
    }

    try {
      final res = await _client
          .from('job_ratings')
          .select('id')
          .eq('job_id', jobId)
          .eq('rater_id', raterId)
          .maybeSingle();
      return res != null;
    } catch (_) {
      return false;
    }
  }

  /// Fetches thumbs summary (total ratings, thumbs up count, and percentage) for a user from the view.
  Future<MutualRatingSummary> fetchThumbsSummary(String targetId) async {
    // Local store calculations first
    final localUp = _localStore
        .where((r) =>
            r['ratee_id'] == targetId && r['rating_type'] == 'thumbs_up')
        .length;
    final localDown = _localStore
        .where((r) =>
            r['ratee_id'] == targetId && r['rating_type'] == 'thumbs_down')
        .length;
    final localTotal = localUp + localDown;
    final localPct = localTotal > 0 ? ((localUp / localTotal) * 100).round() : null;

    if (!_hasActiveSession ||
        !_uuidRegExp.hasMatch(targetId)) {
      return MutualRatingSummary(
        totalRatings: localTotal,
        thumbsUpCount: localUp,
        thumbsUpPercentage: localPct,
      );
    }

    try {
      final res = await _client
          .from('mutual_rating_summary')
          .select('total_ratings, thumbs_up_count, thumbs_up_percentage')
          .eq('user_id', targetId)
          .maybeSingle();

      if (res == null) {
        return MutualRatingSummary(
          totalRatings: localTotal,
          thumbsUpCount: localUp,
          thumbsUpPercentage: localPct,
        );
      }

      final dbTotal = (res['total_ratings'] as num?)?.toInt() ?? 0;
      final dbUp = (res['thumbs_up_count'] as num?)?.toInt() ?? 0;

      final total = dbTotal + localTotal;
      final upCount = dbUp + localUp;
      final pct = total > 0 ? ((upCount / total) * 100).round() : null;

      return MutualRatingSummary(
        totalRatings: total,
        thumbsUpCount: upCount,
        thumbsUpPercentage: pct,
      );
    } catch (_) {
      return MutualRatingSummary(
        totalRatings: localTotal,
        thumbsUpCount: localUp,
        thumbsUpPercentage: localPct,
      );
    }
  }
}

/// Fire-and-forget helper — prevents unawaited lint.
void unawaited(Future<void> future) {}
