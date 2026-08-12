import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';

class JobCategory {
  final String id;
  final IconData icon;
  final String? badgeTextKey;
  final Color? badgeColor;
  final Color? badgeBg;

  const JobCategory({
    required this.id,
    required this.icon,
    this.badgeTextKey,
    this.badgeColor,
    this.badgeBg,
  });

  String getLocalizedName(AppLocalizations l10n) {
    switch (id.toLowerCase()) {
      case 'painting':
        return l10n.categoryPainting;
      case 'cleaning':
        return l10n.categoryCleaning;
      case 'plumbing':
        return l10n.categoryPlumbing;
      case 'cooking':
        return l10n.categoryCooking;
      case 'gardening':
        return l10n.categoryGardening;
      case 'electrical':
        return l10n.categoryElectrical;
      default:
        return id;
    }
  }

  String? getLocalizedBadge(AppLocalizations l10n) {
    if (badgeTextKey == null) return null;
    switch (badgeTextKey) {
      case 'HIGH DEMAND':
        return l10n.badgeHighDemand;
      case 'POPULAR':
        return l10n.badgePopular;
      case 'URGENT':
        return l10n.badgeUrgent;
      default:
        return badgeTextKey;
    }
  }
}

abstract class AppCategories {
  /// The SINGLE, canonical list of daily work categories used across the app.
  static const List<JobCategory> all = [
    JobCategory(
      id: 'Painting',
      icon: Icons.format_paint_rounded,
      badgeTextKey: 'HIGH DEMAND',
      badgeColor: Color(0xFF943D39),
      badgeBg: Color(0xFFF7EBEB),
    ),
    JobCategory(
      id: 'Cleaning',
      icon: Icons.cleaning_services_rounded,
      badgeTextKey: 'POPULAR',
      badgeColor: Color(0xFF2563EB),
      badgeBg: Color(0xFFEFF6FF),
    ),
    JobCategory(
      id: 'Plumbing',
      icon: Icons.plumbing_rounded,
      badgeTextKey: 'URGENT',
      badgeColor: Color(0xFFDC2626),
      badgeBg: Color(0xFFFEF2F2),
    ),
    JobCategory(
      id: 'Cooking',
      icon: Icons.soup_kitchen_rounded,
    ),
    JobCategory(
      id: 'Gardening',
      icon: Icons.grass_rounded,
    ),
    JobCategory(
      id: 'Electrical',
      icon: Icons.electric_bolt_rounded,
    ),
  ];

  /// List of category IDs (e.g. ['Painting', 'Cleaning', ...])
  static List<String> get categoryIds => all.map((c) => c.id).toList();

  /// List of category IDs including 'All' for filters/tabs
  static List<String> get categoryIdsWithAll => ['All', ...categoryIds];

  /// Finds a JobCategory by string ID (case-insensitive)
  static JobCategory? findById(String id) {
    try {
      return all.firstWhere((c) => c.id.toLowerCase() == id.toLowerCase());
    } catch (_) {
      return null;
    }
  }

  /// Returns localized category name for a given raw category string ID
  static String getLocalizedName(BuildContext context, String rawCategory) {
    final l10n = AppLocalizations.of(context);
    if (l10n == null) return rawCategory;
    if (rawCategory.toLowerCase() == 'all') {
      return l10n.categoryAll;
    }
    final found = findById(rawCategory);
    if (found != null) {
      return found.getLocalizedName(l10n);
    }
    return rawCategory;
  }
}
