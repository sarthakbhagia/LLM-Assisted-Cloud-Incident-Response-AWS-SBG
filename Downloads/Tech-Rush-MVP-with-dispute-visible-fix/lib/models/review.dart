class Review {
  final String id;
  final String jobId;
  final String workerId;
  final String employerId;
  final int rating; // 1-5
  final String? comment;
  final DateTime createdAt;

  const Review({
    required this.id,
    required this.jobId,
    required this.workerId,
    required this.employerId,
    required this.rating,
    this.comment,
    required this.createdAt,
  });

  factory Review.fromJson(Map<String, dynamic> json) {
    return Review(
      id: json['id']?.toString() ?? '',
      jobId: json['job_id']?.toString() ?? '',
      workerId: json['worker_id']?.toString() ?? '',
      employerId: json['employer_id']?.toString() ?? '',
      rating: (json['rating'] as num?)?.toInt() ?? 5,
      comment: json['comment'] as String?,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      if (id.isNotEmpty && !id.startsWith('rev_')) 'id': id,
      'job_id': jobId,
      'worker_id': workerId,
      'employer_id': employerId,
      'rating': rating,
      if (comment != null) 'comment': comment,
      'created_at': createdAt.toIso8601String(),
    };
  }
}

class WorkerRatingSummary {
  final double averageRating;
  final int totalReviews;
  final Map<int, int> starDistribution; // e.g. {5: 18, 4: 4, 3: 2, 2: 0, 1: 0}

  const WorkerRatingSummary({
    required this.averageRating,
    required this.totalReviews,
    required this.starDistribution,
  });

  factory WorkerRatingSummary.empty() {
    return const WorkerRatingSummary(
      averageRating: 0.0,
      totalReviews: 0,
      starDistribution: {5: 0, 4: 0, 3: 0, 2: 0, 1: 0},
    );
  }
}
