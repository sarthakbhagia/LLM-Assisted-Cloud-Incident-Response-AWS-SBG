import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/review.dart';
import 'supabase_service.dart';
import 'notification_service.dart';

class ReviewService {
  final SupabaseClient _client = SupabaseService().client;
  final NotificationService _notif = NotificationService();
  static final List<Review> _localReviewsStore = [];
  static final RegExp _uuidRegExp = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  /// Submits a review (employer -> worker only)
  Future<Review?> submitReview({
    required String jobId,
    required String workerId,
    required int rating,
    String? comment,
  }) async {
    final user = _client.auth.currentUser;
    final employerId = user?.id ?? 'demo_employer';

    final now = DateTime.now();
    final newReview = Review(
      id: 'rev_${now.millisecondsSinceEpoch}',
      jobId: jobId,
      workerId: workerId,
      employerId: employerId,
      rating: rating.clamp(1, 5),
      comment: comment,
      createdAt: now,
    );

    // Save locally in fallback store
    _localReviewsStore.removeWhere((r) => r.jobId == jobId && r.employerId == employerId);
    _localReviewsStore.add(newReview);

    if (!_uuidRegExp.hasMatch(jobId) || !_uuidRegExp.hasMatch(workerId)) {
      return newReview;
    }

    try {
      final payload = {
        'job_id': jobId,
        'worker_id': workerId,
        'employer_id': employerId,
        'rating': rating.clamp(1, 5),
        if (comment != null && comment.trim().isNotEmpty) 'comment': comment.trim(),
        'created_at': now.toIso8601String(),
      };

      final res = await _client.from('reviews').insert(payload).select().single();
      final review = Review.fromJson(res);
      if (kDebugMode) {
        print('✅ [ReviewService] Submitted review for worker $workerId: ${res['id']}');
      }

      // Fetch employer name for personalized notification body
      String employerName = 'An employer';
      if (_uuidRegExp.hasMatch(employerId)) {
        try {
          final profileRes = await _client
              .from('profiles')
              .select('full_name')
              .eq('id', employerId)
              .maybeSingle();
          if (profileRes != null && profileRes['full_name'] != null) {
            employerName = profileRes['full_name'].toString();
          }
        } catch (_) {}
      }

      // ── Notify worker ────────────────────────────────────────────────────
      unawaited(_notif.insertNotification(
        userId: workerId,
        type: 'review_received',
        title: 'You Received a New Review ⭐',
        body: 'You received a new rating from $employerName',
        relatedJobId: jobId,
      ));

      return review;
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [ReviewService] Error submitting review (using local store): $e');
      }
      return newReview;
    }
  }

  /// Computes worker rating summary (average rating, count, star distribution)
  Future<WorkerRatingSummary> fetchWorkerRatingSummary(String workerId) async {
    List<Review> reviews = [];

    if (_uuidRegExp.hasMatch(workerId)) {
      try {
        final res = await _client
            .from('reviews')
            .select()
            .eq('worker_id', workerId);
        final List data = res as List;
        reviews = data.map((json) => Review.fromJson(json)).toList();
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ [ReviewService] Error fetching reviews for worker ($workerId): $e');
        }
      }
    }

    // Combine local store reviews if empty or for demo workers
    if (reviews.isEmpty) {
      reviews = _localReviewsStore.where((r) => r.workerId == workerId).toList();
    }

    if (reviews.isEmpty) {
      return WorkerRatingSummary.empty();
    }

    int totalCount = reviews.length;
    double sumRating = reviews.fold(0.0, (sum, r) => sum + r.rating);
    double avgRating = double.parse((sumRating / totalCount).toStringAsFixed(1));

    Map<int, int> distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0};
    for (var r in reviews) {
      int rKey = r.rating.clamp(1, 5);
      distribution[rKey] = (distribution[rKey] ?? 0) + 1;
    }

    return WorkerRatingSummary(
      averageRating: avgRating,
      totalReviews: totalCount,
      starDistribution: distribution,
    );
  }

  /// Fetches individual reviews for worker
  Future<List<Review>> fetchReviewsForWorker(String workerId) async {
    if (_uuidRegExp.hasMatch(workerId)) {
      try {
        final res = await _client
            .from('reviews')
            .select()
            .eq('worker_id', workerId)
            .order('created_at', ascending: false);
        final List data = res as List;
        return data.map((json) => Review.fromJson(json)).toList();
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ [ReviewService] Error fetching reviews: $e');
        }
      }
    }
    return _localReviewsStore.where((r) => r.workerId == workerId).toList();
  }
}

/// Fire-and-forget helper.
void unawaited(Future<void> future) {}
