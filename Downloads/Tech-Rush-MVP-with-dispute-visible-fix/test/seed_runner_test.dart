import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:kaamsetu/services/supabase_service.dart';
import 'package:kaamsetu/services/seed_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('Execute Database Seed Service against live Supabase backend', () async {
    print('🌱 Initializing Supabase client for automated seeding test...');
    await SupabaseService.initialize();

    print('🌱 Executing SeedService.seedDemoData()...');
    final seedService = SeedService();
    final success = await seedService.seedDemoData();

    expect(success, isTrue);
    print('🎉 SEEDING COMPLETED SUCCESSFULLY VIA FLUTTER SDK!');

    // Verify seeded jobs count
    final client = SupabaseService().client;
    final jobs = await client.from('jobs').select('id, title, category');
    print('📊 Total jobs currently in Supabase table: ${jobs.length}');
    expect(jobs.length, greaterThanOrEqualTo(5));
  });
}
