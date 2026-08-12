import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Single source of truth for KaamSetu design system tokens.
/// Premium, consumer-grade Light Theme palette, typography, radii, and soft shadows.

abstract class AppColors {
  // Canvas & Background
  static const Color canvas = Color(0xFFFAF9F7);        // Soft warm off-white: #FAF9F7

  // Surface Tiers
  static const Color surface = Color(0xFFFFFFFF);       // Pure white card surface: #FFFFFF
  static const Color surfaceRaised = Color(0xFFF4F3F0); // Subtle warm tinted container fill
  static const Color surface2 = Color(0xFFF4F3F0);      // Alias for surface-2

  // Border & Hairline
  static const Color border = Color(0xFFE5E3DD);        // Hairline border: #E5E3DD

  // Ink / Text Tiers
  static const Color inkPrimary = Color(0xFF1A1A1A);    // Crisp near-black primary text: #1A1A1A
  static const Color inkMuted = Color(0xFF6B6B6B);      // Warm medium gray text: #6B6B6B
  static const Color inkCaption = Color(0xFF8E8D8A);    // De-emphasized caption text: #8E8D8A

  // Brand / Single-Purpose Accent (CTAs, Active states, Price, Ratings)
  static const Color brand = Color(0xFF943D39);         // Base maroon accent
  static const Color brandLight = Color(0xFFA64A45);    // Lighter / Active maroon
  static const Color brandSubtle = Color(0xFFF7EBEB);   // Soft warm maroon pastel fill

  // Status & Utility Colors
  static const Color success = Color(0xFF059669);       // Muted emerald green: #059669
  static const Color successSubtle = Color(0xFFECFDF5); // Soft green pastel fill

  static const Color warning = Color(0xFFD97706);       // Muted amber warning: #D97706
  static const Color warningSubtle = Color(0xFFFFFBEB); // Soft amber pastel fill

  static const Color danger = Color(0xFFDC2626);        // Warm red error: #DC2626
  static const Color dangerSubtle = Color(0xFFFEF2F2);  // Soft red pastel fill
}

abstract class AppRadii {
  static const double smValue = 8.0;
  static const double controlValue = 12.0;
  static const double cardValue = 16.0;
  static const double pillValue = 999.0;

  static const BorderRadius sm = BorderRadius.all(Radius.circular(smValue));
  static const BorderRadius control = BorderRadius.all(Radius.circular(controlValue));
  static const BorderRadius card = BorderRadius.all(Radius.circular(cardValue));
  static const BorderRadius pill = BorderRadius.all(Radius.circular(pillValue));
}

abstract class AppShadows {
  /// Soft warm elevation shadow for light cards
  static const List<BoxShadow> card = [
    BoxShadow(
      color: Color(0x0F000000),
      blurRadius: 10.0,
      offset: Offset(0, 2),
    ),
    BoxShadow(
      color: Color(0x08000000),
      blurRadius: 2.0,
      offset: Offset(0, 1),
    ),
  ];

  /// Floating shadow for bottom sheets and overlays
  static const List<BoxShadow> floating = [
    BoxShadow(
      color: Color(0x1F000000),
      blurRadius: 20.0,
      offset: Offset(0, 8),
    ),
  ];
}

abstract class AppTheme {
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: AppColors.canvas,
      canvasColor: AppColors.canvas,

      colorScheme: const ColorScheme.light(
        surface: AppColors.surface,
        surfaceContainerHighest: AppColors.surfaceRaised,
        onSurface: AppColors.inkPrimary,
        onSurfaceVariant: AppColors.inkMuted,
        primary: AppColors.brand,
        onPrimary: Colors.white,
        secondary: AppColors.brandLight,
        onSecondary: Colors.white,
        outline: AppColors.border,
        error: AppColors.danger,
        onError: Colors.white,
      ),

      textTheme: TextTheme(
        // Headline Tier (Sora)
        headlineLarge: GoogleFonts.sora(
          fontSize: 24.0,
          fontWeight: FontWeight.bold,
          color: AppColors.inkPrimary,
          letterSpacing: -0.5,
          height: 1.33,
        ),
        headlineMedium: GoogleFonts.sora(
          fontSize: 20.0,
          fontWeight: FontWeight.bold,
          color: AppColors.inkPrimary,
          letterSpacing: -0.3,
          height: 1.3,
        ),
        headlineSmall: GoogleFonts.sora(
          fontSize: 18.0,
          fontWeight: FontWeight.bold,
          color: AppColors.inkPrimary,
          letterSpacing: -0.2,
        ),

        // Title / Section Header Tier (Sora)
        titleLarge: GoogleFonts.sora(
          fontSize: 16.0,
          fontWeight: FontWeight.w600,
          color: AppColors.inkPrimary,
          letterSpacing: -0.1,
        ),
        titleMedium: GoogleFonts.sora(
          fontSize: 14.0,
          fontWeight: FontWeight.w600,
          color: AppColors.inkPrimary,
        ),
        titleSmall: GoogleFonts.sora(
          fontSize: 12.0,
          fontWeight: FontWeight.w600,
          color: AppColors.inkPrimary,
        ),

        // Body Text Tier (Inter)
        bodyLarge: GoogleFonts.inter(
          fontSize: 14.0,
          fontWeight: FontWeight.normal,
          color: AppColors.inkPrimary,
          height: 1.4,
        ),
        bodyMedium: GoogleFonts.inter(
          fontSize: 12.0,
          fontWeight: FontWeight.normal,
          color: AppColors.inkMuted,
          height: 1.4,
        ),
        bodySmall: GoogleFonts.inter(
          fontSize: 10.0,
          fontWeight: FontWeight.normal,
          color: AppColors.inkCaption,
          height: 1.3,
        ),

        // Overline & Mono Code Tier (Space Mono)
        labelLarge: GoogleFonts.spaceMono(
          fontSize: 12.0,
          fontWeight: FontWeight.bold,
          color: AppColors.brand,
        ),
        labelMedium: GoogleFonts.spaceMono(
          fontSize: 11.0,
          fontWeight: FontWeight.w500,
          color: AppColors.inkMuted,
        ),
        labelSmall: GoogleFonts.spaceMono(
          fontSize: 10.0,
          fontWeight: FontWeight.w500,
          color: AppColors.inkMuted,
          letterSpacing: 1.0,
        ),
      ),

      cardTheme: const CardThemeData(
        color: AppColors.surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadii.card,
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surface,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: const OutlineInputBorder(
          borderRadius: AppRadii.control,
          borderSide: BorderSide(color: AppColors.border),
        ),
        enabledBorder: const OutlineInputBorder(
          borderRadius: AppRadii.control,
          borderSide: BorderSide(color: AppColors.border),
        ),
        focusedBorder: const OutlineInputBorder(
          borderRadius: AppRadii.control,
          borderSide: BorderSide(color: AppColors.brand, width: 1.5),
        ),
        errorBorder: const OutlineInputBorder(
          borderRadius: AppRadii.control,
          borderSide: BorderSide(color: AppColors.danger),
        ),
        hintStyle: GoogleFonts.inter(
          fontSize: 12,
          color: AppColors.inkCaption,
        ),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.brand,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          shape: const RoundedRectangleBorder(borderRadius: AppRadii.control),
          textStyle: GoogleFonts.inter(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  // Alias for backward compatibility
  static ThemeData get darkTheme => lightTheme;
}
