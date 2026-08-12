import 'package:flutter_test/flutter_test.dart';
import 'package:kaamsetu/services/rating_service.dart';

void main() {
  group('RatingService Unit Tests', () {
    late RatingService ratingService;

    setUp(() {
      ratingService = RatingService();
    });

    test('submitRating stores locally and returns success', () async {
      final result = await ratingService.submitRating(
        jobId: 'demo-job-1',
        raterId: 'demo-rater-1',
        rateeId: 'demo-ratee-1',
        raterRole: 'employer',
        isThumbsUp: true,
      );

      expect(result.success, true);
    });

    test('hasRated returns correct status from local store', () async {
      await ratingService.submitRating(
        jobId: 'demo-job-2',
        raterId: 'demo-rater-2',
        rateeId: 'demo-ratee-2',
        raterRole: 'worker',
        isThumbsUp: false,
      );

      final hasRated = await ratingService.hasRated(
        jobId: 'demo-job-2',
        raterId: 'demo-rater-2',
      );

      expect(hasRated, true);
    });

    test('fetchThumbsSummary aggregates local ratings correctly', () async {
      final targetId = 'unique-ratee-999';

      await ratingService.submitRating(
        jobId: 'job-a',
        raterId: 'rater-a',
        rateeId: targetId,
        raterRole: 'employer',
        isThumbsUp: true,
      );

      await ratingService.submitRating(
        jobId: 'job-b',
        raterId: 'rater-b',
        rateeId: targetId,
        raterRole: 'employer',
        isThumbsUp: true,
      );

      await ratingService.submitRating(
        jobId: 'job-c',
        raterId: 'rater-c',
        rateeId: targetId,
        raterRole: 'worker',
        isThumbsUp: false,
      );

      final summary = await ratingService.fetchThumbsSummary(targetId);

      expect(summary.totalRatings, 3);
      expect(summary.thumbsUpCount, 2);
      expect(summary.thumbsUpPercentage, 67); // (2/3) * 100 = 66.666 -> rounded to 67
    });
  });
}
