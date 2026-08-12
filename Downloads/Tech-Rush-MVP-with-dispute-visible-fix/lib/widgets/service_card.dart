import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../core/utils/formatters.dart';
import '../l10n/app_localizations.dart';

class ServiceCard extends StatefulWidget {
  final String? image;
  final String title;
  final String category;
  final int? thumbsUpCount;
  final int? thumbsUpPercentage;
  final double price;
  final double? originalPrice;
  final bool verified;
  final VoidCallback? onSelect;
  final Color? accentColor;

  const ServiceCard({
    super.key,
    this.image,
    required this.title,
    required this.category,
    this.thumbsUpCount,
    this.thumbsUpPercentage,
    required this.price,
    this.originalPrice,
    this.verified = true,
    this.onSelect,
    this.accentColor,
  });

  @override
  State<ServiceCard> createState() => _ServiceCardState();
}

class _ServiceCardState extends State<ServiceCard> {
  bool _isPressed = false;
  bool _isSaved = false;

  void _handleTapDown(TapDownDetails details) {
    setState(() => _isPressed = true);
  }

  void _handleTapUp(TapUpDetails details) {
    setState(() => _isPressed = false);
  }

  void _handleTapCancel() {
    setState(() => _isPressed = false);
  }

  String _getCategoryName(BuildContext context, String cat) {
    final l10n = AppLocalizations.of(context);
    if (l10n == null) return cat;
    switch (cat.toLowerCase()) {
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
      case 'carpentry':
        return l10n.categoryCarpentry;
      case 'all':
        return l10n.categoryAll;
      default:
        return cat;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final categoryPrefix = widget.category.length >= 3
        ? widget.category.substring(0, 3).toUpperCase()
        : widget.category.toUpperCase();
    final localizedCategory = _getCategoryName(context, widget.category);

    return GestureDetector(
      onTapDown: _handleTapDown,
      onTapUp: _handleTapUp,
      onTapCancel: _handleTapCancel,
      onTap: widget.onSelect,
      child: AnimatedScale(
        scale: _isPressed ? 0.98 : 1.0,
        duration: const Duration(milliseconds: 100),
        curve: Curves.easeOut,
        child: Container(
          margin: const EdgeInsets.only(bottom: AppSpacing.md),
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: const BoxDecoration(
            color: AppColors.surface,
            borderRadius: AppRadii.card,
            boxShadow: AppShadows.card,
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Left Image Thumbnail & Verified Overlay
              Stack(
                children: [
                  Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      color: AppColors.surfaceRaised,
                      borderRadius: AppRadii.control,
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: widget.image != null && widget.image!.isNotEmpty
                        ? Image.network(
                            widget.image!,
                            fit: BoxFit.cover,
                            errorBuilder: (context, error, stackTrace) =>
                                _buildCategoryFallback(categoryPrefix),
                          )
                        : _buildCategoryFallback(categoryPrefix),
                  ),

                  // Overlay Verified Badge
                  if (widget.verified)
                    Positioned(
                      left: 4,
                      bottom: 4,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.surface.withValues(alpha: 0.95),
                          borderRadius: AppRadii.pill,
                          border: Border.all(
                            color: AppColors.border,
                            width: 1.0,
                          ),
                        ),
                        child: Text(
                          l10n?.badgeVerified ?? 'VERIFIED',
                          style: GoogleFonts.spaceMono(
                            fontSize: 9.0,
                            fontWeight: FontWeight.w600,
                            color: widget.accentColor ?? AppColors.brand,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(width: AppSpacing.md),

              // Right Details Column
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Category, Title, Rating Row
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          localizedCategory.toUpperCase(),
                          style: GoogleFonts.spaceMono(
                            fontSize: 10.0,
                            fontWeight: FontWeight.w500,
                            color: AppColors.inkMuted,
                            letterSpacing: 0.5,
                            height: 1.2,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          widget.title,
                          style: GoogleFonts.sora(
                            fontSize: 14.0,
                            fontWeight: FontWeight.w600,
                            color: AppColors.inkPrimary,
                            height: 1.2,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 3),
                        Row(
                          children: [
                            Text(
                              '👍',
                              style: const TextStyle(fontSize: 12.0, height: 1.0),
                            ),
                            const SizedBox(width: 3),
                            Text(
                              widget.thumbsUpPercentage != null
                                  ? '${widget.thumbsUpPercentage}%'
                                  : (widget.thumbsUpCount != null
                                      ? '${widget.thumbsUpCount}'
                                      : 'New'),
                              style: GoogleFonts.spaceMono(
                                fontSize: 11.0,
                                fontWeight: FontWeight.bold,
                                color: AppColors.success,
                                height: 1.2,
                              ),
                            ),
                            if (widget.thumbsUpPercentage != null) ...[
                              const SizedBox(width: 4),
                              Text(
                                'Recommended',
                                style: GoogleFonts.spaceMono(
                                  fontSize: 10.0,
                                  color: AppColors.inkMuted,
                                  height: 1.2,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),

                    // Price & Heart Save Toggle Row
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.baseline,
                          textBaseline: TextBaseline.alphabetic,
                          children: [
                            Text(
                              Formatters.currency(widget.price),
                              style: GoogleFonts.spaceMono(
                                fontSize: 15.0,
                                fontWeight: FontWeight.bold,
                                color: widget.accentColor ?? AppColors.brand,
                                height: 1.2,
                              ),
                            ),
                            if (widget.originalPrice != null) ...[
                              const SizedBox(width: AppSpacing.xs + 2),
                              Text(
                                Formatters.currency(widget.originalPrice!),
                                style: GoogleFonts.spaceMono(
                                  fontSize: 11.0,
                                  color: AppColors.inkCaption,
                                  decoration: TextDecoration.lineThrough,
                                  decorationColor: AppColors.inkCaption,
                                  height: 1.2,
                                ),
                              ),
                            ],
                          ],
                        ),

                        // Interactive Bookmark / Save Toggle Button
                        GestureDetector(
                          onTap: () {
                            setState(() => _isSaved = !_isSaved);
                          },
                          behavior: HitTestBehavior.opaque,
                          child: Padding(
                            padding: const EdgeInsets.all(4.0),
                            child: Icon(
                              _isSaved
                                  ? Icons.favorite_rounded
                                  : Icons.favorite_border_rounded,
                              size: 16.0,
                              color: _isSaved
                                  ? const Color(0xFFD66853)
                                  : AppColors.inkMuted,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCategoryFallback(String prefix) {
    return Container(
      color: AppColors.surfaceRaised,
      alignment: Alignment.center,
      child: Text(
        prefix,
        style: GoogleFonts.spaceMono(
          fontSize: 11.0,
          fontWeight: FontWeight.bold,
          color: AppColors.inkMuted,
        ),
      ),
    );
  }
}
