import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/notification_item.dart';
import 'supabase_service.dart';

/// Service for all Supabase interactions with the `notifications` table.
///
/// All public methods are fire-and-forget safe — they catch exceptions
/// internally and log them in debug mode so that a notification failure
/// never crashes the triggering action (apply, accept, complete, review).
class NotificationService {
  final SupabaseClient _client = SupabaseService().client;

  static final RegExp _uuidRegExp = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  // ── Write ────────────────────────────────────────────────────────────────

  /// Inserts a notification row for [userId].
  /// Silently swallows errors so callers are never blocked.
  Future<void> insertNotification({
    required String userId,
    required String type,
    required String title,
    required String body,
    String? relatedJobId,
  }) async {
    if (!_uuidRegExp.hasMatch(userId)) {
      if (kDebugMode) {
        print('⚠️ [NotificationService] Skipping insert — userId is not a UUID: $userId');
      }
      return;
    }

    try {
      final payload = <String, dynamic>{
        'user_id': userId,
        'type': type,
        'title': title,
        'body': body,
        'is_read': false,
      };
      if (relatedJobId != null && _uuidRegExp.hasMatch(relatedJobId)) {
        payload['related_job_id'] = relatedJobId;
      }

      await _client.from('notifications').insert(payload);
      if (kDebugMode) {
        print('✅ [NotificationService] Inserted [$type] notification for user $userId');
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [NotificationService] insertNotification failed: $e');
      }
    }
  }

  /// Marks a single notification as read.
  Future<void> markAsRead(String notificationId) async {
    if (!_uuidRegExp.hasMatch(notificationId)) return;
    try {
      await _client
          .from('notifications')
          .update({'is_read': true})
          .eq('id', notificationId);
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [NotificationService] markAsRead failed: $e');
      }
    }
  }

  /// Marks all notifications for [userId] as read.
  Future<void> markAllAsRead(String userId) async {
    if (!_uuidRegExp.hasMatch(userId)) return;
    try {
      await _client
          .from('notifications')
          .update({'is_read': true})
          .eq('user_id', userId)
          .eq('is_read', false);
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [NotificationService] markAllAsRead failed: $e');
      }
    }
  }

  // ── Read ─────────────────────────────────────────────────────────────────

  /// Fetches all notifications for [userId], newest first.
  Future<List<NotificationItem>> fetchNotifications(String userId) async {
    if (!_uuidRegExp.hasMatch(userId)) return [];
    try {
      final res = await _client
          .from('notifications')
          .select()
          .eq('user_id', userId)
          .order('created_at', ascending: false)
          .limit(50);

      final List rows = res as List;
      return rows.map((json) => NotificationItem.fromJson(json)).toList();
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [NotificationService] fetchNotifications failed: $e');
      }
      return [];
    }
  }

  /// Returns the count of unread notifications for [userId].
  Future<int> fetchUnreadCount(String userId) async {
    if (!_uuidRegExp.hasMatch(userId)) return 0;
    try {
      final res = await _client
          .from('notifications')
          .select()
          .eq('user_id', userId)
          .eq('is_read', false);
      return (res as List).length;
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [NotificationService] fetchUnreadCount failed: $e');
      }
      return 0;
    }
  }

  /// Subscribes to realtime PostgreSQL INSERT/UPDATE/DELETE events on the notifications table for a specific user ID
  RealtimeChannel subscribeToNotifications({
    required String userId,
    required void Function(PostgresChangePayload payload) onEvent,
  }) {
    if (kDebugMode) {
      print('⚡ [NotificationService] Subscribing to realtime notifications for user $userId');
    }
    final channel = _client.channel('public:notifications_user_$userId');
    channel.onPostgresChanges(
      event: PostgresChangeEvent.all,
      schema: 'public',
      table: 'notifications',
      filter: PostgresChangeFilter(
        type: PostgresChangeFilterType.eq,
        column: 'user_id',
        value: userId,
      ),
      callback: onEvent,
    ).subscribe((status, [error]) {
      if (kDebugMode) {
        print('⚡ [NotificationService] Realtime subscription status: $status, error: $error');
      }
    });
    return channel;
  }
}
