import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../l10n/app_localizations.dart';

enum StatusChipType {
  open,
  assigned,
  interested,
  completed,
  closed,
}

class StatusChipStyle {
  final String label;
  final Color bg;
  final Color border;
  final Color text;
  final Color dotColor;
  final bool shouldPulse;

  const StatusChipStyle({
    required this.label,
    required this.bg,
    required this.border,
    required this.text,
    required this.dotColor,
    required this.shouldPulse,
  });
}

class StatusChip extends StatefulWidget {
  final StatusChipType status;
  final String? labelOverride;

  const StatusChip({
    super.key,
    required this.status,
    this.labelOverride,
  });

  @override
  State<StatusChip> createState() => _StatusChipState();
}

class _StatusChipState extends State<StatusChip>
    with TickerProviderStateMixin {
  AnimationController? _controller;
  Animation<double>? _pulseAnimation;

  static StatusChipStyle _getStyle(StatusChipType type) {
    switch (type) {
      case StatusChipType.open:
        return StatusChipStyle(
          label: 'OPEN',
          bg: AppColors.warningSubtle,
          border: AppColors.warning.withValues(alpha: 0.4),
          text: AppColors.warning,
          dotColor: AppColors.warning,
          shouldPulse: true,
        );
      case StatusChipType.assigned:
        return StatusChipStyle(
          label: 'ASSIGNED',
          bg: AppColors.brandSubtle,
          border: AppColors.brand.withValues(alpha: 0.4),
          text: AppColors.brand,
          dotColor: AppColors.brand,
          shouldPulse: true,
        );
      case StatusChipType.interested:
        return StatusChipStyle(
          label: 'INTERESTED',
          bg: AppColors.brandSubtle,
          border: AppColors.brand.withValues(alpha: 0.4),
          text: AppColors.brand,
          dotColor: AppColors.brand,
          shouldPulse: true,
        );
      case StatusChipType.completed:
        return StatusChipStyle(
          label: 'COMPLETED',
          bg: AppColors.successSubtle,
          border: AppColors.success.withValues(alpha: 0.4),
          text: AppColors.success,
          dotColor: AppColors.success,
          shouldPulse: false,
        );
      case StatusChipType.closed:
        return StatusChipStyle(
          label: 'CLOSED',
          bg: AppColors.dangerSubtle,
          border: AppColors.danger.withValues(alpha: 0.4),
          text: AppColors.danger,
          dotColor: AppColors.danger,
          shouldPulse: false,
        );
    }
  }

  @override
  void initState() {
    super.initState();
    _setupAnimationIfNeeded();
  }

  @override
  void didUpdateWidget(covariant StatusChip oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.status != widget.status) {
      _setupAnimationIfNeeded();
    }
  }

  void _setupAnimationIfNeeded() {
    final style = _getStyle(widget.status);
    if (style.shouldPulse) {
      _controller ??= AnimationController(
        vsync: this,
        duration: const Duration(milliseconds: 750),
      )..repeat(reverse: true);

      _pulseAnimation ??= Tween<double>(begin: 0.35, end: 1.0).animate(
        CurvedAnimation(parent: _controller!, curve: Curves.easeInOut),
      );
    } else {
      _controller?.stop();
      _controller?.dispose();
      _controller = null;
      _pulseAnimation = null;
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final style = _getStyle(widget.status);
    String defaultLabel = style.label;
    if (l10n != null) {
      switch (widget.status) {
        case StatusChipType.open:
          defaultLabel = l10n.statusOpen;
          break;
        case StatusChipType.assigned:
        case StatusChipType.interested:
          defaultLabel = l10n.statusAssigned;
          break;
        case StatusChipType.completed:
          defaultLabel = l10n.statusCompletedFull;
          break;
        case StatusChipType.closed:
          defaultLabel = 'CLOSED';
          break;
      }
    }
    final displayLabel = widget.labelOverride ?? defaultLabel;

    StatusChipStyle finalStyle = style;
    if (displayLabel.toUpperCase() == 'AVAILABLE' || (l10n != null && displayLabel == l10n.statusAvailable)) {
      finalStyle = StatusChipStyle(
        label: displayLabel,
        bg: AppColors.successSubtle,
        border: AppColors.success.withValues(alpha: 0.4),
        text: AppColors.success,
        dotColor: AppColors.success,
        shouldPulse: style.shouldPulse,
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm + 2,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: finalStyle.bg,
        borderRadius: AppRadii.pill,
        border: Border.all(
          color: finalStyle.border,
          width: 1.0,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Dot Indicator (Pulsing for active states, static for completed)
          if (finalStyle.shouldPulse && _pulseAnimation != null) ...[
            SizedBox(
              width: 8,
              height: 8,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  FadeTransition(
                    opacity: _pulseAnimation!,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: finalStyle.dotColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                  Container(
                    width: 5,
                    height: 5,
                    decoration: BoxDecoration(
                      color: finalStyle.dotColor,
                      shape: BoxShape.circle,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.xs + 2),
          ] else if (!finalStyle.shouldPulse) ...[
            Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(
                color: finalStyle.dotColor,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: AppSpacing.xs + 2),
          ],

          // Status Label
          Flexible(
            child: Text(
              displayLabel,
              style: GoogleFonts.spaceMono(
                fontSize: 10.0,
                fontWeight: FontWeight.bold,
                color: finalStyle.text,
                letterSpacing: 0.5,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
