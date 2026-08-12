import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:kaamsetu/services/supabase_service.dart';
import 'package:kaamsetu/services/profile_service.dart';

class _AllowHttpOverrides extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) {
    return super.createHttpClient(context)
      ..badCertificateCallback = (cert, host, port) => true;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  HttpOverrides.global = _AllowHttpOverrides();

  setUpAll(() async {
    SharedPreferences.setMockInitialValues({});
    await SupabaseService.initialize();
  });

  tearDownAll(() async {
    await SupabaseService().client.auth.signOut();
  });

  test('Profile Persistence: edits survive app restart (cold fetch from Supabase)', () async {
    final client = SupabaseService().client;
    final profileService = ProfileService();

    print('\n========================================================================');
    print('[Profile Persistence Test] Signing in test worker...');

    const wrkPhone = '+919876543211';
    User? user;
    try {
      await client.auth.signInWithOtp(phone: wrkPhone);
      final res = await client.auth.verifyOTP(
        phone: wrkPhone,
        token: '123456',
        type: OtpType.sms,
      );
      user = res.user;
    } catch (_) {
      user = client.auth.currentUser;
    }

    final userId = user?.id ?? '00000000-0000-0000-0000-000000000002';
    print('  -> Test user ID: $userId');

    print('\n[Step 1] Writing full profile to Supabase...');
    final success = await profileService.upsertProfile(
      userId: userId,
      fullName: 'Ramesh Kumar (Test)',
      streetAddress: 'Plot 12, Naya Mohalla',
      locality: 'Koramangala',
      city: 'BLR',
      email: 'ramesh@test.kaamsetu.com',
      phone: wrkPhone,
      role: 'worker',
      skills: ['Painting', 'Plumbing Repair', 'Waterproofing'],
      dailyRate: 850.0,
      dispatchRadiusKm: 20.0,
      availabilityStatus: 'available',
    );
    expect(success, isTrue);
    print('  -> Profile upserted successfully!');

    print('\n[Step 2] Cold restart simulation (fresh fetch from Supabase)...');
    final fetched = await profileService.fetchProfile(userId);
    expect(fetched, isNotNull);

    print('  -> name=${fetched!.name}, role=${fetched.role}');
    print('  -> skills=${fetched.skills}');
    print('  -> dailyRate=${fetched.dailyRate}, radius=${fetched.dispatchRadiusKm}, avail=${fetched.availabilityStatus}');

    expect(fetched.name, equals('Ramesh Kumar (Test)'));
    expect(fetched.streetAddress, equals('Plot 12, Naya Mohalla'));
    expect(fetched.locality, equals('Koramangala'));
    expect(fetched.role, equals('worker'));
    expect(fetched.skills, containsAll(['Painting', 'Plumbing Repair', 'Waterproofing']));
    expect(fetched.dailyRate, equals(850.0));
    expect(fetched.dispatchRadiusKm, equals(20.0));
    expect(fetched.availabilityStatus, equals('available'));
    print('  -> All step 2 assertions PASSED!');

    print('\n[Step 3] Updating role, rate, and availability...');
    await profileService.upsertProfile(
      userId: userId,
      fullName: fetched.name,
      streetAddress: fetched.streetAddress,
      locality: fetched.locality,
      city: fetched.city,
      email: fetched.email,
      phone: fetched.phone,
      role: 'employer',
      skills: fetched.skills,
      dailyRate: 950.0,
      dispatchRadiusKm: fetched.dispatchRadiusKm,
      availabilityStatus: 'busy',
    );

    final refetched = await profileService.fetchProfile(userId);
    expect(refetched, isNotNull);
    expect(refetched!.role, equals('employer'));
    expect(refetched.dailyRate, equals(950.0));
    expect(refetched.availabilityStatus, equals('busy'));
    print('  -> Role switch, rate change, availability update PERSISTED!');

    print('\n🎉 PROFILE PERSISTENCE VERIFIED END-TO-END SUCCESSFULLY!');
    print('All fields (address/skills/rate/radius/availability/role) read from Supabase.\n');
  });
}
