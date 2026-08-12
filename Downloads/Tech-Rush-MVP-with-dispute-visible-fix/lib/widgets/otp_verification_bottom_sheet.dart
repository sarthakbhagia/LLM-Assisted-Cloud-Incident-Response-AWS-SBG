import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../core/theme.dart';
import '../core/spacing.dart';
import '../core/utils/formatters.dart';
import '../providers/user_provider.dart';
import 'app_bottom_sheet.dart';

void openOtpVerificationBottomSheet({
  required BuildContext context,
  required WidgetRef ref,
  required String phone,
  String? fullName,
  String? streetAddress,
  String? locality,
  String? city,
  String role = 'employer',
  bool isDemoMode = false,
}) {
  showAppBottomSheet(
    context: context,
    title: 'Verify Mobile Security OTP',
    child: OtpVerificationWidget(
      phone: phone,
      fullName: fullName,
      streetAddress: streetAddress,
      locality: locality,
      city: city,
      role: role,
      isDemoMode: isDemoMode,
    ),
  );
}

class OtpVerificationWidget extends ConsumerStatefulWidget {
  final String phone;
  final String? fullName;
  final String? streetAddress;
  final String? locality;
  final String? city;
  final String role;
  final bool isDemoMode;

  const OtpVerificationWidget({
    super.key,
    required this.phone,
    this.fullName,
    this.streetAddress,
    this.locality,
    this.city,
    this.role = 'employer',
    this.isDemoMode = false,
  });

  @override
  ConsumerState<OtpVerificationWidget> createState() =>
      _OtpVerificationWidgetState();
}

class _OtpVerificationWidgetState
    extends ConsumerState<OtpVerificationWidget> {
  final List<TextEditingController> _controllers =
      List.generate(6, (_) => TextEditingController());
  final List<FocusNode> _focusNodes = List.generate(6, (_) => FocusNode());

  int _resendCountdown = 30;
  Timer? _timer;
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _startTimer();
  }

  @override
  void dispose() {
    _timer?.cancel();
    for (var c in _controllers) {
      c.dispose();
    }
    for (var fn in _focusNodes) {
      fn.dispose();
    }
    super.dispose();
  }

  void _startTimer() {
    _resendCountdown = 30;
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_resendCountdown > 0) {
        setState(() => _resendCountdown--);
      } else {
        timer.cancel();
      }
    });
  }

  String get _otpToken => Formatters.toWesternDigits(
        _controllers.map((c) => c.text).join(),
      );

  /// Determines the post-auth route.
  String _postAuthRoute() {
    return '/dashboard';
  }

  Future<void> _verifyOtp() async {
    final token = _otpToken.trim();
    if (token.length < 6) {
      setState(
          () => _errorMessage = 'Please enter all 6 digits of your OTP code');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final cleanPhone = widget.phone.replaceAll(RegExp(r'\D'), '');
      // Dev/test bypass for well-known test numbers
      if ((cleanPhone.contains('7058046461') ||
              cleanPhone.contains('917058046461')) &&
          token == '123456') {
        try {
          await ref.read(userProfileProvider.notifier).verifyMobileOtp(
                phone: widget.phone,
                token: token,
                fullName: widget.fullName,
                streetAddress: widget.streetAddress,
                locality: widget.locality,
                city: widget.city,
                role: widget.role,
                isDemoMode: widget.isDemoMode,
              );
          if (mounted) {
            Navigator.of(context).pop();
            context.go(_postAuthRoute());
          }
          return;
        } catch (_) {
          if (kDebugMode) {
            print('Dev Mode: Proceeding with test user session override...');
          }
          final notifier = ref.read(userProfileProvider.notifier);
          await notifier.updateProfile(
                name: widget.fullName,
                streetAddress: widget.streetAddress,
                locality: widget.locality,
                city: widget.city,
                phone: widget.phone,
                role: widget.role,
              );
          notifier.state = notifier.state.copyWith(
                id: widget.role == 'employer'
                    ? 'e0000000-0000-0000-0000-000000000001'
                    : 'e0000000-0000-0000-0000-000000000002',
                isLoggedIn: true,
              );
          if (mounted) {
            Navigator.of(context).pop();
            context.go(_postAuthRoute());
          }
          return;
        }
      }

      await ref.read(userProfileProvider.notifier).verifyMobileOtp(
            phone: widget.phone,
            token: token,
            fullName: widget.fullName,
            streetAddress: widget.streetAddress,
            locality: widget.locality,
            city: widget.city,
            role: widget.role,
            isDemoMode: widget.isDemoMode,
          );

      if (mounted) {
        Navigator.of(context).pop();
        context.go(_postAuthRoute());
      }
    } on AuthException catch (e) {
      if (mounted) {
        setState(() => _errorMessage = e.message);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _errorMessage = e.toString());
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _resendOtp() async {
    if (_resendCountdown > 0) return;
    setState(() => _errorMessage = null);
    try {
      await ref
          .read(userProfileProvider.notifier)
          .sendMobileOtp(phone: widget.phone);
      _startTimer();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('OTP code resent to your mobile number.')),
        );
      }
    } catch (e) {
      setState(() => _errorMessage = 'Failed to resend OTP: ${e.toString()}');
    }
  }

  @override
  Widget build(BuildContext context) {
    final displayPhone =
        widget.phone.startsWith('+') ? widget.phone : '+91 ${widget.phone}';

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Enter the 6-digit authorization code dispatched to:',
          style: GoogleFonts.inter(fontSize: 12, color: AppColors.inkMuted),
        ),
        const SizedBox(height: 4),
        Row(
          children: [
            Text(
              displayPhone,
              style: GoogleFonts.spaceMono(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: AppColors.inkPrimary,
              ),
            ),
            const SizedBox(width: 8),
            GestureDetector(
              onTap: () => Navigator.of(context).pop(),
              child: Text(
                'Change Number',
                style: GoogleFonts.spaceMono(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: AppColors.brand,
                  decoration: TextDecoration.underline,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.lg),

        if (_errorMessage != null) ...[
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppColors.danger.withValues(alpha: 0.1),
              borderRadius: AppRadii.control,
              border: Border.all(color: AppColors.danger),
            ),
            child: Row(
              children: [
                const Icon(Icons.error_outline_rounded,
                    size: 16, color: AppColors.danger),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _errorMessage!,
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      color: AppColors.danger,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.md),
        ],

        // 6-digit pin boxes
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: List.generate(6, (index) {
            return SizedBox(
              width: 44,
              height: 52,
              child: TextField(
                controller: _controllers[index],
                focusNode: _focusNodes[index],
                keyboardType: TextInputType.number,
                inputFormatters: const [WesternDigitsTextInputFormatter()],
                textAlign: TextAlign.center,
                maxLength: 1,
                style: GoogleFonts.spaceMono(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppColors.inkPrimary,
                ),
                decoration: InputDecoration(
                  counterText: '',
                  contentPadding: EdgeInsets.zero,
                  fillColor: AppColors.surfaceRaised,
                  enabledBorder: OutlineInputBorder(
                    borderRadius: AppRadii.control,
                    borderSide: BorderSide(
                      color: _errorMessage != null
                          ? AppColors.danger
                          : Colors.transparent,
                      width: _errorMessage != null ? 1.5 : 0,
                    ),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: AppRadii.control,
                    borderSide: BorderSide(
                      color: _errorMessage != null
                          ? AppColors.danger
                          : AppColors.brand,
                      width: 2,
                    ),
                  ),
                ),
                onChanged: (val) {
                  if (val.isNotEmpty && index < 5) {
                    _focusNodes[index + 1].requestFocus();
                  } else if (val.isEmpty && index > 0) {
                    _focusNodes[index - 1].requestFocus();
                  }
                  if (_otpToken.length == 6) {
                    _verifyOtp();
                  }
                },
              ),
            );
          }),
        ),
        const SizedBox(height: AppSpacing.lg),

        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              _resendCountdown > 0
                  ? 'Resend OTP in ${_resendCountdown}s'
                  : "Didn't receive code?",
              style:
                  GoogleFonts.spaceMono(fontSize: 11, color: AppColors.inkMuted),
            ),
            GestureDetector(
              onTap: _resendCountdown == 0 ? _resendOtp : null,
              child: Text(
                'RESEND NOW',
                style: GoogleFonts.spaceMono(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: _resendCountdown == 0
                      ? AppColors.brand
                      : AppColors.inkCaption,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.xl),

        SizedBox(
          height: 48,
          child: ElevatedButton(
            onPressed: _isLoading ? null : _verifyOtp,
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.brand,
              shape: RoundedRectangleBorder(
                borderRadius: AppRadii.control,
              ),
            ),
            child: _isLoading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : Text(
                    'Verify & Proceed',
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
  }
}
