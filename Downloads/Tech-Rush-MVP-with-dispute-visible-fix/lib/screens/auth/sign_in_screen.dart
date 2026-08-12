import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../../core/theme.dart';
import '../../core/spacing.dart';
import '../../core/utils/formatters.dart';
import '../../widgets/logo.dart';
import '../../widgets/otp_verification_bottom_sheet.dart';
import '../../providers/user_provider.dart';
import '../../providers/locale_provider.dart';
import '../../l10n/app_localizations.dart';

enum SignInMethod { email, phone }

class SignInScreen extends ConsumerStatefulWidget {
  const SignInScreen({super.key});

  @override
  ConsumerState<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends ConsumerState<SignInScreen> {
  SignInMethod _method = SignInMethod.email;

  // Role selection for OTP sign-in (email carries it from profile)
  String _selectedRole = 'employer';

  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();

  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _handleSignIn() async {
    final email = _emailController.text.trim();
    final password = _passwordController.text.trim();
    final phone = _phoneController.text.trim();

    if (_method == SignInMethod.email) {
      if (email.isEmpty || !email.contains('@')) {
        setState(() => _errorMessage = 'Please enter a valid email address');
        return;
      }
      if (password.isEmpty) {
        setState(() => _errorMessage = 'Please enter your password');
        return;
      }
    } else {
      if (phone.length < 10) {
        setState(() =>
            _errorMessage = 'Please enter a valid 10-digit mobile number');
        return;
      }
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      if (_method == SignInMethod.email) {
        await ref.read(userProfileProvider.notifier).signInWithEmail(
              email: email,
              password: password,
            );
        if (mounted) {
          context.go('/dashboard');
        }
      } else {
        final success = await ref
            .read(userProfileProvider.notifier)
            .sendMobileOtp(phone: phone);
        setState(() => _isLoading = false);
        if (mounted) {
          openOtpVerificationBottomSheet(
            context: context,
            ref: ref,
            phone: phone,
            role: _selectedRole,
            isDemoMode: !success,
          );
        }
      }
    } on AuthException catch (e) {
      setState(() {
        _errorMessage = e.message;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Sign in failed: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final currentLocale = ref.watch(localeProvider);

    return Scaffold(
      backgroundColor: AppColors.canvas,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const SizedBox(width: 40),
                  const Logo(size: 28, showSubtitle: true),
                  GestureDetector(
                    onTap: () =>
                        ref.read(localeProvider.notifier).toggleLocale(),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 9, vertical: 5),
                      decoration: BoxDecoration(
                        color: AppColors.surfaceRaised,
                        borderRadius: AppRadii.pill,
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Text(
                        currentLocale.languageCode == 'en' ? 'हिं' : 'EN',
                        style: GoogleFonts.spaceMono(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: AppColors.brand,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xl),

              // Main Sign In Card
              Container(
                padding: const EdgeInsets.all(AppSpacing.lg),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: AppRadii.card,
                  border: Border.all(color: AppColors.border),
                  boxShadow: AppShadows.card,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      l10n.authWelcomeBack,
                      textAlign: TextAlign.center,
                      style: GoogleFonts.sora(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.inkPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Sign in to access your dispatches & services',
                      textAlign: TextAlign.center,
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        color: AppColors.inkMuted,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    // ── ROLE SELECTOR (shown for phone OTP only) ───────────
                    // For email sign-in the role is loaded from the profile.
                    // For phone sign-in (first time or new device), let them pick.
                    if (_method == SignInMethod.phone) ...[
                      Text(
                        'SIGNING IN AS',
                        style: GoogleFonts.spaceMono(
                          fontSize: 10,
                          fontWeight: FontWeight.w500,
                          color: AppColors.inkMuted,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: _RoleChip(
                              emoji: '🏠',
                              label: 'Employer',
                              isSelected: _selectedRole == 'employer',
                              onTap: () =>
                                  setState(() => _selectedRole = 'employer'),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: _RoleChip(
                              emoji: '🛠️',
                              label: 'Worker',
                              isSelected: _selectedRole == 'worker',
                              onTap: () =>
                                  setState(() => _selectedRole = 'worker'),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.lg),
                    ],

                    // Error Message Banner
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

                    // Sign In Method Selector
                    Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: AppColors.canvas,
                        borderRadius: AppRadii.control,
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: GestureDetector(
                              onTap: () => setState(() {
                                _method = SignInMethod.email;
                                _errorMessage = null;
                              }),
                              child: Container(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 8),
                                decoration: BoxDecoration(
                                  color: _method == SignInMethod.email
                                      ? AppColors.surfaceRaised
                                      : Colors.transparent,
                                  borderRadius: BorderRadius.circular(8),
                                  border: _method == SignInMethod.email
                                      ? Border.all(color: AppColors.border)
                                      : null,
                                ),
                                alignment: Alignment.center,
                                child: Text(
                                  l10n.authEmailAuth,
                                  style: GoogleFonts.spaceMono(
                                    fontSize: 11,
                                    fontWeight: _method == SignInMethod.email
                                        ? FontWeight.bold
                                        : FontWeight.normal,
                                    color: _method == SignInMethod.email
                                        ? AppColors.inkPrimary
                                        : AppColors.inkMuted,
                                  ),
                                ),
                              ),
                            ),
                          ),
                          Expanded(
                            child: GestureDetector(
                              onTap: () => setState(() {
                                _method = SignInMethod.phone;
                                _errorMessage = null;
                              }),
                              child: Container(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 8),
                                decoration: BoxDecoration(
                                  color: _method == SignInMethod.phone
                                      ? AppColors.surfaceRaised
                                      : Colors.transparent,
                                  borderRadius: BorderRadius.circular(8),
                                  border: _method == SignInMethod.phone
                                      ? Border.all(color: AppColors.border)
                                      : null,
                                ),
                                alignment: Alignment.center,
                                child: Text(
                                  l10n.authMobileOtp,
                                  style: GoogleFonts.spaceMono(
                                    fontSize: 11,
                                    fontWeight: _method == SignInMethod.phone
                                        ? FontWeight.bold
                                        : FontWeight.normal,
                                    color: _method == SignInMethod.phone
                                        ? AppColors.inkPrimary
                                        : AppColors.inkMuted,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    if (_method == SignInMethod.email) ...[
                      Text(
                        l10n.authEmail,
                        style: GoogleFonts.spaceMono(
                          fontSize: 10,
                          fontWeight: FontWeight.w500,
                          color: AppColors.inkMuted,
                        ),
                      ),
                      const SizedBox(height: 6),
                      TextField(
                        controller: _emailController,
                        keyboardType: TextInputType.emailAddress,
                        style: GoogleFonts.inter(
                            fontSize: 13, color: AppColors.inkPrimary),
                        decoration: const InputDecoration(
                          hintText: 'user@example.com',
                          prefixIcon: Icon(Icons.mail_outline_rounded,
                              size: 16, color: AppColors.inkMuted),
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      Text(
                        l10n.authPassword,
                        style: GoogleFonts.spaceMono(
                          fontSize: 10,
                          fontWeight: FontWeight.w500,
                          color: AppColors.inkMuted,
                        ),
                      ),
                      const SizedBox(height: 6),
                      TextField(
                        controller: _passwordController,
                        obscureText: true,
                        style: GoogleFonts.inter(
                            fontSize: 13, color: AppColors.inkPrimary),
                        decoration: const InputDecoration(
                          hintText: '••••••••',
                          prefixIcon: Icon(Icons.lock_outline_rounded,
                              size: 16, color: AppColors.inkMuted),
                        ),
                      ),
                    ] else ...[
                      Text(
                        l10n.authPhoneNumber,
                        style: GoogleFonts.spaceMono(
                          fontSize: 10,
                          fontWeight: FontWeight.w500,
                          color: AppColors.inkMuted,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 14, vertical: 14),
                            decoration: const BoxDecoration(
                              color: AppColors.surfaceRaised,
                              borderRadius: BorderRadius.only(
                                topLeft: Radius.circular(12),
                                bottomLeft: Radius.circular(12),
                              ),
                              border: Border(
                                top: BorderSide(color: AppColors.border),
                                bottom: BorderSide(color: AppColors.border),
                                left: BorderSide(color: AppColors.border),
                              ),
                            ),
                            child: Text(
                              '+91',
                              style: GoogleFonts.spaceMono(
                                fontSize: 14,
                                fontWeight: FontWeight.bold,
                                color: AppColors.inkPrimary,
                              ),
                            ),
                          ),
                          Expanded(
                            child: TextField(
                              controller: _phoneController,
                              keyboardType: TextInputType.phone,
                              inputFormatters: const [
                                WesternDigitsTextInputFormatter(),
                              ],
                              maxLength: 10,
                              style: GoogleFonts.spaceMono(
                                  fontSize: 14, color: AppColors.inkPrimary),
                              decoration: const InputDecoration(
                                counterText: '',
                                hintText: '98765 43210',
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: AppSpacing.xl),

                    // Submit CTA Button
                    SizedBox(
                      height: 48,
                      child: ElevatedButton(
                        onPressed: _isLoading ? null : _handleSignIn,
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
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Text(
                                    _method == SignInMethod.email
                                        ? l10n.authSignIn
                                        : l10n.authSendOtpCta,
                                    style: GoogleFonts.inter(
                                      fontSize: 14,
                                      fontWeight: FontWeight.bold,
                                      color: Colors.white,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  const Icon(Icons.arrow_forward_rounded,
                                      size: 16, color: Colors.white),
                                ],
                              ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.lg),

              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'New here? ',
                    style: GoogleFonts.inter(
                        fontSize: 13, color: AppColors.inkMuted),
                  ),
                  GestureDetector(
                    onTap: () => context.go('/auth/sign-up'),
                    child: Text(
                      'Sign Up',
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                        color: AppColors.brand,
                        decoration: TextDecoration.underline,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xl),
            ],
          ),
        ),
      ),
    );
  }
}

/// Compact role chip for sign-in screen
class _RoleChip extends StatelessWidget {
  final String emoji;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _RoleChip({
    required this.emoji,
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.brandSubtle : AppColors.canvas,
          borderRadius: AppRadii.control,
          border: Border.all(
            color: isSelected ? AppColors.brand : AppColors.border,
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(emoji, style: const TextStyle(fontSize: 16)),
            const SizedBox(width: 6),
            Text(
              label,
              style: GoogleFonts.spaceMono(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: isSelected ? AppColors.brand : AppColors.inkMuted,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
