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

enum AuthMethod { email, phone }

class SignUpScreen extends ConsumerStatefulWidget {
  const SignUpScreen({super.key});

  @override
  ConsumerState<SignUpScreen> createState() => _SignUpScreenState();
}

class _SignUpScreenState extends ConsumerState<SignUpScreen> {
  AuthMethod _method = AuthMethod.email;

  // Role selection — default to employer (household)
  String _selectedRole = 'employer';

  final TextEditingController _fullNameController = TextEditingController();
  final TextEditingController _streetController = TextEditingController();
  final TextEditingController _localityController = TextEditingController();
  final TextEditingController _cityController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();

  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _fullNameController.dispose();
    _streetController.dispose();
    _localityController.dispose();
    _cityController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _handleCreateAccount() async {
    final name = _fullNameController.text.trim();
    final street = _streetController.text.trim();
    final locality = _localityController.text.trim();
    final city = _cityController.text.trim();
    final email = _emailController.text.trim();
    final password = _passwordController.text.trim();
    final phone = _phoneController.text.trim();

    if (name.isEmpty) {
      setState(() => _errorMessage = 'Please enter your full name');
      return;
    }
    if (street.isEmpty || locality.isEmpty || city.isEmpty) {
      setState(() => _errorMessage = 'Please complete your full address');
      return;
    }
    if (_method == AuthMethod.email) {
      if (email.isEmpty || !email.contains('@')) {
        setState(() => _errorMessage = 'Please enter a valid email address');
        return;
      }
      if (password.length < 6) {
        setState(() => _errorMessage = 'Password must be at least 6 characters');
        return;
      }
    } else {
      if (phone.length < 10) {
        setState(
            () => _errorMessage = 'Please enter a valid 10-digit mobile number');
        return;
      }
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      if (_method == AuthMethod.email) {
        await ref.read(userProfileProvider.notifier).signUpWithEmail(
              fullName: name,
              streetAddress: street,
              locality: locality,
              city: city,
              email: email,
              password: password,
              role: _selectedRole,
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
            fullName: name,
            streetAddress: street,
            locality: locality,
            city: city,
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
        _errorMessage = 'Sign up failed: ${e.toString()}';
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

              // Main Signup Card
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
                      l10n.authCreateAccount,
                      textAlign: TextAlign.center,
                      style: GoogleFonts.sora(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.inkPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Set up your KaamSetu profile to get started',
                      textAlign: TextAlign.center,
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        color: AppColors.inkMuted,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    // ── ROLE SELECTOR ──────────────────────────────────────
                    Text(
                      'I AM A *',
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
                          child: _RoleOption(
                            emoji: '🏠',
                            label: 'Employer',
                            sublabel: 'I hire daily workers',
                            isSelected: _selectedRole == 'employer',
                            onTap: () =>
                                setState(() => _selectedRole = 'employer'),
                          ),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: _RoleOption(
                            emoji: '🛠️',
                            label: 'Worker',
                            sublabel: 'I find daily work',
                            isSelected: _selectedRole == 'worker',
                            onTap: () =>
                                setState(() => _selectedRole = 'worker'),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.lg),

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

                    // Full Name
                    Text(
                      _selectedRole == 'worker'
                          ? 'FULL NAME *'
                          : 'FULL NAME / HOUSEHOLD NAME *',
                      style: GoogleFonts.spaceMono(
                        fontSize: 10,
                        fontWeight: FontWeight.w500,
                        color: AppColors.inkMuted,
                      ),
                    ),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _fullNameController,
                      textCapitalization: TextCapitalization.words,
                      enableSuggestions: false,
                      autocorrect: false,
                      style: GoogleFonts.inter(
                          fontSize: 13, color: AppColors.inkPrimary),
                      decoration: InputDecoration(
                        hintText: _selectedRole == 'worker'
                            ? 'e.g. Ramesh Kumar'
                            : 'e.g. Sharma Household',
                        prefixIcon: const Icon(Icons.person_outline_rounded,
                            size: 16, color: AppColors.inkMuted),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),

                    // Street / Flat Address
                    Text(
                      'STREET / FLAT *',
                      style: GoogleFonts.spaceMono(
                        fontSize: 10,
                        fontWeight: FontWeight.w500,
                        color: AppColors.inkMuted,
                      ),
                    ),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _streetController,
                      textCapitalization: TextCapitalization.words,
                      enableSuggestions: false,
                      autocorrect: false,
                      style: GoogleFonts.inter(
                          fontSize: 13, color: AppColors.inkPrimary),
                      decoration: const InputDecoration(
                        hintText: 'Flat 402, Sunrise Apt',
                        prefixIcon: Icon(Icons.home_outlined,
                            size: 16, color: AppColors.inkMuted),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),

                    // Locality & City
                    Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'LOCALITY *',
                                style: GoogleFonts.spaceMono(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w500,
                                  color: AppColors.inkMuted,
                                ),
                              ),
                              const SizedBox(height: 6),
                              TextField(
                                controller: _localityController,
                                textCapitalization: TextCapitalization.words,
                                enableSuggestions: false,
                                autocorrect: false,
                                style: GoogleFonts.inter(
                                    fontSize: 13, color: AppColors.inkPrimary),
                                decoration: const InputDecoration(
                                  hintText: 'Indiranagar',
                                  prefixIcon: Icon(Icons.location_on_outlined,
                                      size: 16, color: AppColors.inkMuted),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'CITY *',
                                style: GoogleFonts.spaceMono(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w500,
                                  color: AppColors.inkMuted,
                                ),
                              ),
                              const SizedBox(height: 6),
                              TextField(
                                controller: _cityController,
                                textCapitalization: TextCapitalization.words,
                                enableSuggestions: false,
                                autocorrect: false,
                                style: GoogleFonts.inter(
                                    fontSize: 13, color: AppColors.inkPrimary),
                                decoration: const InputDecoration(
                                  hintText: 'e.g. Pune',
                                  prefixIcon: Icon(
                                      Icons.location_city_rounded,
                                      size: 16,
                                      color: AppColors.inkMuted),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),

                    // Auth Method Toggle
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
                                _method = AuthMethod.email;
                                _errorMessage = null;
                              }),
                              child: Container(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 8),
                                decoration: BoxDecoration(
                                  color: _method == AuthMethod.email
                                      ? AppColors.surfaceRaised
                                      : Colors.transparent,
                                  borderRadius: BorderRadius.circular(8),
                                  border: _method == AuthMethod.email
                                      ? Border.all(color: AppColors.border)
                                      : null,
                                ),
                                alignment: Alignment.center,
                                child: Text(
                                  l10n.authEmailAuth,
                                  style: GoogleFonts.spaceMono(
                                    fontSize: 11,
                                    fontWeight: _method == AuthMethod.email
                                        ? FontWeight.bold
                                        : FontWeight.normal,
                                    color: _method == AuthMethod.email
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
                                _method = AuthMethod.phone;
                                _errorMessage = null;
                              }),
                              child: Container(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 8),
                                decoration: BoxDecoration(
                                  color: _method == AuthMethod.phone
                                      ? AppColors.surfaceRaised
                                      : Colors.transparent,
                                  borderRadius: BorderRadius.circular(8),
                                  border: _method == AuthMethod.phone
                                      ? Border.all(color: AppColors.border)
                                      : null,
                                ),
                                alignment: Alignment.center,
                                child: Text(
                                  l10n.authMobileOtp,
                                  style: GoogleFonts.spaceMono(
                                    fontSize: 11,
                                    fontWeight: _method == AuthMethod.phone
                                        ? FontWeight.bold
                                        : FontWeight.normal,
                                    color: _method == AuthMethod.phone
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
                    const SizedBox(height: AppSpacing.md),

                    if (_method == AuthMethod.email) ...[
                      Text(
                        'EMAIL ADDRESS *',
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
                        'PASSWORD *',
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
                          hintText: 'At least 6 characters',
                          prefixIcon: Icon(Icons.lock_outline_rounded,
                              size: 16, color: AppColors.inkMuted),
                        ),
                      ),
                    ] else ...[
                      Text(
                        'MOBILE NUMBER *',
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

                    // Submit CTA
                    SizedBox(
                      height: 48,
                      child: ElevatedButton(
                        onPressed: _isLoading ? null : _handleCreateAccount,
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
                                    'Create Account as ${_selectedRole == 'worker' ? 'Worker 🛠️' : 'Employer 🏠'}',
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
                    'Already have an account? ',
                    style: GoogleFonts.inter(
                        fontSize: 13, color: AppColors.inkMuted),
                  ),
                  GestureDetector(
                    onTap: () => context.go('/auth/sign-in'),
                    child: Text(
                      'Sign In',
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

/// Reusable role option card widget
class _RoleOption extends StatelessWidget {
  final String emoji;
  final String label;
  final String sublabel;
  final bool isSelected;
  final VoidCallback onTap;

  const _RoleOption({
    required this.emoji,
    required this.label,
    required this.sublabel,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.brandSubtle : AppColors.canvas,
          borderRadius: AppRadii.card,
          border: Border.all(
            color: isSelected ? AppColors.brand : AppColors.border,
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Column(
          children: [
            Text(emoji, style: const TextStyle(fontSize: 26)),
            const SizedBox(height: 4),
            Text(
              label,
              style: GoogleFonts.sora(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: isSelected ? AppColors.brand : AppColors.inkPrimary,
              ),
            ),
            Text(
              sublabel,
              style: GoogleFonts.inter(
                fontSize: 10,
                color: AppColors.inkMuted,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
