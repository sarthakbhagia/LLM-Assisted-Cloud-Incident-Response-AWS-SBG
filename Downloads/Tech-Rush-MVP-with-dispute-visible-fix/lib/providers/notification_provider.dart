import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/notification_item.dart';
import '../services/notification_service.dart';

final _notificationService = NotificationService();

/// Resolves the current authenticated user's ID, or empty string if not logged in.
String _currentUserId() =>
    Supabase.instance.client.auth.currentUser?.id ?? '';

// ── Read Providers ────────────────────────────────────────────────────────

/// Fetches all notifications for the current user, ordered newest-first.
/// Watch this in the notifications screen and the bell badge.
final notificationsProvider = FutureProvider<List<NotificationItem>>((ref) async {
  final userId = _currentUserId();
  if (userId.isEmpty) return [];

  // Subscribe to realtime changes on notifications table for this user
  final channel = _notificationService.subscribeToNotifications(
    userId: userId,
    onEvent: (payload) {
      ref.invalidateSelf();
    },
  );

  // Clean up and unsubscribe on dispose
  ref.onDispose(() {
    channel.unsubscribe();
  });

  return _notificationService.fetchNotifications(userId);
});

/// Real unread count from Supabase (used for the bell badge in the app bar).
final unreadNotificationCountProvider = FutureProvider<int>((ref) async {
  // Derive from notificationsProvider so both stay in sync without extra query.
  final notifs = await ref.watch(notificationsProvider.future);
  return notifs.where((n) => !n.isRead).length;
});

// ── Write Actions ─────────────────────────────────────────────────────────

/// Marks one notification as read, then invalidates the list provider
/// so the bell badge and list both update.
Future<void> markNotificationRead(WidgetRef ref, String notificationId) async {
  await _notificationService.markAsRead(notificationId);
  ref.invalidate(notificationsProvider);
}

/// Marks all notifications read, then invalidates.
Future<void> markAllNotificationsRead(WidgetRef ref) async {
  final userId = _currentUserId();
  if (userId.isEmpty) return;
  await _notificationService.markAllAsRead(userId);
  ref.invalidate(notificationsProvider);
}
