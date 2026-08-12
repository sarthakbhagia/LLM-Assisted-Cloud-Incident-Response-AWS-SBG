import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../core/utils/formatters.dart';

class StickyBottomBar extends StatelessWidget {
  final String? label;
  final dynamic price;
  final String ctaLabel;
  final VoidCallback onCta;
  final bool disabled;
  final bool isLoading;
  final Widget? icon;

  const StickyBottomBar({
    super.key,
    this.label = 'DAILY WAGE RATE',
    this.price,
    required this.ctaLabel,
    required this.onCta,
    this.disabled = false,
    this.isLoading = false,
    this.icon,
  });

  String? get formattedPrice {
    if (price == null) return null;
    if (price is num) {
      return Formatters.currency(price as num);
    }
    return price.toString();
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).padding.bottom;
    final effectiveBottomPadding = math.max(bottomInset, 12.0);

    final isButtonDisabled = disabled || isLoading;

    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(
          top: BorderSide(
            color: AppColors.border,
            width: 1.0,
          ),
        ),
        boxShadow: AppShadows.floating,
      ),
      padding: EdgeInsets.only(
        left: AppSpacing.lg,
        right: AppSpacing.lg,
        top: AppSpacing.md,
        bottom: effectiveBottomPadding,
      ),
      child: Row(
        children: [
          // Optional Left Price & Label Column
          if (price != null) ...[
            Flexible(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (label != null && label!.isNotEmpty)
                    Text(
                      label!.toUpperCase(),
                      style: GoogleFonts.spaceMono(
                        fontSize: 10.0,
                        fontWeight: FontWeight.w500,
                        color: AppColors.inkMuted,
                        letterSpacing: 0.5,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  const SizedBox(height: 2),
                  Text(
                    formattedPrice!,
                    style: GoogleFonts.spaceMono(
                      fontSize: 20.0,
                      fontWeight: FontWeight.bold,
                      color: AppColors.brand,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.md),
          ],

          // Right Primary CTA Button
          Expanded(
            child: SizedBox(
              height: 48.0,
              child: ElevatedButton(
                onPressed: isButtonDisabled ? null : onCta,
                style: ElevatedButton.styleFrom(
                  backgroundColor: isButtonDisabled
                      ? AppColors.brand.withValues(alpha: 0.5)
                      : AppColors.brand,
                  disabledBackgroundColor: AppColors.brand.withValues(alpha: 0.5),
                  foregroundColor: Colors.white,
                  disabledForegroundColor: Colors.white70,
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: AppRadii.control,
                    side: BorderSide(
                      color: isButtonDisabled
                          ? Colors.transparent
                          : AppColors.brand,
                    ),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (isLoading) ...[
                      const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.0,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                    ] else if (icon != null) ...[
                      icon!,
                      const SizedBox(width: AppSpacing.sm),
                    ],
                    Flexible(
                      child: Text(
                        ctaLabel,
                        style: GoogleFonts.inter(
                          fontSize: 14.0,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
