class Application {
  final String id;
  final String jobId;
  final String workerId;
  final String workerName;
  final String workerPhone;
  final String status; // 'interested', 'assigned', 'rejected'
  final DateTime createdAt;

  const Application({
    required this.id,
    required this.jobId,
    required this.workerId,
    required this.workerName,
    required this.workerPhone,
    required this.status,
    required this.createdAt,
  });

  Application copyWith({
    String? id,
    String? jobId,
    String? workerId,
    String? workerName,
    String? workerPhone,
    String? status,
    DateTime? createdAt,
  }) {
    return Application(
      id: id ?? this.id,
      jobId: jobId ?? this.jobId,
      workerId: workerId ?? this.workerId,
      workerName: workerName ?? this.workerName,
      workerPhone: workerPhone ?? this.workerPhone,
      status: status ?? this.status,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  factory Application.fromJson(Map<String, dynamic> json) {
    return Application(
      id: json['id']?.toString() ?? '',
      jobId: json['job_id']?.toString() ?? '',
      workerId: json['worker_id']?.toString() ?? '',
      workerName: json['worker_name'] ?? 'Worker',
      workerPhone: json['worker_phone'] ?? '',
      status: json['status'] ?? 'interested',
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      if (id.isNotEmpty && !id.startsWith('app-')) 'id': id,
      'job_id': jobId,
      'worker_id': workerId,
      'worker_name': workerName,
      'worker_phone': workerPhone,
      'status': status,
      'created_at': createdAt.toIso8601String(),
    };
  }
}
