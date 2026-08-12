class JobDispute {
  final String id;
  final String jobId;
  final String reporterId;
  final String reporterRole;
  final String category;
  final String description;
  final String status;
  final DateTime createdAt;
  final DateTime? resolvedAt;
  final String? resolutionNote;

  const JobDispute({
    required this.id,
    required this.jobId,
    required this.reporterId,
    required this.reporterRole,
    required this.category,
    required this.description,
    required this.status,
    required this.createdAt,
    this.resolvedAt,
    this.resolutionNote,
  });

  factory JobDispute.fromJson(Map<String, dynamic> json) {
    return JobDispute(
      id: json['id'].toString(),
      jobId: json['job_id'].toString(),
      reporterId: json['reporter_id'].toString(),
      reporterRole: json['reporter_role']?.toString() ?? 'worker',
      category: json['category']?.toString() ?? 'Other',
      description: json['description']?.toString() ?? '',
      status: json['status']?.toString() ?? 'under_review',
      createdAt: DateTime.tryParse(json['created_at']?.toString() ?? '') ?? DateTime.now(),
      resolvedAt: DateTime.tryParse(json['resolved_at']?.toString() ?? ''),
      resolutionNote: json['resolution_note']?.toString(),
    );
  }
}
