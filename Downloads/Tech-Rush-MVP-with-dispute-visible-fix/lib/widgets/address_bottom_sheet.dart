import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../providers/user_provider.dart';
import 'app_bottom_sheet.dart';
import 'sticky_bottom_bar.dart';
import '../l10n/app_localizations.dart';

void openAddressBottomSheet(BuildContext context, WidgetRef ref) {
  final l10n = AppLocalizations.of(context);
  showAppBottomSheet(
    context: context,
    title: l10n?.updateAddressSheetTitle ?? 'Update Primary Address',
    child: _AddressBottomSheetContent(ref: ref),
  );
}

class _AddressBottomSheetContent extends StatefulWidget {
  final WidgetRef ref;
  const _AddressBottomSheetContent({required this.ref});

  @override
  State<_AddressBottomSheetContent> createState() =>
      __AddressBottomSheetContentState();
}

class __AddressBottomSheetContentState
    extends State<_AddressBottomSheetContent> {
  late TextEditingController _streetController;
  late TextEditingController _localityController;
  late TextEditingController _cityController;

  // Removed hardcoded presets as per Option A

  @override
  void initState() {
    super.initState();
    final user = widget.ref.read(userProfileProvider);
    _streetController = TextEditingController(text: user.streetAddress);
    _localityController = TextEditingController(text: user.locality);
    _cityController = TextEditingController(text: user.city);
  }

  @override
  void dispose() {
    _streetController.dispose();
    _localityController.dispose();
    _cityController.dispose();
    super.dispose();
  }

  // Preset method removed

  void _saveAddress() {
    widget.ref.read(userProfileProvider.notifier).updateAddress(
          streetAddress: _streetController.text.trim(),
          locality: _localityController.text.trim(),
          city: _cityController.text.trim(),
        );
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        // Quick Location Presets removed as per Option A

        // Address Fields
        Text(
          l10n?.authStreetAddress ?? 'STREET ADDRESS',
          style: GoogleFonts.spaceMono(
            fontSize: 10,
            fontWeight: FontWeight.w500,
            color: AppColors.inkMuted,
          ),
        ),
        const SizedBox(height: 6),
        TextField(
          controller: _streetController,
          style: GoogleFonts.inter(fontSize: 13, color: AppColors.inkPrimary),
          decoration: const InputDecoration(
            hintText: 'e.g. Flat 302, Green Acres Apartments',
            prefixIcon: Icon(Icons.home_outlined, size: 18, color: AppColors.inkMuted),
          ),
        ),
        const SizedBox(height: AppSpacing.md),

        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l10n?.authLocality ?? 'LOCALITY / AREA *',
                    style: GoogleFonts.spaceMono(
                      fontSize: 10,
                      fontWeight: FontWeight.w500,
                      color: AppColors.inkMuted,
                    ),
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: _localityController,
                    style: GoogleFonts.inter(fontSize: 13, color: AppColors.inkPrimary),
                    decoration: const InputDecoration(
                      hintText: 'e.g. Indiranagar',
                      prefixIcon: Icon(Icons.map_outlined, size: 18, color: AppColors.inkMuted),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l10n?.authCity ?? 'CITY *',
                    style: GoogleFonts.spaceMono(
                      fontSize: 10,
                      fontWeight: FontWeight.w500,
                      color: AppColors.inkMuted,
                    ),
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: _cityController,
                    style: GoogleFonts.inter(fontSize: 13, color: AppColors.inkPrimary),
                    decoration: const InputDecoration(
                      hintText: 'e.g. Pune',
                      prefixIcon: Icon(Icons.location_city_rounded, size: 18, color: AppColors.inkMuted),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.xl),

        StickyBottomBar(
          label: 'LOCATION UPDATE',
          price: _localityController.text.isEmpty
              ? 'Set Address'
              : _cityController.text.isEmpty
                  ? _localityController.text
                  : '${_localityController.text}, ${_cityController.text}',
          ctaLabel: l10n?.saveAddressCta ?? 'SAVE ADDRESS',
          onCta: _saveAddress,
        ),
      ],
    );
  }
}
