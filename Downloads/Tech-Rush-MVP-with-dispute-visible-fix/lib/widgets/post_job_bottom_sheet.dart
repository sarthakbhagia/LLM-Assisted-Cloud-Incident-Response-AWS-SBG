import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../core/utils/formatters.dart';
import 'package:image_picker/image_picker.dart';
import '../models/job.dart';
import '../providers/job_provider.dart';
import '../providers/user_provider.dart';
import '../services/storage_service.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:go_router/go_router.dart';
import 'app_bottom_sheet.dart';
import '../l10n/app_localizations.dart';
import '../models/job_category.dart';

void openPostJobBottomSheet(BuildContext context, WidgetRef ref, {String? initialCategory}) {
  final userId = activeUserId;
  if (userId.isEmpty) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: AppColors.danger,
        content: Text(
          'Please sign in to post a job.',
          style: GoogleFonts.inter(color: Colors.white),
        ),
      ),
    );
    context.go('/auth/sign-in');
    return;
  }

  final l10n = AppLocalizations.of(context);
  showAppBottomSheet(
    context: context,
    title: l10n?.postJobSheetTitle ?? 'Post a New Job',
    child: _PostJobBottomSheetContent(ref: ref, initialCategory: initialCategory),
  );
}

class _PostJobBottomSheetContent extends StatefulWidget {
  final WidgetRef ref;
  final String? initialCategory;

  const _PostJobBottomSheetContent({required this.ref, this.initialCategory});

  @override
  State<_PostJobBottomSheetContent> createState() =>
      __PostJobBottomSheetContentState();
}

class __PostJobBottomSheetContentState
    extends State<_PostJobBottomSheetContent> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _titleController = TextEditingController();
  final TextEditingController _descController = TextEditingController();
  final TextEditingController _priceController = TextEditingController();
  final TextEditingController _locationController = TextEditingController();

  late String _selectedCategory;
  final TextEditingController _customCategoryController = TextEditingController();
  DateTime _scheduledDate = DateTime.now();
  bool _isUrgent = false;
  bool _isPosting = false;
  String? _errorMessage;

  List<String> get _categories => [...AppCategories.categoryIds, 'Other'];

  @override
  void initState() {
    super.initState();
    final isCustom = widget.initialCategory != null && !AppCategories.categoryIds.contains(widget.initialCategory);
    if (isCustom) {
      _selectedCategory = 'Other';
      _customCategoryController.text = widget.initialCategory!;
    } else {
      _selectedCategory = widget.initialCategory ?? _categories.first;
    }
    final user = widget.ref.read(userProfileProvider);
    _locationController.text = user.shortAddress.isNotEmpty ? user.shortAddress : 'Indiranagar, BLR';
  }

  @override
  void dispose() {
    _titleController.dispose();
    _descController.dispose();
    _priceController.dispose();
    _locationController.dispose();
    _customCategoryController.dispose();
    super.dispose();
  }

  XFile? _jobImageFile;
  final ImagePicker _picker = ImagePicker();
  final StorageService _storageService = StorageService();

  Future<void> _handlePickJobImage() async {
    final file = await _picker.pickImage(source: ImageSource.gallery, imageQuality: 85);
    if (file != null) {
      setState(() => _jobImageFile = file);
    }
  }

  Future<void> _handleSelectScheduledDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _scheduledDate,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 90)),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.light(
              primary: AppColors.brand,
              onPrimary: Colors.white,
              onSurface: AppColors.inkPrimary,
            ),
          ),
          child: child!,
        );
      },
    );
    if (picked != null) {
      setState(() => _scheduledDate = picked);
    }
  }

  Future<void> _handlePostJob() async {
    if (!_formKey.currentState!.validate()) return;

    final title = _titleController.text.trim();
    final desc = _descController.text.trim();
    final price = double.tryParse(_priceController.text.trim()) ?? 0.0;
    final location = _locationController.text.trim();
    final user = widget.ref.read(userProfileProvider);

    setState(() {
      _isPosting = true;
      _errorMessage = null;
    });

    String? imageUrl;
    if (_jobImageFile != null) {
      imageUrl = await _storageService.uploadJobImage(
        _jobImageFile!,
        'temp_${DateTime.now().millisecondsSinceEpoch}',
      );
    }

    final newJob = Job(
      id: '',
      employerId: null, // populated with auth.uid() inside createJob
      title: title,
      category: _selectedCategory == 'Other' ? _customCategoryController.text.trim() : _selectedCategory,
      description: desc.isNotEmpty ? desc : '.',
      wage: price,
      originalWage: _isUrgent ? (price * 1.2).roundToDouble() : null,
      status: 'open',
      rating: 5.0,
      reviewCount: 0,
      location: location.isNotEmpty ? location : 'Indiranagar, BLR',
      date: '${_scheduledDate.day}/${_scheduledDate.month}/${_scheduledDate.year}',
      employerName: user.name.isNotEmpty ? user.name : 'Employer',
      verified: true,
      urgent: _isUrgent,
      imageUrl: imageUrl,
    );

    try {
      final created = await widget.ref.read(jobServiceProvider).createJob(
            newJob,
            activeUserId: user.id,
          );

      if (mounted) {
        setState(() => _isPosting = false);
        widget.ref.invalidate(jobsByCategoryProvider);
        widget.ref.invalidate(jobsByEmployerProvider);
        widget.ref.invalidate(filteredJobsProvider);
        widget.ref.invalidate(dashboardStatsProvider);
        widget.ref.invalidate(customCategoriesProvider);
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.success,
            content: Row(
              children: [
                const Icon(Icons.check_circle_rounded, color: Colors.white, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Job "${created.title}" published successfully!',
                    style: GoogleFonts.inter(fontSize: 13, color: Colors.white),
                  ),
                ),
              ],
            ),
          ),
        );
      }
    } catch (e) {
      // Log the full raw error for debugging — visible in flutter run console
      debugPrint('❌ [PostJob] REAL ERROR from Supabase: $e');
      debugPrint('   Type: ${e.runtimeType}');

      if (mounted) {
        setState(() {
          _isPosting = false;
          // Show friendly message to user; full error is in console
          _errorMessage = 'Failed to post job: ${e.toString()}';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_errorMessage != null) ...[
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppColors.danger.withValues(alpha: 0.1),
                borderRadius: AppRadii.control,
                border: Border.all(color: AppColors.danger),
              ),
              child: Text(
                _errorMessage!,
                style: GoogleFonts.inter(fontSize: 12, color: AppColors.danger),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
          ],

          // Category Selector
          Text(
            'CATEGORY *',
            style: GoogleFonts.spaceMono(
              fontSize: 10,
              fontWeight: FontWeight.w500,
              color: AppColors.inkMuted,
            ),
          ),
          const SizedBox(height: 6),
          DropdownButtonFormField<String>(
            value: _selectedCategory,
            decoration: const InputDecoration(
              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            ),
            items: _categories.map((cat) {
              return DropdownMenuItem(
                value: cat,
                child: Text(
                  cat == 'Other' ? '+ Other (specify)' : AppCategories.getLocalizedName(context, cat),
                  style: GoogleFonts.inter(fontSize: 13),
                ),
              );
            }).toList(),
            onChanged: (val) {
              if (val != null) setState(() => _selectedCategory = val);
            },
          ),
          if (_selectedCategory == 'Other') ...[
            const SizedBox(height: AppSpacing.md),
            Text(
              'SPECIFY CATEGORY *',
              style: GoogleFonts.spaceMono(
                fontSize: 10,
                fontWeight: FontWeight.w500,
                color: AppColors.inkMuted,
              ),
            ),
            const SizedBox(height: 6),
            TextFormField(
              controller: _customCategoryController,
              keyboardType: TextInputType.text,
              textCapitalization: TextCapitalization.words,
              style: GoogleFonts.inter(fontSize: 13, color: AppColors.inkPrimary),
              decoration: const InputDecoration(
                hintText: 'e.g. Furniture Assembly, Pet Sitting',
              ),
              validator: (val) {
                if (_selectedCategory == 'Other' && (val == null || val.trim().isEmpty)) {
                  return 'Please specify a custom category name';
                }
                return null;
              },
            ),
          ],
          const SizedBox(height: AppSpacing.md),

          // Job Title
          Text(
            'JOB TITLE *',
            style: GoogleFonts.spaceMono(
              fontSize: 10,
              fontWeight: FontWeight.w500,
              color: AppColors.inkMuted,
            ),
          ),
          const SizedBox(height: 6),
          TextFormField(
            controller: _titleController,
            keyboardType: TextInputType.text,
            textCapitalization: TextCapitalization.sentences,
            style: GoogleFonts.inter(fontSize: 13, color: AppColors.inkPrimary),
            decoration: const InputDecoration(
              hintText: 'e.g. 3 BHK Interior Wall Painting',
            ),
            validator: (val) =>
                val == null || val.trim().isEmpty ? 'Please enter a job title' : null,
          ),
          const SizedBox(height: AppSpacing.md),

          // Description
          Text(
            'DESCRIPTION *',
            style: GoogleFonts.spaceMono(
              fontSize: 10,
              fontWeight: FontWeight.w500,
              color: AppColors.inkMuted,
            ),
          ),
          const SizedBox(height: 6),
          TextFormField(
            controller: _descController,
            maxLines: 2,
            keyboardType: TextInputType.multiline,
            textCapitalization: TextCapitalization.sentences,
            style: GoogleFonts.inter(fontSize: 13, color: AppColors.inkPrimary),
            decoration: const InputDecoration(
              hintText: 'Provide task details, tools available, site requirements...',
            ),
            validator: (val) =>
                val == null || val.trim().isEmpty ? 'Please enter job description' : null,
          ),
          const SizedBox(height: AppSpacing.md),

          // Price & Location Row
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'DAILY WAGE (₹) *',
                      style: GoogleFonts.spaceMono(
                        fontSize: 10,
                        fontWeight: FontWeight.w500,
                        color: AppColors.inkMuted,
                      ),
                    ),
                    const SizedBox(height: 6),
                    TextFormField(
                      controller: _priceController,
                      keyboardType: TextInputType.number,
                      inputFormatters: const [
                        WesternDigitsTextInputFormatter(),
                      ],
                      style: GoogleFonts.spaceMono(fontSize: 13, color: AppColors.inkPrimary),
                      decoration: const InputDecoration(
                        hintText: '1200',
                      ),
                      validator: (val) {
                        if (val == null || val.trim().isEmpty) {
                          return 'Required';
                        }
                        final parsed = double.tryParse(val.trim());
                        if (parsed == null || parsed <= 0) {
                          return 'Must be > 0';
                        }
                        return null;
                      },
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
                      'LOCATION *',
                      style: GoogleFonts.spaceMono(
                        fontSize: 10,
                        fontWeight: FontWeight.w500,
                        color: AppColors.inkMuted,
                      ),
                    ),
                    const SizedBox(height: 6),
                    TextFormField(
                      controller: _locationController,
                      style: GoogleFonts.inter(fontSize: 13, color: AppColors.inkPrimary),
                      decoration: const InputDecoration(
                        hintText: 'Indiranagar, Stage 2',
                      ),
                      validator: (val) =>
                          val == null || val.trim().isEmpty ? 'Required' : null,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),

          // Scheduled Date Picker Row
          Text(
            'SCHEDULED DISPATCH DATE *',
            style: GoogleFonts.spaceMono(
              fontSize: 10,
              fontWeight: FontWeight.w500,
              color: AppColors.inkMuted,
            ),
          ),
          const SizedBox(height: 6),
          GestureDetector(
            onTap: _handleSelectScheduledDate,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              decoration: BoxDecoration(
                color: AppColors.surfaceRaised,
                borderRadius: AppRadii.control,
                border: Border.all(color: AppColors.border),
              ),
              child: Row(
                children: [
                  const Icon(Icons.calendar_today_rounded, size: 16, color: AppColors.brand),
                  const SizedBox(width: 8),
                  Text(
                    '${_scheduledDate.day}/${_scheduledDate.month}/${_scheduledDate.year}',
                    style: GoogleFonts.spaceMono(
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                      color: AppColors.inkPrimary,
                    ),
                  ),
                  const Spacer(),
                  Text(
                    'Change',
                    style: GoogleFonts.spaceMono(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: AppColors.brand,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),

          // Urgent Switch
          SwitchListTile(
            title: Text(
              'Mark as Urgent Dispatch',
              style: GoogleFonts.sora(fontSize: 13, fontWeight: FontWeight.bold),
            ),
            subtitle: Text(
              'Highlights posting for immediate worker bids',
              style: GoogleFonts.inter(fontSize: 11, color: AppColors.inkMuted),
            ),
            value: _isUrgent,
            activeThumbColor: AppColors.brand,
            onChanged: (val) => setState(() => _isUrgent = val),
            contentPadding: EdgeInsets.zero,
          ),
          const SizedBox(height: AppSpacing.sm),

          // Optional Job Site Photo Attachment
          Text(
            'OPTIONAL JOB SITE PHOTO',
            style: GoogleFonts.spaceMono(
              fontSize: 10,
              fontWeight: FontWeight.w500,
              color: AppColors.inkMuted,
            ),
          ),
          const SizedBox(height: 6),
          GestureDetector(
            onTap: _handlePickJobImage,
            child: Container(
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: AppColors.surfaceRaised,
                borderRadius: AppRadii.control,
                border: Border.all(color: AppColors.border),
              ),
              child: Row(
                children: [
                  Icon(
                    _jobImageFile != null ? Icons.check_circle_rounded : Icons.add_a_photo_rounded,
                    color: _jobImageFile != null ? AppColors.success : AppColors.brand,
                    size: 20,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      _jobImageFile != null
                          ? 'Photo attached: ${_jobImageFile!.name}'
                          : 'Attach photo of job site (e.g. sofa, wall)',
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        color: _jobImageFile != null ? AppColors.inkPrimary : AppColors.inkMuted,
                        fontWeight: _jobImageFile != null ? FontWeight.bold : FontWeight.normal,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // Submit CTA
          SizedBox(
            height: 48,
            child: ElevatedButton(
              onPressed: _isPosting ? null : _handlePostJob,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.brand,
                shape: RoundedRectangleBorder(borderRadius: AppRadii.control),
              ),
              child: _isPosting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : Text(
                      'Publish Job Posting',
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
            ),
          ),
        ],
      ),
    );
  }
}
