import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../l10n/app_localizations.dart';

class TrustBadgeItem {
  final IconData icon;
  final String label;

  const TrustBadgeItem({
    required this.icon,
    required this.label,
  });
}

class TrustBadgeRow extends StatelessWidget {
  final List<TrustBadgeItem>? badgesOverride;

  const TrustBadgeRow({
    super.key,
    this.badgesOverride,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final defaultBadges = [
      TrustBadgeItem(
        icon: Icons.fingerprint_rounded,
        label: l10n?.trustAadhaar ?? 'Aadhaar Verified',
      ),
      TrustBadgeItem(
        icon: Icons.verified_user_rounded,
        label: l10n?.trustBackground ?? 'Background Checked',
      ),
      TrustBadgeItem(
        icon: Icons.workspace_premium_rounded,
        label: l10n?.trustSkill ?? 'Skill Certified',
      ),
    ];

    final badges = badgesOverride ?? defaultBadges;

    return Wrap(
      spacing: AppSpacing.xs + 2,
      runSpacing: AppSpacing.xs + 2,
      children: badges.map((badge) {
        return Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.sm + 2,
            vertical: AppSpacing.xs,
          ),
          decoration: BoxDecoration(
            color: AppColors.successSubtle,
            borderRadius: AppRadii.pill,
            border: Border.all(
              color: AppColors.success.withValues(alpha: 0.3),
              width: 1.0,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                badge.icon,
                size: 12.0,
                color: AppColors.success,
              ),
              const SizedBox(width: AppSpacing.xs + 2),
              Text(
                badge.label,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      fontSize: 10.0,
                      fontWeight: FontWeight.w500,
                      color: AppColors.success,
                      letterSpacing: 0.2,
                    ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }
}
