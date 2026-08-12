import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../providers/job_provider.dart';
import '../services/dashboard_stats_service.dart';
import '../providers/review_provider.dart';
import '../providers/user_provider.dart';
import '../services/rating_service.dart';

/// Opens the dual 👍 / 👎 rating bottom sheet.
///
/// [raterRole]   — 'employer' (household rates worker) or 'worker' (worker rates employer).
/// [evaluatorId] — UUID of the person giving the rating.
/// [targetId]    — UUID of the person being rated.
/// [targetName]  — Display name of the person being rated.
/// [employerId]  — UUID of the employer (used so worker can also rate employer).
/// [workerId]    — UUID of the worker (used so employer can also rate worker).
void openThumbsRatingBottomSheet(
  BuildContext context,
  WidgetRef ref, {
  required String jobId,
  required String evaluatorId,
  required String targetId,
  required String targetName,
  required String raterRole, // 'employer' or 'worker'
  required String employerId,
  required String workerId,
}) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => ThumbsRatingBottomSheet(
      jobId: jobId,
      evaluatorId: evaluatorId,
      targetId: targetId,
      targetName: targetName,
      raterRole: raterRole,
      employerId: employerId,
      workerId: workerId,
    ),
  );
}

class ThumbsRatingBottomSheet extends ConsumerStatefulWidget {
  final String jobId;
  final String evaluatorId;
  final String targetId;
  final String targetName;
  final String raterRole; // 'employer' or 'worker'
  final String employerId;
  final String workerId;

  const ThumbsRatingBottomSheet({
    super.key,
    required this.jobId,
    required this.evaluatorId,
    required this.targetId,
    required this.targetName,
    required this.raterRole,
    required this.employerId,
    required this.workerId,
  });

  @override
  ConsumerState<ThumbsRatingBottomSheet> createState() =>
      _ThumbsRatingBottomSheetState();
}

class _ThumbsRatingBottomSheetState
    extends ConsumerState<ThumbsRatingBottomSheet> {
  bool? _selectedThumb; // null = not selected, true = 👍, false = 👎
  bool _isSubmitting = false;
  bool _submitted = false;

  Future<void> _handleSubmit() async {
    if (_selectedThumb == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Please select 👍 or 👎 before submitting.',
            style: GoogleFonts.inter(fontSize: 13),
          ),
          backgroundColor: AppColors.brand,
        ),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    final service = ref.read(ratingServiceProvider);
    final result = await service.submitRating(
      jobId: widget.jobId,
      raterId: widget.evaluatorId,
      rateeId: widget.targetId,
      raterRole: widget.raterRole,
      isThumbsUp: _selectedThumb!,
    );

    if (!mounted) return;

    if (result.success) {
      setState(() {
        _isSubmitting = false;
        _submitted = true;
      });

      // Invalidate all rating-related providers for instant UI updates
      ref.invalidate(mutualRatingSummaryProvider(widget.targetId));
      ref.invalidate(hasRatedProvider((jobId: widget.jobId, raterId: widget.evaluatorId)));
      ref.invalidate(userProfileProvider);
      ref.invalidate(dashboardStatsProvider);
      ref.invalidate(jobDetailProvider(widget.jobId));
      ref.invalidate(jobsByCategoryProvider);

      await Future.delayed(const Duration(milliseconds: 1200));
      if (mounted) Navigator.pop(context);

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.success,
          content: Text(
            _selectedThumb == true
                ? '👍 Thumbs up sent to ${widget.targetName}!'
                : '👎 Feedback sent to ${widget.targetName}.',
            style: GoogleFonts.inter(fontSize: 13, color: Colors.white),
          ),
        ),
      );
    } else {
      setState(() => _isSubmitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.danger,
          content: Text(
            result.errorMessage ?? 'Failed to submit rating.',
            style: GoogleFonts.inter(fontSize: 13, color: Colors.white),
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isEmployerRating = widget.raterRole == 'employer';

    return Container(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom + AppSpacing.lg,
        left: AppSpacing.lg,
        right: AppSpacing.lg,
        top: AppSpacing.lg,
      ),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24.0)),
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Handle bar
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(2.0),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.md),

            // Header row
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  isEmployerRating
                      ? 'RATE YOUR WORKER'
                      : 'RATE THIS HOUSEHOLD',
                  style: GoogleFonts.spaceMono(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: AppColors.brand,
                    letterSpacing: 0.8,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close_rounded,
                      size: 20, color: AppColors.inkMuted),
                  onPressed: () => Navigator.pop(context),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),

            Text(
              isEmployerRating
                  ? 'How was ${widget.targetName}\'s performance?'
                  : 'How was your experience with ${widget.targetName}?',
              style: GoogleFonts.sora(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppColors.inkPrimary,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Your rating helps build trust in the KaamSetu community.',
              style: GoogleFonts.inter(
                fontSize: 12,
                color: AppColors.inkMuted,
              ),
            ),
            const SizedBox(height: AppSpacing.xl),

            // Submitted success state
            if (_submitted) ...[
              Center(
                child: Column(
                  children: [
                    Text(
                      _selectedThumb == true ? '👍' : '👎',
                      style: const TextStyle(fontSize: 56),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      'Rating submitted!',
                      style: GoogleFonts.sora(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.success,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.xxl),
            ] else ...[
              // Thumbs buttons
              Row(
                children: [
                  Expanded(
                    child: GestureDetector(
                      onTap: () => setState(() => _selectedThumb = true),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 180),
                        padding: const EdgeInsets.symmetric(vertical: 18),
                        decoration: BoxDecoration(
                          color: _selectedThumb == true
                              ? const Color(0xFFECFDF5)
                              : AppColors.canvas,
                          borderRadius: AppRadii.card,
                          border: Border.all(
                            color: _selectedThumb == true
                                ? AppColors.success
                                : AppColors.border,
                            width: _selectedThumb == true ? 2 : 1,
                          ),
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              '👍',
                              style: TextStyle(
                                fontSize: _selectedThumb == true ? 44 : 38,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              'Thumbs Up',
                              style: GoogleFonts.spaceMono(
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                                color: _selectedThumb == true
                                    ? AppColors.success
                                    : AppColors.inkMuted,
                              ),
                            ),
                            Text(
                              'Recommended',
                              style: GoogleFonts.inter(
                                fontSize: 10,
                                color: AppColors.inkMuted,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: GestureDetector(
                      onTap: () => setState(() => _selectedThumb = false),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 180),
                        padding: const EdgeInsets.symmetric(vertical: 18),
                        decoration: BoxDecoration(
                          color: _selectedThumb == false
                              ? const Color(0xFFFEF2F2)
                              : AppColors.canvas,
                          borderRadius: AppRadii.card,
                          border: Border.all(
                            color: _selectedThumb == false
                                ? AppColors.danger
                                : AppColors.border,
                            width: _selectedThumb == false ? 2 : 1,
                          ),
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              '👎',
                              style: TextStyle(
                                fontSize: _selectedThumb == false ? 44 : 38,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              'Thumbs Down',
                              style: GoogleFonts.spaceMono(
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                                color: _selectedThumb == false
                                    ? AppColors.danger
                                    : AppColors.inkMuted,
                              ),
                            ),
                            Text(
                              'Not recommended',
                              style: GoogleFonts.inter(
                                fontSize: 10,
                                color: AppColors.inkMuted,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xl),

              // Submit button
              SizedBox(
                width: double.infinity,
                height: 48,
                child: ElevatedButton(
                  onPressed: _isSubmitting ? null : _handleSubmit,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.brand,
                    shape: RoundedRectangleBorder(
                      borderRadius: AppRadii.control,
                    ),
                  ),
                  child: _isSubmitting
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor:
                                AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : Text(
                          'Submit Rating',
                          style: GoogleFonts.spaceMono(
                            fontSize: 13,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
            ],
          ],
        ),
      ),
    );
  }
}
