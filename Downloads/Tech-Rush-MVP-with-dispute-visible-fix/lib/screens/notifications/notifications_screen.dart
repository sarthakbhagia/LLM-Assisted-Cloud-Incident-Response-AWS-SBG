import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/theme.dart';
import '../../core/spacing.dart';
import '../../models/notification_item.dart';
import '../../providers/notification_provider.dart';
import '../../widgets/empty_state.dart';
import '../../l10n/app_localizations.dart';

class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  IconData _getTypeIcon(NotificationType type) {
    switch (type) {
      case NotificationType.applicationReceived:
        return Icons.person_add_rounded;
      case NotificationType.jobAccepted:
        return Icons.check_circle_rounded;
      case NotificationType.jobCompleted:
        return Icons.task_alt_rounded;
      case NotificationType.reviewReceived:
        return Icons.star_rounded;
      case NotificationType.rateWorker:
        return Icons.rate_review_rounded;
      case NotificationType.payment:
        return Icons.account_balance_wallet_rounded;
      case NotificationType.system:
        return Icons.verified_user_rounded;
    }
  }

  Color _getTypeColor(NotificationType type) {
    switch (type) {
      case NotificationType.applicationReceived:
        return AppColors.brand;
      case NotificationType.jobAccepted:
        return AppColors.success;
      case NotificationType.jobCompleted:
        return AppColors.success;
      case NotificationType.reviewReceived:
        return AppColors.warning;
      case NotificationType.rateWorker:
        return AppColors.warning;
      case NotificationType.payment:
        return AppColors.success;
      case NotificationType.system:
        return const Color(0xFF2563EB);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final notifsAsync = ref.watch(notificationsProvider);
    final unreadCountAsync = ref.watch(unreadNotificationCountProvider);
    final unreadCount = unreadCountAsync.valueOrNull ?? 0;

    return Scaffold(
      backgroundColor: AppColors.canvas,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: AppColors.inkPrimary),
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go('/dashboard');
            }
          },
        ),
        title: Row(
          children: [
            Text(
              l10n.notificationsTitle,
              style: GoogleFonts.sora(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppColors.inkPrimary,
              ),
            ),
            if (unreadCount > 0) ...[
              const SizedBox(width: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.brandSubtle,
                  borderRadius: AppRadii.pill,
                  border:
                      Border.all(color: AppColors.brand.withValues(alpha: 0.3)),
                ),
                child: Text(
                  '$unreadCount',
                  style: GoogleFonts.spaceMono(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    color: AppColors.brand,
                  ),
                ),
              ),
            ],
          ],
        ),
        actions: [
          if (unreadCount > 0)
            TextButton(
              onPressed: () => markAllNotificationsRead(ref),
              child: Text(
                l10n.markAllAsRead,
                style: GoogleFonts.inter(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppColors.brand,
                ),
              ),
            ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1.0),
          child: Container(color: AppColors.border, height: 1.0),
        ),
      ),
      body: notifsAsync.when(
        loading: () => _buildLoadingSkeleton(),
        error: (e, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: Text(
              'Could not load notifications.\n$e',
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(
                  fontSize: 13, color: AppColors.inkMuted),
            ),
          ),
        ),
        data: (notifications) {
          if (notifications.isEmpty) {
            return Center(
              child: EmptyState(
                icon: Icons.notifications_off_rounded,
                title: 'No Notifications Yet',
                description:
                    'We will notify you when job applications, wage payments, or status updates occur.',
                actionLabel: 'Back to Dashboard',
                onAction: () => context.pop(),
              ),
            );
          }

          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(notificationsProvider),
            backgroundColor: AppColors.surface,
            color: AppColors.brand,
            child: ListView.separated(
              padding: const EdgeInsets.all(AppSpacing.md),
              physics: const BouncingScrollPhysics(
                  parent: AlwaysScrollableScrollPhysics()),
              itemCount: notifications.length,
              separatorBuilder: (_, __) =>
                  const SizedBox(height: AppSpacing.sm),
              itemBuilder: (context, index) {
                final item = notifications[index];
                final typeColor = _getTypeColor(item.type);

                return Material(
                  color: item.isRead
                      ? AppColors.surface
                      : AppColors.surfaceRaised,
                  borderRadius: AppRadii.control,
                  child: InkWell(
                    onTap: item.isRead
                        ? null
                        : () => markNotificationRead(ref, item.id),
                    borderRadius: AppRadii.control,
                    child: Container(
                      padding: const EdgeInsets.all(AppSpacing.md),
                      decoration: BoxDecoration(
                        border: Border.all(
                          color: item.isRead
                              ? AppColors.border
                              : typeColor.withValues(alpha: 0.4),
                          width: item.isRead ? 1.0 : 1.5,
                        ),
                        borderRadius: AppRadii.control,
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Type icon
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: typeColor.withValues(alpha: 0.12),
                              shape: BoxShape.circle,
                            ),
                            child: Icon(
                              _getTypeIcon(item.type),
                              size: 20,
                              color: typeColor,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.md),

                          // Text info
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Expanded(
                                      child: Text(
                                        item.title,
                                        style: GoogleFonts.sora(
                                          fontSize: 13,
                                          fontWeight: item.isRead
                                              ? FontWeight.w600
                                              : FontWeight.bold,
                                          color: AppColors.inkPrimary,
                                        ),
                                      ),
                                    ),
                                    Text(
                                      item.timestamp,
                                      style: GoogleFonts.spaceMono(
                                        fontSize: 10,
                                        color: AppColors.inkMuted,
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  item.body,
                                  style: GoogleFonts.inter(
                                    fontSize: 12,
                                    color: AppColors.inkMuted,
                                    height: 1.35,
                                  ),
                                ),
                              ],
                            ),
                          ),

                          // Unread dot
                          if (!item.isRead) ...[
                            const SizedBox(width: AppSpacing.sm),
                            Container(
                              margin: const EdgeInsets.only(top: 4),
                              width: 8,
                              height: 8,
                              decoration: BoxDecoration(
                                color: typeColor,
                                shape: BoxShape.circle,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }

  Widget _buildLoadingSkeleton() {
    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.md),
      itemCount: 4,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (_, __) => Container(
        height: 80,
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: AppRadii.control,
        ),
        child: const _ShimmerBox(),
      ),
    );
  }
}

class _ShimmerBox extends StatefulWidget {
  const _ShimmerBox();

  @override
  State<_ShimmerBox> createState() => _ShimmerBoxState();
}

class _ShimmerBoxState extends State<_ShimmerBox>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
    _anim = CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _anim,
      builder: (_, __) => Container(
        decoration: BoxDecoration(
          borderRadius: AppRadii.control,
          color: Color.lerp(
            AppColors.surface,
            AppColors.border,
            _anim.value,
          ),
        ),
      ),
    );
  }
}
