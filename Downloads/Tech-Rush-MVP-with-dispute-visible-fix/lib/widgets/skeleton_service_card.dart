import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../core/spacing.dart';

/// Animated skeleton loading placeholder widget matching the ServiceCard layout.
/// Uses a custom [AnimationController] with a 650ms easeInOut pulse (opacity 0.35 -> 0.9 -> 0.35)
/// to match the React Native opacity pulse behavior without third-party dependencies.
class SkeletonServiceCard extends StatefulWidget {
  const SkeletonServiceCard({super.key});

  @override
  State<SkeletonServiceCard> createState() => _SkeletonServiceCardState();
}

class _SkeletonServiceCardState extends State<SkeletonServiceCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _opacityAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 650),
    )..repeat(reverse: true);

    _opacityAnimation = Tween<double>(
      begin: 0.35,
      end: 0.9,
    ).animate(
      CurvedAnimation(
        parent: _controller,
        curve: Curves.easeInOut,
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: AppSpacing.md),
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadii.card,
        border: Border.all(color: AppColors.border, width: 1.0),
        boxShadow: AppShadows.card,
      ),
      child: FadeTransition(
        opacity: _opacityAnimation,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Left Thumbnail Block
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: AppColors.surfaceRaised,
                borderRadius: AppRadii.control,
                border: Border.all(color: AppColors.border, width: 1.0),
              ),
            ),
            const SizedBox(width: AppSpacing.md),

            // Right Text Lines Column
            Expanded(
              child: SizedBox(
                height: 80,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Title line (75% width)
                        FractionallySizedBox(
                          widthFactor: 0.75,
                          child: Container(
                            height: 14,
                            decoration: BoxDecoration(
                              color: AppColors.surfaceRaised,
                              borderRadius: BorderRadius.circular(4),
                            ),
                          ),
                        ),
                        const SizedBox(height: AppSpacing.xs + 2),
                        // Subtitle line (50% width)
                        FractionallySizedBox(
                          widthFactor: 0.50,
                          child: Container(
                            height: 12,
                            decoration: BoxDecoration(
                              color: AppColors.surfaceRaised,
                              borderRadius: BorderRadius.circular(4),
                            ),
                          ),
                        ),
                      ],
                    ),
                    // Price line (25% width)
                    FractionallySizedBox(
                      widthFactor: 0.25,
                      child: Container(
                        height: 12,
                        decoration: BoxDecoration(
                          color: AppColors.surfaceRaised,
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Renders a column of [SkeletonServiceCard] items for loading lists.
class SkeletonList extends StatelessWidget {
  final int count;

  const SkeletonList({
    super.key,
    this.count = 4,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(
        count,
        (_) => const SkeletonServiceCard(),
      ),
    );
  }
}
