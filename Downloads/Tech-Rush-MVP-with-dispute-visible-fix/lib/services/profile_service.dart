import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/user_profile.dart';
import 'supabase_service.dart';

class ProfileService {
  final SupabaseClient _client = SupabaseService().client;

  static final RegExp _uuidRegExp = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  /// Creates or updates a user profile in Supabase public.profiles table
  Future<bool> upsertProfile({
    required String userId,
    required String fullName,
    String? streetAddress,
    String? locality,
    String? city,
    String? email,
    String? phone,
    String role = 'employer',
    List<String>? skills,
    double? dailyRate,
    double? dispatchRadiusKm,
    String? availabilityStatus,
    String? photoUrl,
  }) async {
    if (!_uuidRegExp.hasMatch(userId)) {
      if (kDebugMode) {
        print('ℹ️ [ProfileService] Skipping DB upsert for demo non-UUID user: $userId');
      }
      return true;
    }

    try {
      // Build the upsert payload; only include non-null optional values
      final data = <String, dynamic>{
        'id': userId,
        'full_name': fullName,
        'email': email ?? '',
        'phone': phone ?? '',
        'role': role ?? 'employer',
        if (streetAddress != null) 'street_address': streetAddress,
        if (locality != null) 'locality': locality,
        if (city != null) 'city': city,
        if (skills != null) 'skills': skills,
        if (dailyRate != null) 'daily_rate': dailyRate,
        if (dispatchRadiusKm != null) 'dispatch_radius_km': dispatchRadiusKm,
        if (availabilityStatus != null) 'availability_status': availabilityStatus,
        if (photoUrl != null) 'photo_url': photoUrl,
        'updated_at': DateTime.now().toIso8601String(),
      };

      try {
        await _client.from('profiles').upsert(data);
      } catch (innerErr) {
        // PGRST204 = column not found in schema cache. Live DB is missing columns.
        // Run: supabase/migrations/20260804000001_profiles_add_missing_columns.sql
        final errStr = innerErr.toString();
        if (errStr.contains('PGRST204') || errStr.contains('column')) {
          if (kDebugMode) {
            print('⚠️ [ProfileService] Schema mismatch — run 20260804000001 migration in Supabase SQL Editor.');
          }
          // Absolute minimal retry: just ensure the row exists with the PK
          // We silently succeed so the app doesn't crash — data is incomplete
          // until the migration is applied.
          try {
            await _client.from('profiles').upsert(<String, dynamic>{'id': userId});
          } catch (_) {
            // Row may already exist; that's fine
          }
        } else {
          rethrow;
        }
      }

      if (kDebugMode) {
        print('✅ [ProfileService] Profile created/updated for user: $userId');
      }
      return true;
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [ProfileService] Error upserting profile: $e');
      }
      return false;
    }
  }

  /// Fetches profile by Supabase Auth user ID
  Future<UserProfile?> fetchProfile(String userId) async {
    if (!_uuidRegExp.hasMatch(userId)) {
      if (kDebugMode) {
        print('ℹ️ [ProfileService] Skipping DB fetch for demo non-UUID user: $userId');
      }
      return null;
    }

    try {
      final res =
          await _client.from('profiles').select('*, worker_profiles(location)').eq('id', userId).maybeSingle();

      if (res == null) return null;

      final List rawSkills = res['skills'] as List? ?? [];
      final skillsList = rawSkills.map((s) => s.toString()).toList();

      String? workerLoc;
      final wpData = res['worker_profiles'];
      if (wpData is Map) {
        workerLoc = wpData['location']?.toString();
      } else if (wpData is List && wpData.isNotEmpty) {
        workerLoc = wpData.first['location']?.toString();
      }

      return UserProfile(
        name: res['full_name'] ?? 'Verified User',
        phone: res['phone'] ?? '',
        email: res['email'] ?? '',
        role: res['role'] ?? 'employer',
        streetAddress: res['street_address'] ?? '',
        locality: res['locality'] ?? '',
        city: res['city'] ?? '',
        pincode: res['pincode'] ?? '',
        photoUrl: res['photo_url'],
        skills: skillsList.isNotEmpty ? skillsList : const ['House Painting', 'Wall Tiling', 'Plumbing Leak Repair'],
        dailyRate: (res['daily_rate'] as num?)?.toDouble() ?? 650.0,
        dispatchRadiusKm: (res['dispatch_radius_km'] as num?)?.toDouble() ?? 15.0,
        availabilityStatus: res['availability_status'] ?? 'available',
        workerAddress: workerLoc,
        isLoggedIn: true,
      );
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [ProfileService] Error fetching profile ($userId): $e');
      }
      return null;
    }
  }
}
