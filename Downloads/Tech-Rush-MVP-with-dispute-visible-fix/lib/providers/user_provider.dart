import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/user_profile.dart';
import '../services/supabase_service.dart';
import '../services/profile_service.dart';
import '../core/utils/formatters.dart';

/// Global helper to retrieve the active user ID, falling back to a demo/test UUID if needed
String get activeUserId {
  final supabaseUser = SupabaseService().client.auth.currentUser?.id;
  if (supabaseUser != null && supabaseUser.isNotEmpty) {
    return supabaseUser;
  }
  // Fallback to a fixed test UUID (Sharma Household) so database operations work in dev mode
  return 'e0000000-0000-0000-0000-000000000001';
}

class UserProfileNotifier extends StateNotifier<UserProfile> {
  final ProfileService _profileService = ProfileService();

  UserProfileNotifier() : super(const UserProfile()) {
    _checkInitialSession();
  }

  /// Automatically checks if a user session is active on app start
  Future<void> _checkInitialSession() async {
    try {
      var user = SupabaseService().client.auth.currentUser;
      if (user == null && SupabaseService().client.auth.currentSession != null) {
        user = SupabaseService().client.auth.currentSession?.user;
      }
      if (user == null) {
        try {
          final res = await SupabaseService().client.auth.getUser();
          user = res.user;
        } catch (_) {}
      }
      if (user != null) {
        final profile = await _profileService.fetchProfile(user.id);
        if (profile != null) {
          state = profile.copyWith(id: user.id);
        } else {
          state = state.copyWith(
            id: user.id,
            email: user.email ?? state.email,
            phone: user.phone ?? state.phone,
            isLoggedIn: true,
          );
        }
      } else {
        state = state.copyWith(
          isLoggedIn: false,
        );
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ Error checking initial Supabase session: $e');
      }
    }
  }

  /// Real Supabase Email Sign Up with Profile creation
  Future<void> signUpWithEmail({
    required String fullName,
    required String streetAddress,
    required String locality,
    required String city,
    required String email,
    required String password,
    String phone = '',
    String role = 'employer',
  }) async {
    final authResponse = await SupabaseService().client.auth.signUp(
          email: email,
          password: password,
        );

    if (authResponse.session == null || authResponse.user == null) {
      throw const AuthException('Registration failed: Invalid credentials or session not established.');
    }
    final user = authResponse.user!;

    // Insert user record into public.profiles
    await _profileService.upsertProfile(
      userId: user.id,
      fullName: fullName,
      streetAddress: streetAddress,
      locality: locality,
      city: city,
      email: email,
      phone: phone,
      role: role,
    );

    // Refresh profile to load everything from database
    await refreshProfile();

    // Fallback if refresh returns null profile
    if (!state.isLoggedIn) {
      state = UserProfile(
        id: user.id,
        name: fullName,
        email: email,
        phone: phone,
        role: role,
        streetAddress: streetAddress,
        locality: locality,
        city: city,
        isLoggedIn: true,
      );
    }
  }

  /// Real Supabase Email & Password Sign In
  Future<void> signInWithEmail({
    required String email,
    required String password,
  }) async {
    final authResponse = await SupabaseService().client.auth.signInWithPassword(
          email: email,
          password: password,
        );

    if (authResponse.session == null || authResponse.user == null) {
      throw const AuthException('Login failed: Invalid credentials or session not established.');
    }
    final user = authResponse.user!;

    // Fetch user profile from Supabase profiles table
    final profile = await _profileService.fetchProfile(user.id);
    if (profile != null) {
      state = profile.copyWith(id: user.id);
    } else {
      state = UserProfile(
        id: user.id,
        name: user.email?.split('@').first ?? 'User',
        email: user.email ?? email,
        role: 'employer',
        streetAddress: 'Flat 302, Green Acres',
        locality: 'Indiranagar',
        city: 'BLR',
        isLoggedIn: true,
      );
    }
  }

  /// Update active user address in state and Supabase database
  Future<void> updateAddress({
    String? streetAddress,
    String? locality,
    String? city,
  }) async {
    final updated = state.copyWith(
      streetAddress: streetAddress,
      locality: locality,
      city: city,
    );
    state = updated;

    final user = SupabaseService().client.auth.currentUser;
    if (user != null) {
      await _profileService.upsertProfile(
        userId: user.id,
        fullName: updated.name,
        streetAddress: updated.streetAddress,
        locality: updated.locality,
        city: updated.city,
        email: updated.email,
        phone: updated.phone,
      );
    }
  }

  /// Real Supabase Send Mobile OTP with fallback handling
  Future<bool> sendMobileOtp({required String phone}) async {
    final digitsOnly = phone.replaceAll(RegExp(r'\D'), '');
    final phoneWithCountryCode = digitsOnly.startsWith('91') ? digitsOnly : '91$digitsOnly';
    final formattedPhone = '+$phoneWithCountryCode';
    try {
      await SupabaseService().client.auth.signInWithOtp(
            phone: formattedPhone,
          ).timeout(
            const Duration(seconds: 5),
            onTimeout: () => throw const AuthException('Supabase connection timed out'),
          );
      return true;
    } on AuthException catch (e) {
      if (e.message.contains('Unsupported phone provider') ||
          e.message.contains('disabled')) {
        return false; // SMS provider unconfigured in Supabase
      }
      rethrow;
    } catch (_) {
      return false;
    }
  }

  /// Real Supabase Verify Mobile OTP
  Future<void> verifyMobileOtp({
    required String phone,
    required String token,
    String? fullName,
    String? streetAddress,
    String? locality,
    String? city,
    String role = 'employer',
    bool isDemoMode = false,
  }) async {
    final cleanToken = Formatters.toWesternDigits(token).trim();
    final digitsOnly = phone.replaceAll(RegExp(r'\D'), '');
    final phoneWithCountryCode = digitsOnly.startsWith('91') ? digitsOnly : '91$digitsOnly';
    final formattedPhone = '+$phoneWithCountryCode';

    if (isDemoMode) {
      if (cleanToken != '123456') {
        throw const AuthException(
          'Invalid code. Please check and try again.',
        );
      }
      final targetUserId = role == 'employer'
          ? 'e0000000-0000-0000-0000-000000000001'
          : 'e0000000-0000-0000-0000-000000000002';

      // Ensure user's selected/entered details are saved
      await _profileService.upsertProfile(
        userId: targetUserId,
        fullName: fullName ?? 'Demo User',
        streetAddress: streetAddress ?? 'Flat 302, Green Acres',
        locality: locality ?? 'Indiranagar',
        city: city ?? 'BLR',
        email: '$phone@kaamsetu.app',
        phone: formattedPhone,
        role: role,
      );
      
      UserProfile? profile;
      try {
        profile = await _profileService.fetchProfile(targetUserId);
      } catch (_) {}

      if (profile != null) {
        state = profile.copyWith(id: targetUserId, isLoggedIn: true);
      } else {
        state = UserProfile(
          id: targetUserId,
          name: fullName ?? 'Demo User',
          phone: formattedPhone,
          email: '$phone@kaamsetu.app',
          streetAddress: streetAddress ?? 'Flat 302, Green Acres',
          locality: locality ?? 'Indiranagar',
          city: city ?? 'BLR',
          role: role,
          isLoggedIn: true,
        );
      }
      return;
    }

    User? user;

    try {
      final authResponse = await SupabaseService().client.auth.verifyOTP(
        phone: formattedPhone,
        token: cleanToken,
        type: OtpType.sms,
      ).timeout(
        const Duration(seconds: 5),
        onTimeout: () => throw const AuthException('Supabase connection timed out'),
      );
      
      if (authResponse.session == null || authResponse.user == null) {
        throw const AuthException('Session could not be established. Please re-enter OTP.');
      }
      user = authResponse.user;
    } catch (e) {
      rethrow;
    }

    if (user == null) {
      throw const AuthException('Verification failed: Session not established. Please try again or use Email Sign In.');
    }

    final String targetUserId = user.id;

    if (fullName != null && streetAddress != null && locality != null) {
      // New User Sign-Up registration
      await _profileService.upsertProfile(
        userId: targetUserId,
        fullName: fullName,
        streetAddress: streetAddress,
        locality: locality,
        city: city ?? 'BLR',
        email: user.email ?? '$phone@kaamsetu.app',
        phone: formattedPhone,
        role: role,
      );
    }

    // Refresh profile to update local state from Supabase
    await refreshProfile();

    // Secondary fallback in case DB fetch returned null profile
    if (!state.isLoggedIn) {
      state = UserProfile(
        id: targetUserId,
        name: fullName ?? 'Verified User',
        phone: formattedPhone,
        email: user.email ?? '',
        streetAddress: streetAddress ?? 'Flat 302, Green Acres',
        locality: locality ?? 'Indiranagar',
        city: city ?? 'BLR',
        role: role,
        isLoggedIn: true,
      );
    }
  }

  /// Real Supabase Sign Out
  Future<void> signOut() async {
    try {
      await SupabaseService().client.auth.signOut();
    } catch (_) {}
    state = const UserProfile(isLoggedIn: false);
  }

  /// Manually refresh profile from Supabase
  Future<void> refreshProfile() async {
    try {
      final userId = SupabaseService().client.auth.currentUser?.id ?? state.id ?? 'e0000000-0000-0000-0000-000000000001';
      final profile = await _profileService.fetchProfile(userId);
      if (profile != null) {
        state = profile.copyWith(id: userId, role: state.role);
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ Error refreshing profile: $e');
      }
    }
  }

  /// Local & remote profile state update helper
  Future<void> updateProfile({
    String? name,
    String? phone,
    String? email,
    String? role,
    String? streetAddress,
    String? locality,
    String? city,
    String? pincode,
    String? photoUrl,
    List<String>? skills,
    double? dailyRate,
    double? dispatchRadiusKm,
    String? availabilityStatus,
  }) async {
    state = state.copyWith(
      name: name,
      phone: phone,
      email: email,
      role: role,
      streetAddress: streetAddress,
      locality: locality,
      city: city,
      pincode: pincode,
      photoUrl: photoUrl,
      skills: skills,
      dailyRate: dailyRate,
      dispatchRadiusKm: dispatchRadiusKm,
      availabilityStatus: availabilityStatus,
    );

    final user = SupabaseService().client.auth.currentUser;
    if (user != null) {
      await _profileService.upsertProfile(
        userId: user.id,
        fullName: state.name,
        streetAddress: state.streetAddress,
        locality: state.locality,
        city: state.city,
        email: state.email,
        phone: state.phone,
        role: state.role,
        skills: state.skills,
        dailyRate: state.dailyRate,
        dispatchRadiusKm: state.dispatchRadiusKm,
        availabilityStatus: state.availabilityStatus,
        photoUrl: state.photoUrl,
      );
    }
  }

  /// Updates active user role ('employer' / 'worker') locally and in Supabase
  Future<void> updateRole(String newRole) async {
    await updateProfile(role: newRole);
  }
}

final userProfileProvider =
    StateNotifierProvider<UserProfileNotifier, UserProfile>((ref) {
  return UserProfileNotifier();
});
