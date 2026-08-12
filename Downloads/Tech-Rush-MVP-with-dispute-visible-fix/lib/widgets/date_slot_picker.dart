import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';

class DateSlot {
  final String id;
  final String label;
  final bool disabled;
  final bool urgent;
  final bool scarce;

  const DateSlot({
    required this.id,
    required this.label,
    this.disabled = false,
    this.urgent = false,
    this.scarce = false,
  });
}

class DateSlotPicker extends StatelessWidget {
  final List<DateSlot> slots;
  final String? selectedId;
  final ValueChanged<String> onSelect;

  const DateSlotPicker({
    super.key,
    required this.slots,
    this.selectedId,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.sm + 2,
      children: slots.map((slot) {
        final isSelected = slot.id == selectedId;
        final isUrgent = (slot.urgent || slot.scarce) && !slot.disabled;

        return _DateSlotTile(
          slot: slot,
          isSelected: isSelected,
          isUrgent: isUrgent,
          onTap: () => onSelect(slot.id),
        );
      }).toList(),
    );
  }
}

class _DateSlotTile extends StatefulWidget {
  final DateSlot slot;
  final bool isSelected;
  final bool isUrgent;
  final VoidCallback onTap;

  const _DateSlotTile({
    required this.slot,
    required this.isSelected,
    required this.isUrgent,
    required this.onTap,
  });

  @override
  State<_DateSlotTile> createState() => _DateSlotTileState();
}

class _DateSlotTileState extends State<_DateSlotTile> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    final isDisabled = widget.slot.disabled;

    Color bg;
    Color border;
    Color textColor;

    if (isDisabled) {
      bg = AppColors.canvas;
      border = AppColors.border.withValues(alpha: 0.5);
      textColor = AppColors.inkCaption;
    } else if (widget.isSelected) {
      bg = AppColors.brandSubtle;
      border = AppColors.brand;
      textColor = AppColors.brand;
    } else {
      bg = AppColors.surface;
      border = AppColors.border;
      textColor = AppColors.inkPrimary;
    }

    return GestureDetector(
      onTapDown: isDisabled ? null : (_) => setState(() => _isPressed = true),
      onTapUp: isDisabled ? null : (_) => setState(() => _isPressed = false),
      onTapCancel: isDisabled ? null : () => setState(() => _isPressed = false),
      onTap: isDisabled ? null : widget.onTap,
      child: AnimatedScale(
        scale: _isPressed ? 0.96 : 1.0,
        duration: const Duration(milliseconds: 100),
        curve: Curves.easeOut,
        child: Opacity(
          opacity: isDisabled ? 0.4 : 1.0,
          child: Stack(
            clipBehavior: Clip.none,
            children: [
              // Main Slot Box
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.sm + 2,
                ),
                constraints: const BoxConstraints(minWidth: 100),
                decoration: BoxDecoration(
                  color: bg,
                  borderRadius: AppRadii.control,
                  border: Border.all(
                    color: border,
                    width: widget.isSelected ? 1.5 : 1.0,
                  ),
                ),
                alignment: Alignment.center,
                child: Text(
                  widget.slot.label,
                  style: GoogleFonts.spaceMono(
                    fontSize: 12.0,
                    fontWeight:
                        widget.isSelected ? FontWeight.bold : FontWeight.w500,
                    color: textColor,
                  ),
                ),
              ),

              // Urgent / Same-day Dispatch Pill Badge
              if (widget.isUrgent)
                Positioned(
                  top: -6.0,
                  right: -6.0,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 5,
                      vertical: 1.5,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.warning,
                      borderRadius: AppRadii.pill,
                      border: Border.all(
                        color: AppColors.border,
                        width: 1.0,
                      ),
                    ),
                    child: Text(
                      'URGENT',
                      style: GoogleFonts.spaceMono(
                        fontSize: 8.0,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
