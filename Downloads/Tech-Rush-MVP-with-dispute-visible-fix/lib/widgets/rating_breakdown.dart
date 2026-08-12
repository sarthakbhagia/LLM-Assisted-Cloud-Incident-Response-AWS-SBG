import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../l10n/app_localizations.dart';

class RatingRowData {
  final int stars;
  final int pct;

  const RatingRowData({
    required this.stars,
    required this.pct,
  });
}

class RatingBreakdown extends StatelessWidget {
  final double average;
  final int total;
  final List<RatingRowData>? rows;

  const RatingBreakdown({
    super.key,
    required this.average,
    required this.total,
    this.rows,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    if (total == 0) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpacing.lg),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: AppRadii.card,
          border: Border.all(color: AppColors.border, width: 1.0),
          boxShadow: AppShadows.card,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.star_outline_rounded,
                    size: 20, color: AppColors.inkMuted),
                const SizedBox(width: 8),
                Text(
                  l10n?.noReviewsYet ?? 'No reviews yet',
                  style: GoogleFonts.sora(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    color: AppColors.inkPrimary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              l10n?.noReviewsSubtext ?? 'Complete jobs to receive ratings and reviews from employers.',
              style: GoogleFonts.inter(
                fontSize: 12,
                color: AppColors.inkMuted,
              ),
            ),
          ],
        ),
      );
    }

    final activeRows = rows ??
        const [
          RatingRowData(stars: 5, pct: 100),
          RatingRowData(stars: 4, pct: 0),
          RatingRowData(stars: 3, pct: 0),
          RatingRowData(stars: 2, pct: 0),
          RatingRowData(stars: 1, pct: 0),
        ];

    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadii.card,
        border: Border.all(color: AppColors.border, width: 1.0),
        boxShadow: AppShadows.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                average.toStringAsFixed(1),
                style: GoogleFonts.spaceMono(
                  fontSize: 32.0,
                  fontWeight: FontWeight.bold,
                  color: AppColors.inkPrimary,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              const Icon(
                Icons.star_rounded,
                size: 16.0,
                color: AppColors.warning,
              ),
              const SizedBox(width: AppSpacing.xs),
              Flexible(
                child: Text(
                  '($total verified review${total > 1 ? "s" : ""})',
                  style: GoogleFonts.spaceMono(
                    fontSize: 11.0,
                    color: AppColors.inkMuted,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),

          Column(
            children: activeRows.map((r) {
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 3.0),
                child: Row(
                  children: [
                    SizedBox(
                      width: 24,
                      child: Text(
                        '${r.stars}★',
                        style: GoogleFonts.spaceMono(
                          fontSize: 11.0,
                          color: AppColors.inkMuted,
                        ),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Expanded(
                      child: Container(
                        height: 6.0,
                        decoration: BoxDecoration(
                          color: AppColors.surfaceRaised,
                          borderRadius: AppRadii.pill,
                          border: Border.all(
                            color: AppColors.border,
                            width: 1.0,
                          ),
                        ),
                        child: FractionallySizedBox(
                          alignment: Alignment.centerLeft,
                          widthFactor: (r.pct.clamp(0, 100)) / 100.0,
                          child: Container(
                            decoration: const BoxDecoration(
                              color: AppColors.brand,
                              borderRadius: AppRadii.pill,
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.xs + 2),
                    SizedBox(
                      width: 32,
                      child: Text(
                        '${r.pct}%',
                        textAlign: TextAlign.right,
                        style: GoogleFonts.spaceMono(
                          fontSize: 10.0,
                          color: AppColors.inkMuted,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}
