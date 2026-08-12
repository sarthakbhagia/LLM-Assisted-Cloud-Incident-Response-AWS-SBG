import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../providers/review_provider.dart';
import '../l10n/app_localizations.dart';

void openRateWorkerBottomSheet(
  BuildContext context,
  WidgetRef ref, {
  required String jobId,
  required String workerId,
  required String workerName,
}) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => RateWorkerBottomSheet(
      jobId: jobId,
      workerId: workerId,
      workerName: workerName,
    ),
  );
}

class RateWorkerBottomSheet extends ConsumerStatefulWidget {
  final String jobId;
  final String workerId;
  final String workerName;

  const RateWorkerBottomSheet({
    super.key,
    required this.jobId,
    required this.workerId,
    required this.workerName,
  });

  @override
  ConsumerState<RateWorkerBottomSheet> createState() =>
      _RateWorkerBottomSheetState();
}

class _RateWorkerBottomSheetState
    extends ConsumerState<RateWorkerBottomSheet> {
  int _selectedRating = 5;
  final TextEditingController _commentController = TextEditingController();
  bool _isSubmitting = false;

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  Future<void> _handleSubmit() async {
    setState(() => _isSubmitting = true);

    final review = await ref.read(reviewServiceProvider).submitReview(
          jobId: widget.jobId,
          workerId: widget.workerId,
          rating: _selectedRating,
          comment: _commentController.text,
        );

    if (mounted) {
      setState(() => _isSubmitting = false);
      if (review != null) {
        ref.invalidate(workerRatingSummaryProvider(widget.workerId));
        ref.invalidate(workerReviewsProvider(widget.workerId));
        Navigator.pop(context);

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.success,
            content: Text(
              'Thank you! Rated ${widget.workerName} $_selectedRating ★',
              style: GoogleFonts.inter(fontSize: 13, color: Colors.white),
            ),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
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

            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'RATE WORKER DISPATCH',
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
              'Rate ${widget.workerName}\'s performance on this completed job',
              style: GoogleFonts.sora(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppColors.inkPrimary,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Star Rating Selector
            Center(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(5, (index) {
                  final starValue = index + 1;
                  return IconButton(
                    iconSize: 36,
                    icon: Icon(
                      starValue <= _selectedRating
                          ? Icons.star_rounded
                          : Icons.star_border_rounded,
                      color: AppColors.warning,
                    ),
                    onPressed: () {
                      setState(() => _selectedRating = starValue);
                    },
                  );
                }),
              ),
            ),
            Center(
              child: Text(
                '$_selectedRating out of 5 Stars',
                style: GoogleFonts.spaceMono(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: AppColors.warning,
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Comment Text Field
            Text(
              'OPTIONAL FEEDBACK / COMMENT',
              style: GoogleFonts.spaceMono(
                fontSize: 10,
                fontWeight: FontWeight.w500,
                color: AppColors.inkMuted,
              ),
            ),
            const SizedBox(height: 6),
            TextField(
              controller: _commentController,
              maxLines: 3,
              style: GoogleFonts.inter(
                fontSize: 13,
                color: AppColors.inkPrimary,
              ),
              decoration: InputDecoration(
                hintText:
                    'Share feedback about quality, punctuality, and work standards...',
                hintStyle: GoogleFonts.inter(
                  fontSize: 12,
                  color: AppColors.inkMuted,
                ),
                fillColor: AppColors.canvas,
                filled: true,
                border: OutlineInputBorder(
                  borderRadius: AppRadii.control,
                  borderSide: const BorderSide(color: AppColors.border),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.xl),

            // Submit Button
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
                        'Submit Worker Review',
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
        ),
      ),
    );
  }
}
