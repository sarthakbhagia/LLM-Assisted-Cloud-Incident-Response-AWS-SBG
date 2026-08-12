import 'package:timeago/timeago.dart' as timeago;

/// Maps to the `type` column values in the Supabase notifications table.
enum NotificationType {
  applicationReceived, // employer: worker applied to your job
  jobAccepted,         // worker: employer accepted your application
  jobCompleted,        // worker: job marked completed
  reviewReceived,      // worker: employer submitted a rating
  rateWorker,          // employer: prompt to rate a completed job
  system,              // general system / verification messages
  payment,             // wage / payout events
}

extension NotificationTypeX on NotificationType {
  String get dbValue {
    switch (this) {
      case NotificationType.applicationReceived:
        return 'application_received';
      case NotificationType.jobAccepted:
        return 'job_accepted';
      case NotificationType.jobCompleted:
        return 'job_completed';
      case NotificationType.reviewReceived:
        return 'review_received';
      case NotificationType.rateWorker:
        return 'rate_worker';
      case NotificationType.payment:
        return 'payment';
      case NotificationType.system:
        return 'system';
    }
  }

  static NotificationType fromDbValue(String? value) {
    switch (value) {
      case 'application_received':
        return NotificationType.applicationReceived;
      case 'job_accepted':
        return NotificationType.jobAccepted;
      case 'job_completed':
        return NotificationType.jobCompleted;
      case 'review_received':
        return NotificationType.reviewReceived;
      case 'rate_worker':
        return NotificationType.rateWorker;
      case 'payment':
        return NotificationType.payment;
      default:
        return NotificationType.system;
    }
  }
}

class NotificationItem {
  final String id;
  final String title;
  final String body;
  final DateTime createdAt;
  final NotificationType type;
  final bool isRead;
  final String? relatedJobId;

  const NotificationItem({
    required this.id,
    required this.title,
    required this.body,
    required this.createdAt,
    required this.type,
    this.isRead = false,
    this.relatedJobId,
  });

  /// Human-readable relative timestamp, e.g. "3 minutes ago"
  String get timestamp => timeago.format(createdAt);

  factory NotificationItem.fromJson(Map<String, dynamic> json) {
    return NotificationItem(
      id: json['id']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      body: json['body']?.toString() ?? '',
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      type: NotificationTypeX.fromDbValue(json['type']?.toString()),
      isRead: json['is_read'] == true,
      relatedJobId: json['related_job_id']?.toString(),
    );
  }

  NotificationItem copyWith({
    String? id,
    String? title,
    String? body,
    DateTime? createdAt,
    NotificationType? type,
    bool? isRead,
    String? relatedJobId,
  }) {
    return NotificationItem(
      id: id ?? this.id,
      title: title ?? this.title,
      body: body ?? this.body,
      createdAt: createdAt ?? this.createdAt,
      type: type ?? this.type,
      isRead: isRead ?? this.isRead,
      relatedJobId: relatedJobId ?? this.relatedJobId,
    );
  }
}
