import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../l10n/app_localizations.dart';

class AppBottomNavScaffold extends StatelessWidget {
  final Widget child;

  const AppBottomNavScaffold({
    super.key,
    required this.child,
  });

  int _calculateSelectedIndex(BuildContext context) {
    final String location = GoRouterState.of(context).uri.path;
    if (location.startsWith('/listings')) return 1;
    if (location.startsWith('/profile')) return 2;
    if (location.startsWith('/dashboard')) return 0;
    return 0;
  }

  void _onItemTapped(int index, BuildContext context) {
    switch (index) {
      case 0:
        context.go('/dashboard');
        break;
      case 1:
        context.go('/listings');
        break;
      case 2:
        context.go('/profile');
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final activeIndex = _calculateSelectedIndex(context);
    final bottomInset = MediaQuery.of(context).padding.bottom;
    final effectiveBottomPadding = math.max(bottomInset, 8.0);
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      body: child,
      bottomNavigationBar: Container(
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
          top: AppSpacing.xs + 2,
          bottom: effectiveBottomPadding,
          left: AppSpacing.md,
          right: AppSpacing.md,
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _NavBarItem(
              icon: Icons.space_dashboard_rounded,
              label: l10n?.navDashboard ?? 'Dashboard',
              isSelected: activeIndex == 0,
              onTap: () => _onItemTapped(0, context),
            ),
            _NavBarItem(
              icon: Icons.work_outline_rounded,
              label: l10n?.navJobPostings ?? 'Job Postings',
              isSelected: activeIndex == 1,
              badgeCount: 2, // Reusable notification badge overlay
              onTap: () => _onItemTapped(1, context),
            ),
            _NavBarItem(
              icon: Icons.person_outline_rounded,
              label: l10n?.navProfile ?? 'Profile',
              isSelected: activeIndex == 2,
              onTap: () => _onItemTapped(2, context),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavBarItem extends StatefulWidget {
  final IconData icon;
  final String label;
  final bool isSelected;
  final int? badgeCount;
  final VoidCallback onTap;

  const _NavBarItem({
    required this.icon,
    required this.label,
    required this.isSelected,
    this.badgeCount,
    required this.onTap,
  });

  @override
  State<_NavBarItem> createState() => _NavBarItemState();
}

class _NavBarItemState extends State<_NavBarItem> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    final activeColor = widget.isSelected ? AppColors.brand : AppColors.inkMuted;

    return GestureDetector(
      onTapDown: (_) => setState(() => _isPressed = true),
      onTapUp: (_) => setState(() => _isPressed = false),
      onTapCancel: () => setState(() => _isPressed = false),
      onTap: widget.onTap,
      behavior: HitTestBehavior.opaque,
      child: AnimatedScale(
        scale: _isPressed ? 0.94 : 1.0,
        duration: const Duration(milliseconds: 100),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.sm,
            vertical: 4.0,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Active Indicator Top Dot Pill
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: widget.isSelected ? 16.0 : 0.0,
                height: 3.0,
                margin: const EdgeInsets.only(bottom: 4.0),
                decoration: BoxDecoration(
                  color: AppColors.brand,
                  borderRadius: AppRadii.pill,
                ),
              ),

              // Icon with Badge Overlay
              Stack(
                clipBehavior: Clip.none,
                children: [
                  Icon(
                    widget.icon,
                    size: 20.0,
                    color: activeColor,
                  ),
                  if (widget.badgeCount != null && widget.badgeCount! > 0)
                    Positioned(
                      top: -3,
                      right: -5,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 4,
                          vertical: 1,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.brand,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: AppColors.surface,
                            width: 1.5,
                          ),
                        ),
                        constraints: const BoxConstraints(
                          minWidth: 14,
                          minHeight: 14,
                        ),
                        child: Text(
                          '${widget.badgeCount}',
                          textAlign: TextAlign.center,
                          style: GoogleFonts.spaceMono(
                            fontSize: 8,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 3.0),
              Text(
                widget.label,
                style: GoogleFonts.spaceMono(
                  fontSize: 10.0,
                  fontWeight: widget.isSelected
                      ? FontWeight.bold
                      : FontWeight.w500,
                  color: activeColor,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
