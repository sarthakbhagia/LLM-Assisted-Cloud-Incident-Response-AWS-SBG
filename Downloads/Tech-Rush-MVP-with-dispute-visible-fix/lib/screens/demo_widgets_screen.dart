import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../widgets/service_card.dart';
import '../widgets/skeleton_service_card.dart';
import '../widgets/status_chip.dart';
import '../widgets/trust_badge_row.dart';
import '../widgets/rating_breakdown.dart';
import '../widgets/provider_card.dart';
import '../widgets/sticky_bottom_bar.dart';
import '../widgets/app_bottom_sheet.dart';
import '../widgets/date_slot_picker.dart';

class DemoWidgetsScreen extends StatefulWidget {
  const DemoWidgetsScreen({super.key});

  @override
  State<DemoWidgetsScreen> createState() => _DemoWidgetsScreenState();
}

class _DemoWidgetsScreenState extends State<DemoWidgetsScreen> {
  String _selectedCategory = 'All';
  String _selectedSlotId = 'slot1';

  static const List<DateSlot> _sampleSlots = [
    DateSlot(id: 'slot1', label: 'Today 14:00', urgent: true),
    DateSlot(id: 'slot2', label: 'Tomorrow 09:00'),
    DateSlot(id: 'slot3', label: 'Tomorrow 15:00'),
    DateSlot(id: 'slot4', label: '05 Aug 09:00', disabled: true),
  ];

  void _openFilterBottomSheet() {
    final categories = [
      'All',
      'Cleaning',
      'Plumbing',
      'Painting',
      'Cooking',
      'Gardening',
      'Electrical'
    ];

    showAppBottomSheet(
      context: context,
      title: 'Filter Dispatches by Category',
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: categories.map((cat) {
          final isSelected = _selectedCategory == cat;
          return Container(
            margin: const EdgeInsets.only(bottom: AppSpacing.sm),
            decoration: BoxDecoration(
              color: isSelected ? AppColors.surfaceRaised : AppColors.surface,
              borderRadius: AppRadii.control,
              border: Border.all(
                color: isSelected ? AppColors.brand : AppColors.border,
              ),
            ),
            child: ListTile(
              title: Text(
                cat,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: isSelected ? AppColors.brand : AppColors.inkPrimary,
                      fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                      fontFamily: 'monospace',
                    ),
              ),
              trailing: isSelected
                  ? const Icon(Icons.check_rounded, color: AppColors.brand, size: 18)
                  : null,
              onTap: () {
                setState(() => _selectedCategory = cat);
                Navigator.of(context).pop();
              },
            ),
          );
        }).toList(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.canvas,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        title: Text(
          'KaamSetu Widget Gallery',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        elevation: 0,
        centerTitle: false,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1.0),
          child: Container(
            color: AppColors.border,
            height: 1.0,
          ),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Section 1: Date & Availability Slot Picker
            Text(
              '1. DATE & DISPATCH SLOT PICKER',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.inkMuted,
                    letterSpacing: 1.2,
                  ),
            ),
            const SizedBox(height: AppSpacing.sm),
            DateSlotPicker(
              slots: _sampleSlots,
              selectedId: _selectedSlotId,
              onSelect: (id) => setState(() => _selectedSlotId = id),
            ),
            const SizedBox(height: AppSpacing.xxl),

            // Section 2: ServiceCard & Press Scale Feedback
            Text(
              '2. SERVICE CARD WIDGETS (WITH TAP FEEDBACK)',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.inkMuted,
                    letterSpacing: 1.2,
                  ),
            ),
            const SizedBox(height: AppSpacing.sm),
            ServiceCard(
              title: 'Full House Painting (Interior Walls)',
              category: 'Painting',
              thumbsUpCount: 24,
              thumbsUpPercentage: 96,
              price: 1500,
              originalPrice: 1800,
              verified: true,
              onSelect: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Selected Job #8491 - House Painting')),
                );
              },
            ),
            ServiceCard(
              title: 'Deep Kitchen & Chimney Cleaning',
              category: 'Cleaning',
              thumbsUpCount: 42,
              thumbsUpPercentage: 98,
              price: 900,
              originalPrice: 1200,
              verified: true,
              onSelect: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Selected Job #8492 - Kitchen Cleaning')),
                );
              },
            ),
            const SizedBox(height: AppSpacing.xxl),

            // Section 3: Shimmer Skeleton Placeholder
            Text(
              '3. SKELETON SHIMMER LIST',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.inkMuted,
                    letterSpacing: 1.2,
                  ),
            ),
            const SizedBox(height: AppSpacing.sm),
            const SkeletonList(count: 2),
            const SizedBox(height: AppSpacing.xxl),

            // Section 4: Bottom Sheet Trigger Demo
            Text(
              '4. MODAL BOTTOM SHEET TRIGGER',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.inkMuted,
                    letterSpacing: 1.2,
                  ),
            ),
            const SizedBox(height: AppSpacing.sm),
            ElevatedButton.icon(
              onPressed: _openFilterBottomSheet,
              icon: const Icon(Icons.filter_list_rounded, size: 16),
              label: Text('Open Category Filter (Selected: $_selectedCategory)'),
            ),
            const SizedBox(height: AppSpacing.xxl),

            // Section 5: Live Status Chips
            Text(
              '5. STATUS CHIP (ENUM & PULSING DOT STATES)',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.inkMuted,
                    letterSpacing: 1.2,
                  ),
            ),
            const SizedBox(height: AppSpacing.sm),
            const Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                StatusChip(status: StatusChipType.open),
                StatusChip(status: StatusChipType.assigned),
                StatusChip(status: StatusChipType.interested),
                StatusChip(status: StatusChipType.completed),
                StatusChip(
                  status: StatusChipType.open,
                  labelOverride: 'STATUS: AVAILABLE',
                ),
                StatusChip(
                  status: StatusChipType.open,
                  labelOverride: '2 POSTINGS ACTIVE',
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xxl),

            // Section 6: Trust Badges
            Text(
              '6. TRUST BADGES ROW',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.inkMuted,
                    letterSpacing: 1.2,
                  ),
            ),
            const SizedBox(height: AppSpacing.sm),
            const TrustBadgeRow(),
            const SizedBox(height: AppSpacing.xxl),

            // Section 7: Provider Card (Unassigned Mode)
            Text(
              '7. WORKER PROVIDER CARD (UNASSIGNED)',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.inkMuted,
                    letterSpacing: 1.2,
                  ),
            ),
            const SizedBox(height: AppSpacing.sm),
            ProviderCard(
              name: 'Ramesh Kumar',
              primarySkill: 'House Painting & Tiling',
              skills: const ['Painting', 'Plumbing', 'Wall Tiling', 'Waterproofing'],
              wage: 650,
              rating: 4.8,
              reviewsCount: 24,
              jobsCompleted: 32,
              phone: '+91 98765 43210',
              isVerified: true,
              isAssigned: false,
              onHire: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Ramesh Kumar assigned to job dispatch!')),
                );
              },
            ),
            const SizedBox(height: AppSpacing.lg),

            // Section 8: Rating Breakdown
            Text(
              '8. RATING BREAKDOWN COMPONENT',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.inkMuted,
                    letterSpacing: 1.2,
                  ),
            ),
            const SizedBox(height: AppSpacing.sm),
            const RatingBreakdown(
              average: 4.8,
              total: 24,
            ),
            const SizedBox(height: AppSpacing.xxxl),
          ],
        ),
      ),
      bottomNavigationBar: StickyBottomBar(
        label: 'DAILY RATE',
        price: 1500,
        ctaLabel: 'Express Interest & Apply',
        icon: const Icon(Icons.work_outline_rounded, size: 16.0, color: Colors.white),
        onCta: () {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Application submitted to job dispatch ledger!')),
          );
        },
      ),
    );
  }
}
