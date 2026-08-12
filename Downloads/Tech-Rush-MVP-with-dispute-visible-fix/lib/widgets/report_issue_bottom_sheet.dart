import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/spacing.dart';
import '../core/theme.dart';
import '../providers/job_dispute_provider.dart';

void openReportIssueBottomSheet(
  BuildContext context,
  WidgetRef ref, {
  required String jobId,
  required String reporterId,
  required String reporterRole,
  required String jobTitle,
  String? otherPartyId,
}) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => ReportIssueBottomSheet(
      jobId: jobId,
      reporterId: reporterId,
      reporterRole: reporterRole,
      jobTitle: jobTitle,
      otherPartyId: otherPartyId,
    ),
  ).then((_) {
    ref.invalidate(myJobDisputeProvider((jobId: jobId, reporterId: reporterId)));
    ref.invalidate(jobDisputesProvider(jobId));
  });
}

class ReportIssueBottomSheet extends ConsumerStatefulWidget {
  final String jobId;
  final String reporterId;
  final String reporterRole;
  final String jobTitle;
  final String? otherPartyId;

  const ReportIssueBottomSheet({
    super.key,
    required this.jobId,
    required this.reporterId,
    required this.reporterRole,
    required this.jobTitle,
    this.otherPartyId,
  });

  @override
  ConsumerState<ReportIssueBottomSheet> createState() => _ReportIssueBottomSheetState();
}

class _ReportIssueBottomSheetState extends ConsumerState<ReportIssueBottomSheet> {
  static const _categories = [
    'Work quality',
    'Payment',
    'No-show',
    'Misconduct',
    'Other',
  ];

  String _category = _categories.first;
  final _descriptionController = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final description = _descriptionController.text.trim();
    if (description.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please describe the issue.')),
      );
      return;
    }

    setState(() => _submitting = true);
    final result = await ref.read(jobDisputeServiceProvider).submitDispute(
          jobId: widget.jobId,
          reporterId: widget.reporterId,
          reporterRole: widget.reporterRole,
          category: _category,
          description: description,
          otherPartyId: widget.otherPartyId,
          jobTitle: widget.jobTitle,
        );

    if (!mounted) return;
    setState(() => _submitting = false);

    if (result != null) {
      ref.invalidate(myJobDisputeProvider((jobId: widget.jobId, reporterId: widget.reporterId)));
      ref.invalidate(jobDisputesProvider(widget.jobId));
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.surface,
          content: Text(
            'Issue reported. It has been flagged for review.',
            style: GoogleFonts.inter(color: AppColors.inkPrimary),
          ),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not report the issue. Please try again.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.viewInsetsOf(context).bottom;
    return Container(
      padding: EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.lg + bottom),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.dangerSubtle,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.flag_outlined, color: AppColors.danger),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Report an issue',
                    style: GoogleFonts.sora(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.inkPrimary),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'Flag this completed job for review. This is separate from a rating.',
              style: GoogleFonts.inter(fontSize: 12, color: AppColors.inkMuted),
            ),
            const SizedBox(height: AppSpacing.lg),
            Text('ISSUE TYPE', style: GoogleFonts.spaceMono(fontSize: 10, color: AppColors.inkMuted, letterSpacing: 1)),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              value: _category,
              decoration: InputDecoration(
                filled: true,
                fillColor: AppColors.surfaceRaised,
                border: OutlineInputBorder(borderRadius: AppRadii.card, borderSide: const BorderSide(color: AppColors.border)),
              ),
              dropdownColor: AppColors.surfaceRaised,
              items: _categories.map((category) => DropdownMenuItem(value: category, child: Text(category))).toList(),
              onChanged: (value) => setState(() => _category = value ?? _categories.first),
            ),
            const SizedBox(height: AppSpacing.md),
            Text('WHAT HAPPENED?', style: GoogleFonts.spaceMono(fontSize: 10, color: AppColors.inkMuted, letterSpacing: 1)),
            const SizedBox(height: 8),
            TextField(
              controller: _descriptionController,
              minLines: 4,
              maxLines: 7,
              decoration: InputDecoration(
                hintText: 'Briefly describe the problem...',
                filled: true,
                fillColor: AppColors.surfaceRaised,
                border: OutlineInputBorder(borderRadius: AppRadii.card, borderSide: const BorderSide(color: AppColors.border)),
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _submitting ? null : _submit,
                icon: _submitting
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.flag_rounded, size: 17),
                label: Text(_submitting ? 'SUBMITTING...' : 'FLAG FOR REVIEW'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
