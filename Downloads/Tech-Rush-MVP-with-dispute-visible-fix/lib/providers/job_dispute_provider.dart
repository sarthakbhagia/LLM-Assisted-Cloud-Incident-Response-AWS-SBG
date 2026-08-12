import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/job_dispute.dart';
import '../services/job_dispute_service.dart';

final jobDisputeServiceProvider = Provider<JobDisputeService>((ref) {
  return JobDisputeService();
});

final myJobDisputeProvider = FutureProvider.family<JobDispute?, ({String jobId, String reporterId})>(
  (ref, arg) async {
    return ref.read(jobDisputeServiceProvider).fetchMyDispute(
          jobId: arg.jobId,
          reporterId: arg.reporterId,
        );
  },
);

final jobDisputesProvider = FutureProvider.family<List<JobDispute>, String>(
  (ref, jobId) async {
    return ref.read(jobDisputeServiceProvider).fetchDisputesForJob(jobId: jobId);
  },
);
