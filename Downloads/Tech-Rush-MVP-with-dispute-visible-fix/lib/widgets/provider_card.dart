import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:url_launcher/url_launcher.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../providers/review_provider.dart';

class ProviderCard extends ConsumerWidget {
  final String name;
  final String primarySkill;
  final List<String> skills;
  final double? dailyRate;
  final double? wage;
  final double rating;
  final int jobsCompleted;
  final int reviewsCount;
  final String phone;
  final String? photoUrl;
  final bool isVerified;
  final bool isAssigned;
  final VoidCallback? onHire;
  final VoidCallback? onCall;
  final VoidCallback? onMessage;
  final String? rateeId;

  const ProviderCard({
    super.key,
    required this.name,
    this.primarySkill = 'Painting Pro',
    this.skills = const ['Painting', 'Plumbing'],
    this.dailyRate,
    this.wage,
    required this.rating,
    required this.jobsCompleted,
    this.reviewsCount = 24,
    this.phone = '+91 98765 43210',
    this.photoUrl,
    this.isVerified = true,
    this.isAssigned = false,
    this.onHire,
    this.onCall,
    this.onMessage,
    this.rateeId,
  });

  double get effectiveRate => dailyRate ?? wage ?? 650.0;

  String get initials {
    final parts = name.trim().split(' ');
    if (parts.isEmpty) return 'W';
    if (parts.length == 1) return parts[0][0].toUpperCase();
    return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
  }

  Future<void> _handleCall(BuildContext context) async {
    if (onCall != null) {
      onCall!();
      return;
    }
    final uri = Uri.parse('tel:${phone.replaceAll(RegExp(r'\s+'), '')}');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    } else {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Dialing $name ($phone)...')),
        );
      }
    }
  }

  Future<void> _handleMessage(BuildContext context) async {
    if (onMessage != null) {
      onMessage!();
      return;
    }
    final uri = Uri.parse('sms:${phone.replaceAll(RegExp(r'\s+'), '')}');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    } else {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Messaging $name ($phone)...')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      margin: const EdgeInsets.only(bottom: AppSpacing.md),
      padding: const EdgeInsets.all(AppSpacing.md + 2),
      decoration: BoxDecoration(
        color: isAssigned
            ? AppColors.successSubtle
            : AppColors.surface,
        borderRadius: AppRadii.card,
        border: Border.all(
          color: isAssigned ? AppColors.success : AppColors.border,
          width: 1.0,
        ),
        boxShadow: AppShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Row (Avatar, Details, Daily Rate Chip)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Avatar with photoUrl or Initials Fallback
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppColors.surfaceRaised,
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.border, width: 1.0),
                ),
                clipBehavior: Clip.antiAlias,
                alignment: Alignment.center,
                child: photoUrl != null && photoUrl!.trim().isNotEmpty
                    ? Image.network(
                        photoUrl!,
                        width: 44,
                        height: 44,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) => Text(
                          initials,
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AppColors.inkPrimary,
                              ),
                        ),
                      )
                    : Text(
                        initials,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: AppColors.inkPrimary,
                            ),
                      ),
              ),
              const SizedBox(width: AppSpacing.md),

              // Name, Badge & Details
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            name,
                            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: AppColors.inkPrimary,
                                ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (isVerified) ...[
                          const SizedBox(width: AppSpacing.xs),
                          const Icon(
                            Icons.verified_rounded,
                            size: 16.0,
                            color: AppColors.success,
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      primarySkill,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            fontSize: 11.0,
                            color: AppColors.inkMuted,
                          ),
                    ),
                    const SizedBox(height: 4),
                    rateeId != null
                        ? ref.watch(mutualRatingSummaryProvider(rateeId!)).when(
                            data: (summary) {
                              if (summary.totalRatings == 0) {
                                return Row(
                                  children: [
                                    Text(
                                      'New Worker',
                                      style: GoogleFonts.spaceMono(
                                        fontSize: 11.0,
                                        fontWeight: FontWeight.bold,
                                        color: AppColors.inkMuted,
                                      ),
                                    ),
                                    const SizedBox(width: 6),
                                    Text(
                                      '($jobsCompleted jobs completed)',
                                      style: GoogleFonts.inter(
                                        fontSize: 11.0,
                                        color: AppColors.inkMuted,
                                      ),
                                    ),
                                  ],
                                );
                              }
                              return Row(
                                children: [
                                  Text(
                                    '👍',
                                    style: const TextStyle(fontSize: 12.0),
                                  ),
                                  const SizedBox(width: 3),
                                  Text(
                                    '${summary.thumbsUpPercentage}% Recommended',
                                    style: GoogleFonts.spaceMono(
                                      fontSize: 11.0,
                                      fontWeight: FontWeight.bold,
                                      color: const Color(0xFF059669),
                                    ),
                                  ),
                                  const SizedBox(width: 6),
                                  Flexible(
                                    child: Text(
                                      '(${summary.totalRatings} rating${summary.totalRatings == 1 ? "" : "s"})',
                                      style: GoogleFonts.inter(
                                        fontSize: 11.0,
                                        color: AppColors.inkMuted,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              );
                            },
                            loading: () => Row(
                              children: [
                                const SizedBox(
                                  width: 12,
                                  height: 12,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  '($jobsCompleted jobs)',
                                  style: GoogleFonts.inter(
                                    fontSize: 11.0,
                                    color: AppColors.inkMuted,
                                  ),
                                ),
                              ],
                            ),
                            error: (_, __) => Row(
                              children: [
                                Text(
                                  'Rating unavailable',
                                  style: GoogleFonts.inter(
                                    fontSize: 11.0,
                                    color: AppColors.inkMuted,
                                  ),
                                ),
                              ],
                            ),
                          )
                        : Row(
                            children: [
                              Text(
                                '👍',
                                style: const TextStyle(fontSize: 12.0),
                              ),
                              const SizedBox(width: 3),
                              Text(
                                '${rating.toStringAsFixed(0)}%',
                                style: GoogleFonts.spaceMono(
                                  fontSize: 11.0,
                                  fontWeight: FontWeight.bold,
                                  color: const Color(0xFF059669),
                                ),
                              ),
                              const SizedBox(width: 4),
                              Flexible(
                                child: Text(
                                  '($jobsCompleted jobs completed)',
                                  style: GoogleFonts.inter(
                                    fontSize: 11.0,
                                    color: AppColors.inkMuted,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                  ],
                ),
              ),

              // Daily Rate Badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.surfaceRaised,
                  borderRadius: AppRadii.control,
                  border: Border.all(color: AppColors.border, width: 1.0),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      '₹${effectiveRate.toInt()}',
                      style: Theme.of(context).textTheme.labelLarge?.copyWith(
                            fontSize: 14.0,
                            fontWeight: FontWeight.bold,
                            color: AppColors.brand,
                          ),
                    ),
                    Text(
                      '/ DAY RATE',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            fontSize: 8.0,
                            color: AppColors.inkMuted,
                          ),
                    ),
                  ],
                ),
              ),
            ],
          ),

          // Skill Chips Row
          if (skills.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm + 2),
            Wrap(
              spacing: 6.0,
              runSpacing: 4.0,
              children: skills.map((skill) {
                return Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceRaised,
                    borderRadius: AppRadii.control,
                    border: Border.all(color: AppColors.border, width: 1.0),
                  ),
                  child: Text(
                    skill,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          fontSize: 10.0,
                          color: AppColors.inkMuted,
                        ),
                  ),
                );
              }).toList(),
            ),
          ],

          const SizedBox(height: AppSpacing.md),

          // Action Buttons
          if (isAssigned) ...[
            Container(
              padding: const EdgeInsets.all(AppSpacing.sm),
              decoration: BoxDecoration(
                color: AppColors.successSubtle,
                borderRadius: AppRadii.control,
                border: Border.all(
                  color: AppColors.success.withValues(alpha: 0.4),
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      const Icon(
                        Icons.check_circle_rounded,
                        size: 16.0,
                        color: AppColors.success,
                      ),
                      const SizedBox(width: AppSpacing.xs + 2),
                      Text(
                        'WORKER ASSIGNED',
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: AppColors.success,
                            ),
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      // Message Button
                      Material(
                        color: AppColors.surfaceRaised,
                        borderRadius: BorderRadius.circular(8),
                        child: InkWell(
                          onTap: () => _handleMessage(context),
                          borderRadius: BorderRadius.circular(8),
                          child: Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              border: Border.all(color: AppColors.border),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Icon(
                              Icons.chat_bubble_outline_rounded,
                              size: 14.0,
                              color: AppColors.inkPrimary,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.xs + 2),
                      // Call Button
                      ElevatedButton.icon(
                        onPressed: () => _handleCall(context),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.success,
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                        icon: const Icon(Icons.phone_rounded, size: 12.0),
                        label: Text(
                          phone,
                          style: GoogleFonts.spaceMono(
                            fontSize: 10.0,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ] else ...[
            Row(
              children: [
                // Circular Message Button (Neutral Surface)
                Material(
                  color: AppColors.surfaceRaised,
                  borderRadius: AppRadii.control,
                  child: InkWell(
                    onTap: () => _handleMessage(context),
                    borderRadius: AppRadii.control,
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        border: Border.all(color: AppColors.border),
                        borderRadius: AppRadii.control,
                      ),
                      child: const Icon(
                        Icons.chat_bubble_outline_rounded,
                        size: 16.0,
                        color: AppColors.inkMuted,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.xs + 2),

                // Circular Call Button (Neutral Surface)
                Material(
                  color: AppColors.surfaceRaised,
                  borderRadius: AppRadii.control,
                  child: InkWell(
                    onTap: () => _handleCall(context),
                    borderRadius: AppRadii.control,
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        border: Border.all(color: AppColors.border),
                        borderRadius: AppRadii.control,
                      ),
                      child: const Icon(
                        Icons.phone_outlined,
                        size: 16.0,
                        color: AppColors.inkMuted,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),

                // Main Action Button (Assign & Dispatch or Contact)
                Expanded(
                  child: ElevatedButton(
                    onPressed: onHire ?? () => _handleCall(context),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.brand,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: AppRadii.control,
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        if (onHire == null) ...[
                          const Icon(Icons.phone_rounded, size: 14.0, color: Colors.white),
                          const SizedBox(width: 6),
                        ],
                        Text(
                          onHire != null ? 'Assign & Dispatch Job' : 'Contact Worker',
                          style: GoogleFonts.spaceMono(
                            fontSize: 12.0,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
