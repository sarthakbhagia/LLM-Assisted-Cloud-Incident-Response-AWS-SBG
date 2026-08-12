import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../core/theme.dart';
import '../core/spacing.dart';

enum JobStepStatus { posted, interested, assigned, completed }

class JobStatusStepper extends StatelessWidget {
  final JobStepStatus currentStatus;

  const JobStatusStepper({
    super.key,
    required this.currentStatus,
  });

  int get _currentStepIndex {
    switch (currentStatus) {
      case JobStepStatus.posted:
        return 0;
      case JobStepStatus.interested:
        return 1;
      case JobStepStatus.assigned:
        return 2;
      case JobStepStatus.completed:
        return 3;
    }
  }

  static const List<String> _stepLabels = [
    'POSTED',
    'INTERESTED',
    'ASSIGNED',
    'DONE',
  ];

  @override
  Widget build(BuildContext context) {
    final activeIdx = _currentStepIndex;

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.md,
      ),
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
            'DISPATCH LIFECYCLE STEPPER',
            style: GoogleFonts.spaceMono(
              fontSize: 10,
              fontWeight: FontWeight.w500,
              color: AppColors.inkMuted,
              letterSpacing: 1.0,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: List.generate(4, (index) {
              final isPassed = index < activeIdx;
              final isCurrent = index == activeIdx;

              Color nodeBorderColor;
              Color nodeBgColor;
              Widget nodeChild;

              if (isPassed) {
                nodeBorderColor = AppColors.success;
                nodeBgColor = AppColors.success;
                nodeChild = const Icon(
                  Icons.check_rounded,
                  size: 10,
                  color: Colors.white,
                );
              } else if (isCurrent) {
                nodeBorderColor = AppColors.brand;
                nodeBgColor = AppColors.brandSubtle;
                nodeChild = Container(
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(
                    color: AppColors.brand,
                    shape: BoxShape.circle,
                  ),
                );
              } else {
                nodeBorderColor = AppColors.border;
                nodeBgColor = AppColors.canvas;
                nodeChild = const SizedBox.shrink();
              }

              return Expanded(
                child: Column(
                  children: [
                    Row(
                      children: [
                        // Left Line Segment
                        Expanded(
                          child: Container(
                            height: 2.0,
                            color: index == 0
                                ? Colors.transparent
                                : (index <= activeIdx
                                    ? AppColors.success
                                    : AppColors.border),
                          ),
                        ),

                        // Stepper Node Circle
                        Container(
                          width: 20,
                          height: 20,
                          decoration: BoxDecoration(
                            color: nodeBgColor,
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: nodeBorderColor,
                              width: isCurrent ? 2.0 : 1.5,
                            ),
                          ),
                          alignment: Alignment.center,
                          child: nodeChild,
                        ),

                        // Right Line Segment
                        Expanded(
                          child: Container(
                            height: 2.0,
                            color: index == 3
                                ? Colors.transparent
                                : (index < activeIdx
                                    ? AppColors.success
                                    : AppColors.border),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      _stepLabels[index],
                      textAlign: TextAlign.center,
                      style: GoogleFonts.spaceMono(
                        fontSize: 9,
                        fontWeight:
                            isCurrent ? FontWeight.bold : FontWeight.w500,
                        color: isCurrent
                            ? AppColors.brand
                            : (isPassed
                                ? AppColors.success
                                : AppColors.inkMuted),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}
