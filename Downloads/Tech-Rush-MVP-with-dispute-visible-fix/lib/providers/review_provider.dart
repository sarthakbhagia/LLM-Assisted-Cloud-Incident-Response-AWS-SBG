import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/review.dart';
import '../services/review_service.dart';
import '../services/rating_service.dart';

final reviewServiceProvider = Provider<ReviewService>((ref) {
  return ReviewService();
});

final ratingServiceProvider = Provider<RatingService>((ref) {
  return RatingService();
});

final workerRatingSummaryProvider =
    FutureProvider.family<WorkerRatingSummary, String>((ref, workerId) async {
  final service = ref.watch(reviewServiceProvider);
  return service.fetchWorkerRatingSummary(workerId);
});

final workerReviewsProvider =
    FutureProvider.family<List<Review>, String>((ref, workerId) async {
  final service = ref.watch(reviewServiceProvider);
  return service.fetchReviewsForWorker(workerId);
});

/// Holds the mutual thumbs rating summary for a given user ID.
final mutualRatingSummaryProvider =
    FutureProvider.family<MutualRatingSummary, String>((ref, userId) async {
  final service = ref.watch(ratingServiceProvider);
  return service.fetchThumbsSummary(userId);
});

/// Checks if a rater has already rated a job.
final hasRatedProvider =
    FutureProvider.family<bool, ({String jobId, String raterId})>((ref, arg) async {
  final service = ref.watch(ratingServiceProvider);
  return service.hasRated(jobId: arg.jobId, raterId: arg.raterId);
});
