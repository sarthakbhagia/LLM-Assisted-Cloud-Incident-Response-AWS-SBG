import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';

enum LogoVariant { centered, header }

class Logo extends StatelessWidget {
  final double size;
  final bool showSubtitle;
  final LogoVariant variant;

  const Logo({
    super.key,
    this.size = 28.0,
    this.showSubtitle = true,
    this.variant = LogoVariant.centered,
  });

  @override
  Widget build(BuildContext context) {
    if (variant == LogoVariant.header) {
      return Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10.0),
          boxShadow: const [
            BoxShadow(
              color: Color(0x1A000000),
              blurRadius: 6,
              offset: Offset(0, 2),
            ),
          ],
        ),
        clipBehavior: Clip.antiAlias,
        child: Image.asset(
          'assets/images/logo-icon.png',
          fit: BoxFit.cover,
        ),
      );
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Brand Image Badge
        Container(
          width: 84,
          height: 84,
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: AppRadii.card,
            boxShadow: AppShadows.card,
          ),
          child: ClipRRect(
            borderRadius: AppRadii.control,
            child: Image.asset(
              'assets/images/logo.png',
              fit: BoxFit.contain,
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.md),

        // Brand Title
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Kaam',
              style: GoogleFonts.sora(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: AppColors.inkPrimary,
                letterSpacing: -0.5,
              ),
            ),
            Text(
              'Setu',
              style: GoogleFonts.sora(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: AppColors.brand,
                letterSpacing: -0.5,
              ),
            ),
          ],
        ),
      ],
    );
  }
}
