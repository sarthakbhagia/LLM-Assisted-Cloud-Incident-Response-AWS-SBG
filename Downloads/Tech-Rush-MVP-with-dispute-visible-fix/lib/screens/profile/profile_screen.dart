import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/theme.dart';
import '../../core/spacing.dart';
import '../../widgets/trust_badge_row.dart';
import '../../widgets/rating_breakdown.dart';
import '../../widgets/app_bottom_sheet.dart';
import '../../widgets/address_bottom_sheet.dart';
import 'package:image_picker/image_picker.dart';
import '../../providers/user_provider.dart';
import '../../providers/review_provider.dart';
import '../../services/storage_service.dart';
import '../../services/work_sample_service.dart';
import '../../services/seed_service.dart';
import '../../providers/job_provider.dart';
import '../../providers/notification_provider.dart';
import '../../providers/locale_provider.dart';
import '../../l10n/app_localizations.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  final ImagePicker _picker = ImagePicker();
  final StorageService _storageService = StorageService();
  final WorkSampleService _workSampleService = WorkSampleService();
  List<String> _workSamples = [];
  bool _isUploadingPhoto = false;

  @override
  void initState() {
    super.initState();
    _loadWorkSamples();
  }

  Future<void> _loadWorkSamples() async {
    final user = ref.read(userProfileProvider);
    final workerId = user.phone.isNotEmpty ? user.phone : 'worker_${user.name}';
    final samples = await _workSampleService.fetchWorkSamples(workerId);
    if (mounted) {
      setState(() => _workSamples = samples);
    }
  }

  Future<void> _handlePickProfilePhoto() async {
    final pickedFile = await _picker.pickImage(source: ImageSource.gallery, imageQuality: 85);
    if (pickedFile == null) return;

    setState(() => _isUploadingPhoto = true);
    final url = await _storageService.uploadProfilePhoto(pickedFile);
    if (mounted) {
      setState(() => _isUploadingPhoto = false);
      if (url != null) {
        ref.read(userProfileProvider.notifier).updateProfile(photoUrl: url);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.success,
            content: Text('Profile photo updated!', style: GoogleFonts.inter(fontSize: 13, color: Colors.white)),
          ),
        );
      }
    }
  }

  Future<void> _handlePickWorkSample() async {
    final pickedFile = await _picker.pickImage(source: ImageSource.gallery, imageQuality: 85);
    if (pickedFile == null) return;

    final user = ref.read(userProfileProvider);
    final workerId = user.phone.isNotEmpty ? user.phone : 'worker_${user.name}';
    final url = await _workSampleService.addWorkSample(workerId: workerId, imageFile: pickedFile);
    if (url != null && mounted) {
      setState(() {
        if (!_workSamples.contains(url)) {
          _workSamples.insert(0, url);
        }
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.success,
          content: Text('Work sample uploaded!', style: GoogleFonts.inter(fontSize: 13, color: Colors.white)),
        ),
      );
    }
  }

  final TextEditingController _skillInputController = TextEditingController();
  final TextEditingController _dailyRateController = TextEditingController();

  @override
  void dispose() {
    _skillInputController.dispose();
    _dailyRateController.dispose();
    super.dispose();
  }

  void _openEditSkillsSheet() {
    // Read current skills from provider — source of truth
    final currentSkills = List<String>.from(ref.read(userProfileProvider).skills);

    showAppBottomSheet(
      context: context,
      title: 'Edit Active Skill Certifications',
      child: StatefulBuilder(
        builder: (context, setSheetState) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'ADD NEW SKILL',
                style: GoogleFonts.spaceMono(
                  fontSize: 10,
                  fontWeight: FontWeight.w500,
                  color: AppColors.inkMuted,
                ),
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  Expanded(
                    child: SizedBox(
                      height: 44,
                      child: TextField(
                        controller: _skillInputController,
                        style: GoogleFonts.spaceMono(
                          fontSize: 13,
                          color: AppColors.inkPrimary,
                        ),
                        decoration: const InputDecoration(
                          hintText: 'e.g. Electrical Repair',
                          fillColor: AppColors.canvas,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  ElevatedButton(
                    onPressed: () {
                      final text = _skillInputController.text.trim();
                      if (text.isNotEmpty && !currentSkills.contains(text)) {
                        setSheetState(() => currentSkills.add(text));
                        _skillInputController.clear();
                      }
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.brand,
                      shape: RoundedRectangleBorder(
                        borderRadius: AppRadii.control,
                      ),
                    ),
                    child: Text(
                      'Add',
                      style: GoogleFonts.spaceMono(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(
                'CURRENT CERTIFIED SKILLS',
                style: GoogleFonts.spaceMono(
                  fontSize: 10,
                  fontWeight: FontWeight.w500,
                  color: AppColors.inkMuted,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Wrap(
                spacing: AppSpacing.xs + 2,
                runSpacing: AppSpacing.xs + 2,
                children: currentSkills.map((skill) {
                  return Chip(
                    backgroundColor: AppColors.surfaceRaised,
                    side: const BorderSide(color: AppColors.border),
                    label: Text(
                      skill,
                      style: GoogleFonts.spaceMono(
                        fontSize: 11,
                        color: AppColors.inkPrimary,
                      ),
                    ),
                    deleteIcon: const Icon(
                      Icons.close_rounded,
                      size: 14,
                      color: AppColors.danger,
                    ),
                    onDeleted: () {
                      setSheetState(() => currentSkills.remove(skill));
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: AppSpacing.lg),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () {
                    // Persist to provider → Supabase
                    ref.read(userProfileProvider.notifier).updateProfile(
                          skills: List.from(currentSkills),
                        );
                    Navigator.of(context).pop();
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        backgroundColor: AppColors.success,
                        content: Text('Skills saved!', style: GoogleFonts.inter(fontSize: 13, color: Colors.white)),
                      ),
                    );
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.brand,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: AppRadii.control),
                  ),
                  child: Text(
                    'Save Skills',
                    style: GoogleFonts.spaceMono(
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _openEditDailyRateDialog() async {
    final user = ref.read(userProfileProvider);
    _dailyRateController.text = user.dailyRate.toStringAsFixed(0);

    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(
          'Set Daily Rate',
          style: GoogleFonts.sora(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.inkPrimary),
        ),
        content: TextField(
          controller: _dailyRateController,
          keyboardType: const TextInputType.numberWithOptions(decimal: false),
          style: GoogleFonts.spaceMono(fontSize: 15, color: AppColors.inkPrimary),
          decoration: InputDecoration(
            prefixText: '₹ ',
            suffixText: '/ day',
            hintText: '650',
            border: OutlineInputBorder(borderRadius: AppRadii.control),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text('Cancel', style: GoogleFonts.inter(color: AppColors.inkMuted)),
          ),
          ElevatedButton(
            onPressed: () {
              final parsed = double.tryParse(_dailyRateController.text.trim());
              if (parsed != null && parsed > 0) {
                ref.read(userProfileProvider.notifier).updateProfile(dailyRate: parsed);
                Navigator.of(ctx).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    backgroundColor: AppColors.success,
                    content: Text('Daily rate updated to ₹${parsed.toStringAsFixed(0)}/day!',
                        style: GoogleFonts.inter(fontSize: 13, color: Colors.white)),
                  ),
                );
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.brand,
              shape: RoundedRectangleBorder(borderRadius: AppRadii.control),
            ),
            child: Text('Save', style: GoogleFonts.inter(fontWeight: FontWeight.bold, color: Colors.white)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final user = ref.watch(userProfileProvider);

    return Scaffold(
      backgroundColor: AppColors.canvas,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        automaticallyImplyLeading: false,
        title: Text(
          l10n.profileTitle,
          style: GoogleFonts.sora(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: AppColors.inkPrimary,
          ),
        ),
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
            // Section 1: User Profile Header Card
            Container(
              padding: const EdgeInsets.all(AppSpacing.lg),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: AppRadii.card,
                border: Border.all(color: AppColors.border),
                boxShadow: AppShadows.card,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      GestureDetector(
                        onTap: _isUploadingPhoto ? null : _handlePickProfilePhoto,
                        child: Stack(
                          children: [
                            Container(
                              width: 60,
                              height: 60,
                              decoration: BoxDecoration(
                                color: AppColors.surfaceRaised,
                                borderRadius: AppRadii.card,
                                border: Border.all(color: AppColors.border),
                              ),
                              clipBehavior: Clip.antiAlias,
                              alignment: Alignment.center,
                              child: _isUploadingPhoto
                                  ? const SizedBox(
                                      width: 20,
                                      height: 20,
                                      child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.brand),
                                    )
                                  : (user.photoUrl != null && user.photoUrl!.trim().isNotEmpty
                                      ? Image.network(
                                          user.photoUrl!,
                                          width: 60,
                                          height: 60,
                                          fit: BoxFit.cover,
                                          errorBuilder: (context, error, stackTrace) => Text(
                                            user.name.isNotEmpty ? user.name.substring(0, 1).toUpperCase() : 'U',
                                            style: GoogleFonts.sora(
                                              fontSize: 20,
                                              fontWeight: FontWeight.bold,
                                              color: AppColors.brand,
                                            ),
                                          ),
                                        )
                                      : Text(
                                          user.name.isNotEmpty ? user.name.substring(0, 1).toUpperCase() : 'U',
                                          style: GoogleFonts.sora(
                                            fontSize: 20,
                                            fontWeight: FontWeight.bold,
                                            color: AppColors.brand,
                                          ),
                                        )),
                            ),
                            Positioned(
                              bottom: 0,
                              right: 0,
                              child: Container(
                                padding: const EdgeInsets.all(4),
                                decoration: const BoxDecoration(
                                  color: AppColors.brand,
                                  shape: BoxShape.circle,
                                ),
                                child: const Icon(
                                  Icons.camera_alt_rounded,
                                  size: 11,
                                  color: Colors.white,
                                ),
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
                            Row(
                              children: [
                                Flexible(
                                  child: Text(
                                    user.name,
                                    style: GoogleFonts.sora(
                                      fontSize: 17,
                                      fontWeight: FontWeight.bold,
                                      color: AppColors.inkPrimary,
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                const SizedBox(width: 6),
                                const Icon(
                                  Icons.check_circle_rounded,
                                  size: 16,
                                  color: AppColors.success,
                                ),
                                if (user.role == 'worker') ...[
                                  const SizedBox(width: 6),
                                  ref.watch(mutualRatingSummaryProvider(user.id ?? '')).when(
                                    data: (summary) {
                                      if (summary.totalRatings == 0) {
                                        return Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                                          decoration: BoxDecoration(
                                            color: AppColors.surfaceRaised,
                                            borderRadius: BorderRadius.circular(4),
                                            border: Border.all(color: AppColors.border),
                                          ),
                                          child: Text(
                                            'New',
                                            style: GoogleFonts.spaceMono(
                                              fontSize: 9,
                                              fontWeight: FontWeight.bold,
                                              color: AppColors.inkMuted,
                                            ),
                                          ),
                                        );
                                      }
                                      return Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: const Color(0xFFECFDF5),
                                          borderRadius: BorderRadius.circular(4),
                                          border: Border.all(color: const Color(0xFFA7F3D0)),
                                        ),
                                        child: Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            Text(
                                              '👍',
                                              style: const TextStyle(fontSize: 9),
                                            ),
                                            const SizedBox(width: 2),
                                            Text(
                                              '${summary.thumbsUpPercentage}%',
                                              style: GoogleFonts.spaceMono(
                                                fontSize: 9,
                                                fontWeight: FontWeight.bold,
                                                color: const Color(0xFF059669),
                                              ),
                                            ),
                                          ],
                                        ),
                                      );
                                    },
                                    loading: () => const SizedBox.shrink(),
                                    error: (_, __) => const SizedBox.shrink(),
                                  ),
                                ],
                              ],
                            ),
                            Text(
                              user.role == 'worker'
                                  ? l10n.verifiedWorkerBadge
                                  : l10n.verifiedEmployerBadge,
                              style: GoogleFonts.inter(
                                fontSize: 12,
                                color: AppColors.inkMuted,
                              ),
                            ),
                            GestureDetector(
                              onTap: () => openAddressBottomSheet(context, ref),
                              child: Row(
                                children: [
                                  const Icon(
                                    Icons.location_on_outlined,
                                    size: 12,
                                    color: AppColors.brand,
                                  ),
                                  const SizedBox(width: 2),
                                  Flexible(
                                    child: Text(
                                      user.fullAddress,
                                      style: GoogleFonts.spaceMono(
                                        fontSize: 10,
                                        color: AppColors.brand,
                                        fontWeight: FontWeight.bold,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  const SizedBox(width: 2),
                                  const Icon(
                                    Icons.edit_outlined,
                                    size: 11,
                                    color: AppColors.brand,
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.lg),

                  // Trust Badges Row
                  const TrustBadgeRow(),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Section 2: Rating Score & Review Breakdown
            ref.watch(workerRatingSummaryProvider(user.phone.isNotEmpty ? user.phone : 'worker_${user.name}')).when(
                  data: (summary) {
                    List<RatingRowData>? rows;
                    if (summary.totalReviews > 0) {
                      rows = [5, 4, 3, 2, 1].map((star) {
                        int cnt = summary.starDistribution[star] ?? 0;
                        int pct = ((cnt / summary.totalReviews) * 100).round();
                        return RatingRowData(stars: star, pct: pct);
                      }).toList();
                    }
                    return RatingBreakdown(
                      average: summary.averageRating,
                      total: summary.totalReviews,
                      rows: rows,
                    );
                  },
                  loading: () => const RatingBreakdown(average: 0.0, total: 0),
                  error: (err, stack) => const RatingBreakdown(average: 0.0, total: 0),
                ),
            const SizedBox(height: AppSpacing.lg),

            ref.watch(mutualRatingSummaryProvider(user.id ?? '')).when(
                  data: (summary) {
                    final hasRatings = summary.totalRatings > 0;
                    final displayStr = hasRatings
                        ? '👍 ${summary.thumbsUpPercentage}% (${summary.totalRatings} job${summary.totalRatings == 1 ? "" : "s"})'
                        : 'No ratings yet';
                    return Container(
                      margin: const EdgeInsets.only(bottom: AppSpacing.lg),
                      padding: const EdgeInsets.all(AppSpacing.md),
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: AppRadii.card,
                        border: Border.all(color: AppColors.border),
                        boxShadow: AppShadows.card,
                      ),
                      child: Row(
                        children: [
                          Icon(
                            hasRatings ? Icons.thumb_up_rounded : Icons.thumb_up_outlined,
                            color: AppColors.brand,
                            size: 16,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Mutual Rating: ',
                            style: GoogleFonts.inter(
                              fontSize: 12,
                              color: AppColors.inkMuted,
                            ),
                          ),
                          Text(
                            displayStr,
                            style: GoogleFonts.spaceMono(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: AppColors.inkPrimary,
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                  loading: () => const SizedBox.shrink(),
                  error: (_, __) => const SizedBox.shrink(),
                ),

            // Section 3: Skills & Certifications Card
            Container(
              padding: const EdgeInsets.all(AppSpacing.lg),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: AppRadii.card,
                border: Border.all(color: AppColors.border),
                boxShadow: AppShadows.card,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          'ACTIVE SKILLS & CERTIFICATIONS',
                          style: GoogleFonts.spaceMono(
                            fontSize: 10,
                            fontWeight: FontWeight.w500,
                            color: AppColors.inkMuted,
                            letterSpacing: 1.0,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      GestureDetector(
                        onTap: _openEditSkillsSheet,
                        child: Text(
                          'Edit Skills ->',
                          style: GoogleFonts.spaceMono(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: AppColors.brand,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.md),
                  Wrap(
                    spacing: AppSpacing.xs + 2,
                    runSpacing: AppSpacing.xs + 2,
                    children: [
                      ...user.skills.map((skill) {
                        return Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 5,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.surfaceRaised,
                            borderRadius: AppRadii.control,
                            border: Border.all(color: AppColors.border),
                          ),
                          child: Text(
                            skill,
                            style: GoogleFonts.spaceMono(
                              fontSize: 11,
                              fontWeight: FontWeight.w500,
                              color: AppColors.inkPrimary,
                            ),
                          ),
                        );
                      }),
                      GestureDetector(
                        onTap: _openEditSkillsSheet,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 5,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.brandSubtle,
                            borderRadius: AppRadii.control,
                            border: Border.all(color: AppColors.brand),
                          ),
                          child: Text(
                            '+ Edit / Add',
                            style: GoogleFonts.spaceMono(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: AppColors.brand,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Section 4: Work Samples Gallery Card
            Container(
              padding: const EdgeInsets.all(AppSpacing.lg),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: AppRadii.card,
                border: Border.all(color: AppColors.border),
                boxShadow: AppShadows.card,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          'WORK SAMPLES & PORTFOLIO GALLERY',
                          style: GoogleFonts.spaceMono(
                            fontSize: 10,
                            fontWeight: FontWeight.w500,
                            color: AppColors.inkMuted,
                            letterSpacing: 1.0,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      GestureDetector(
                        onTap: _handlePickWorkSample,
                        child: Text(
                          '+ Add Sample',
                          style: GoogleFonts.spaceMono(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: AppColors.brand,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    'Upload photos of past completed work to build trust with households.',
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      color: AppColors.inkMuted,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  SizedBox(
                    height: 90,
                    child: SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          GestureDetector(
                            onTap: _handlePickWorkSample,
                            child: Container(
                              width: 90,
                              height: 90,
                              margin: const EdgeInsets.only(right: AppSpacing.sm),
                              decoration: BoxDecoration(
                                color: AppColors.surfaceRaised,
                                borderRadius: AppRadii.control,
                                border: Border.all(color: AppColors.brand, style: BorderStyle.solid),
                              ),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  const Icon(Icons.add_a_photo_rounded, size: 22, color: AppColors.brand),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Add Photo',
                                    style: GoogleFonts.spaceMono(
                                      fontSize: 9.5,
                                      fontWeight: FontWeight.bold,
                                      color: AppColors.brand,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          ..._workSamples.map((sampleUrl) {
                            return Container(
                              width: 90,
                              height: 90,
                              margin: const EdgeInsets.only(right: AppSpacing.sm),
                              decoration: BoxDecoration(
                                color: AppColors.surfaceRaised,
                                borderRadius: AppRadii.control,
                                border: Border.all(color: AppColors.border),
                              ),
                              clipBehavior: Clip.antiAlias,
                              child: Image.network(
                                sampleUrl,
                                fit: BoxFit.cover,
                                errorBuilder: (context, err, stack) => const Icon(
                                  Icons.image_not_supported_rounded,
                                  color: AppColors.inkMuted,
                                ),
                              ),
                            );
                          }),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Section 4: Workforce Dispatch Specs Card
            Container(
              padding: const EdgeInsets.all(AppSpacing.lg),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: AppRadii.card,
                border: Border.all(color: AppColors.border),
                boxShadow: AppShadows.card,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l10n.profileDispatchSpecs,
                    style: GoogleFonts.spaceMono(
                      fontSize: 10,
                      fontWeight: FontWeight.w500,
                      color: AppColors.inkMuted,
                      letterSpacing: 1.0,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  GestureDetector(
                    onTap: _openEditDailyRateDialog,
                    child: _buildSpecRow(
                      l10n.profileExpectedDailyRate,
                      '₹${user.dailyRate.toStringAsFixed(0)}/day',
                      valueColor: AppColors.brand,
                      trailing: const Icon(Icons.edit_outlined, size: 13, color: AppColors.brand),
                    ),
                  ),
                  _buildSpecRow(l10n.profileDispatchRadius, '${user.dispatchRadiusKm.toStringAsFixed(0)} km'),
                  _buildSpecRow(l10n.profilePreferredShift, 'Morning (08:00 - 16:00)'),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'AVAILABILITY',
                            style: GoogleFonts.spaceMono(fontSize: 10, fontWeight: FontWeight.w500, color: AppColors.inkMuted),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            user.availabilityStatus == 'available' ? 'Available for Work' : 'Busy / Unavailable',
                            style: GoogleFonts.sora(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: user.availabilityStatus == 'available' ? AppColors.success : AppColors.danger,
                            ),
                          ),
                        ],
                      ),
                      Switch.adaptive(
                        value: user.availabilityStatus == 'available',
                        activeColor: AppColors.success,
                        onChanged: (val) {
                          ref.read(userProfileProvider.notifier).updateProfile(
                                availabilityStatus: val ? 'available' : 'busy',
                              );
                        },
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  _buildSpecRow(l10n.profilePaymentMode, 'Instant UPI / Cash',
                      isLast: true),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Section 4.5: App Language Settings Card
            Container(
              padding: const EdgeInsets.all(AppSpacing.lg),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: AppRadii.card,
                border: Border.all(color: AppColors.border),
                boxShadow: AppShadows.card,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    (AppLocalizations.of(context)?.languageSettingTitle ?? 'APP LANGUAGE / भाषा').toUpperCase(),
                    style: GoogleFonts.spaceMono(
                      fontSize: 10,
                      fontWeight: FontWeight.w500,
                      color: AppColors.inkMuted,
                      letterSpacing: 1.0,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  Row(
                    children: [
                      Container(
                        width: 36,
                        height: 36,
                        decoration: const BoxDecoration(
                          color: AppColors.brandSubtle,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.language_rounded,
                          size: 20,
                          color: AppColors.brand,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              ref.watch(localeProvider).languageCode == 'hi' ? 'हिंदी (Hindi)' : 'English',
                              style: GoogleFonts.sora(
                                fontSize: 13,
                                fontWeight: FontWeight.bold,
                                color: AppColors.inkPrimary,
                              ),
                            ),
                            Text(
                              ref.watch(localeProvider).languageCode == 'hi'
                                  ? 'वर्तमान भाषा: हिंदी'
                                  : 'Active Language: English',
                              style: GoogleFonts.inter(
                                fontSize: 11,
                                color: AppColors.inkMuted,
                              ),
                            ),
                          ],
                        ),
                      ),
                      // Segmented Language Toggle Button
                      Container(
                        decoration: BoxDecoration(
                          color: AppColors.surfaceRaised,
                          borderRadius: AppRadii.pill,
                          border: Border.all(color: AppColors.border),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            GestureDetector(
                              onTap: () => ref.read(localeProvider.notifier).setLocale(const Locale('en')),
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                decoration: BoxDecoration(
                                  color: ref.watch(localeProvider).languageCode == 'en'
                                      ? AppColors.brand
                                      : Colors.transparent,
                                  borderRadius: AppRadii.pill,
                                ),
                                child: Text(
                                  'English',
                                  style: GoogleFonts.spaceMono(
                                    fontSize: 10.5,
                                    fontWeight: FontWeight.bold,
                                    color: ref.watch(localeProvider).languageCode == 'en'
                                        ? Colors.white
                                        : AppColors.inkMuted,
                                  ),
                                ),
                              ),
                            ),
                            GestureDetector(
                              onTap: () => ref.read(localeProvider.notifier).setLocale(const Locale('hi')),
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                decoration: BoxDecoration(
                                  color: ref.watch(localeProvider).languageCode == 'hi'
                                      ? AppColors.brand
                                      : Colors.transparent,
                                  borderRadius: AppRadii.pill,
                                ),
                                child: Text(
                                  'हिंदी',
                                  style: GoogleFonts.spaceMono(
                                    fontSize: 10.5,
                                    fontWeight: FontWeight.bold,
                                    color: ref.watch(localeProvider).languageCode == 'hi'
                                        ? Colors.white
                                        : AppColors.inkMuted,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Section 5: System Reconfiguration Card
            Container(
              padding: const EdgeInsets.all(AppSpacing.lg),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: AppRadii.card,
                border: Border.all(color: AppColors.border),
                boxShadow: AppShadows.card,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l10n.profileSystemReconfiguration,
                    style: GoogleFonts.spaceMono(
                      fontSize: 10,
                      fontWeight: FontWeight.w500,
                      color: AppColors.inkMuted,
                      letterSpacing: 1.0,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  _buildActionRow(
                    Icons.terminal_rounded,
                    l10n.profileViewSystemGallery,
                    onTap: () => context.push('/demo'),
                  ),
                  _buildActionRow(
                    Icons.palette_outlined,
                    l10n.profileTogglePalette,
                    onTap: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Warm dark mode tokens active.')),
                      );
                    },
                  ),
                  _buildActionRow(
                    Icons.dataset_linked_rounded,
                    'Reset & Seed Demo Data',
                    onTap: () async {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Seeding database with demo profiles & jobs...')),
                      );
                      final success = await SeedService().seedDemoData();
                      ref.invalidate(filteredJobsProvider);
                      ref.invalidate(notificationsProvider);
                      ref.invalidate(dashboardStatsProvider);
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            backgroundColor: success ? AppColors.success : AppColors.brand,
                            content: Text(
                              success
                                  ? '✅ Database seeded successfully! Pull to refresh.'
                                  : '⚠️ Seed data queued. Verify Supabase connection.',
                            ),
                          ),
                        );
                      }
                    },
                  ),
                  _buildActionRow(
                    Icons.cleaning_services_rounded,
                    l10n.profileClearCache,
                    isLast: true,
                    onTap: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Cache purged cleanly.')),
                      );
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Section 6: Account & Compliance Card
            Container(
              padding: const EdgeInsets.all(AppSpacing.lg),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: AppRadii.card,
                border: Border.all(color: AppColors.border),
                boxShadow: AppShadows.card,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l10n.profileAccountCompliance,
                    style: GoogleFonts.spaceMono(
                      fontSize: 10,
                      fontWeight: FontWeight.w500,
                      color: AppColors.inkMuted,
                      letterSpacing: 1.0,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  _buildActionRow(
                    Icons.badge_outlined,
                    l10n.profileAadhaarDoc,
                    trailingIcon: Icons.check_circle_rounded,
                    trailingColor: AppColors.success,
                  ),
                  _buildActionRow(
                    Icons.account_balance_outlined,
                    l10n.profileBankAccount,
                  ),
                  _buildActionRow(
                    Icons.logout_rounded,
                    l10n.profileSignOut,
                    textColor: AppColors.danger,
                    iconColor: AppColors.danger,
                    isLast: true,
                    onTap: () async {
                      await ref.read(userProfileProvider.notifier).signOut();
                      if (context.mounted) {
                        context.go('/auth/sign-in');
                      }
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.xxxl),
          ],
        ),
      ),
    );
  }

  Widget _buildSpecRow(String label, String value,
      {Color? valueColor, bool isLast = false, Widget? trailing}) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        border: isLast
            ? null
            : const Border(
                bottom: BorderSide(
                  color: AppColors.border,
                  width: 1.0,
                ),
              ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Text(
              label,
              style: GoogleFonts.inter(
                fontSize: 12,
                color: AppColors.inkMuted,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Flexible(
            child: Text(
              value,
              style: GoogleFonts.spaceMono(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: valueColor ?? AppColors.inkPrimary,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: 4),
            trailing,
          ],
        ],
      ),
    );
  }

  Widget _buildActionRow(
    IconData icon,
    String label, {
    Color? textColor,
    Color? iconColor,
    IconData trailingIcon = Icons.chevron_right_rounded,
    Color? trailingColor,
    bool isLast = false,
    VoidCallback? onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          border: isLast
              ? null
              : const Border(
                  bottom: BorderSide(
                    color: AppColors.border,
                    width: 1.0,
                  ),
                ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Expanded(
              child: Row(
                children: [
                  Icon(
                    icon,
                    size: 16,
                    color: iconColor ?? AppColors.inkMuted,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      label,
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                        color: textColor ?? AppColors.inkPrimary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Icon(
              trailingIcon,
              size: 16,
              color: trailingColor ?? AppColors.inkMuted,
            ),
          ],
        ),
      ),
    );
  }
}
