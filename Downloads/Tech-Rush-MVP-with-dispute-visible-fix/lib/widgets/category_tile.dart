import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';

class CategoryTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? badgeText;
  final Color? badgeColor;
  final Color? badgeBg;
  final VoidCallback onTap;
  final Color? iconColor;

  const CategoryTile({
    super.key,
    required this.icon,
    required this.label,
    this.badgeText,
    this.badgeColor,
    this.badgeBg,
    required this.onTap,
    this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          // 1. Base Card Container (Uniform size and reserved inner padding for all tiles)
          Container(
            width: double.infinity,
            height: double.infinity,
            padding: const EdgeInsets.only(top: 12, bottom: 8, left: 4, right: 4),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: AppRadii.card,
              boxShadow: AppShadows.card,
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: const BoxDecoration(
                    color: AppColors.surfaceRaised,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: Icon(
                    icon,
                    size: 20,
                    color: iconColor ?? AppColors.brand,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  label,
                  style: GoogleFonts.sora(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w600,
                    color: AppColors.inkPrimary,
                    height: 1.1,
                  ),
                  textAlign: TextAlign.center,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),

          // 2. Uniform Badge Positioning (Anchored Top-Center with fixed negative offset for all cards with badges)
          if (badgeText != null)
            Positioned(
              top: -9,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 7,
                    vertical: 2.5,
                  ),
                  decoration: BoxDecoration(
                    color: badgeBg ?? AppColors.brandSubtle,
                    borderRadius: AppRadii.pill,
                    border: Border.all(
                      color: badgeColor ?? AppColors.brand,
                      width: 1.0,
                    ),
                  ),
                  child: Text(
                    badgeText!,
                    style: GoogleFonts.spaceMono(
                      fontSize: 7.5,
                      fontWeight: FontWeight.bold,
                      color: badgeColor ?? AppColors.brand,
                      height: 1.0,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
