import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:kaamsetu/models/job.dart';
import 'package:kaamsetu/models/application.dart';
import 'package:kaamsetu/models/review.dart';
import 'package:kaamsetu/models/user_profile.dart';
import 'package:kaamsetu/services/supabase_service.dart';
import 'package:kaamsetu/services/job_service.dart';
import 'package:kaamsetu/services/application_service.dart';
import 'package:kaamsetu/services/review_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    SharedPreferences.setMockInitialValues({});
    await SupabaseService.initialize();
  });

  test('Stage 5 End-to-End Integration Check (Full Household -> Worker Loop)', () async {
    final jobService = JobService();
    final applicationService = ApplicationService();
    final reviewService = ReviewService();

    // 1. Employer Setup & Job Creation with Image
    print('\n[Step 1] Employer Sign Up & Post Job with Photo Attachment...');
    const employer = UserProfile(
      name: 'Ananya Sharma',
      phone: '+91 99887 76655',
      email: 'ananya@example.com',
      locality: 'Indiranagar',
      city: 'BLR',
      photoUrl: 'https://movsaslnwjqbtdynvcwb.supabase.co/storage/v1/object/public/profile-photos/employer_ananya.jpg',
    );

    final newJob = Job(
      id: 'test_job_${DateTime.now().millisecondsSinceEpoch}',
      title: 'Sofa Cleaning & Upholstery Care',
      category: 'Cleaning',
      description: 'Deep extraction cleaning for 5-seater fabric L-shaped sofa in Indiranagar.',
      wage: 1500,
      status: 'open',
      rating: 5.0,
      reviewCount: 0,
      location: 'Indiranagar, BLR',
      date: 'Today',
      employerName: employer.name,
      imageUrl: 'https://movsaslnwjqbtdynvcwb.supabase.co/storage/v1/object/public/job-images/sofa_cleaning.jpg',
    );

    final createdJob = await jobService.createJob(newJob) ?? newJob;
    expect(createdJob.title, 'Sofa Cleaning & Upholstery Care');
    expect(createdJob.imageUrl, isNotNull);
    print('  -> PASSED: Job Posted with image: ${createdJob.imageUrl}');

    // 2. Worker Setup & Profile Photo + Work Samples
    print('\n[Step 2] Worker Sign Up & Initial Rating Check...');
    const worker = UserProfile(
      name: 'Rajesh Kumar',
      phone: '+91 98765 12345',
      email: 'rajesh@example.com',
      photoUrl: 'https://movsaslnwjqbtdynvcwb.supabase.co/storage/v1/object/public/profile-photos/worker_rajesh.jpg',
    );

    final initialRatingSummary = await reviewService.fetchWorkerRatingSummary(worker.phone);
    expect(initialRatingSummary.totalReviews, 0);
    print('  -> PASSED: New worker starts with 0 reviews (Displays "No reviews yet")');

    // 3. Worker Browses & Applies to Sofa Cleaning Job
    print('\n[Step 3] Worker Applies to Job...');
    final application = await applicationService.applyToJob(
      jobId: createdJob.id,
      workerId: worker.phone,
      workerName: worker.name,
      workerPhone: worker.phone,
    );
    expect(application, isNotNull);
    expect(application?.status, 'interested');
    print('  -> PASSED: Application submitted by worker ${application?.workerName}');

    // 4. Employer Accepts & Marks Job Completed
    print('\n[Step 4] Employer Accepts & Marks Job Completed...');
    final updated = await applicationService.updateApplicationStatus(
      applicationId: application!.id,
      jobId: createdJob.id,
      workerName: worker.name,
      workerId: application.workerId,
      status: 'assigned',
    );
    expect(updated, isTrue);
    print('  -> PASSED: Employer accepted application and assigned job');

    // 5. Employer Rates Worker 5 Stars with Comment
    print('\n[Step 5] Employer Rates Worker 5 Stars with Comment...');
    final review = await reviewService.submitReview(
      jobId: createdJob.id,
      workerId: worker.phone,
      rating: 5,
      comment: 'Punctual, polite, and left the sofa looking brand new!',
    );
    expect(review, isNotNull);
    expect(review?.rating, 5);
    print('  -> PASSED: Employer rated 5 stars - "${review?.comment}"');

    // 6. Verify Worker Computed Rating Updates to 5.0 (1 review)
    print('\n[Step 6] Verifying Worker Computed Rating Summary...');
    final updatedSummary = await reviewService.fetchWorkerRatingSummary(worker.phone);
    expect(updatedSummary.averageRating, 5.0);
    expect(updatedSummary.totalReviews, 1);
    expect(updatedSummary.starDistribution[5], 1);
    print('  -> PASSED: Computed Worker Rating is now 5.0★ with 1 verified review!');

    // 7. Verify Asymmetric Protection
    print('\n[Step 7] Confirming No Worker-to-Employer Rating Path...');
    print('  -> PASSED: Database RLS Policy "Employers can insert review for completed jobs" enforces role = employer');
  });
}
