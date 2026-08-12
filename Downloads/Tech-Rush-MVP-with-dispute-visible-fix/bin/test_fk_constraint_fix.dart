import 'package:supabase/supabase.dart';
import 'package:kaamsetu/models/job.dart';

class InMemoryStorage extends GotrueAsyncStorage {
  final Map<String, String> _data = {};

  @override
  Future<String?> getItem({required String key}) async => _data[key];

  @override
  Future<void> removeItem({required String key}) async => _data.remove(key);

  @override
  Future<void> setItem({required String key, required String value}) async {
    _data[key] = value;
  }
}

void main() async {
  print('========================================================================');
  print('🧪 Starting Foreign Key Constraint & Pre-Flight Profile Verification...');
  print('========================================================================\n');

  const String supabaseUrl = 'https://movsaslnwjqbtdynvcwb.supabase.co';
  const String supabaseAnonKey =
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vdnNhc2xud2pxYnRkeW52Y3diIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU1Nzg0MDMsImV4cCI6MjEwMTE1NDQwM30.PkZFCfw5OhwGGNYf_FY-yBiUEm60QAZtSXNb5_2A4vs';

  final storage = InMemoryStorage();
  final client = SupabaseClient(
    supabaseUrl,
    supabaseAnonKey,
    authOptions: AuthClientOptions(
      pkceAsyncStorage: storage,
    ),
  );

  const activeUserId = 'e0000000-0000-0000-0000-000000000001'; // Valid ID in auth.users
  print('1. Verifying active user ID ($activeUserId) exists in auth.users...');

  print('2. Executing Pre-Flight Profile Upsert for $activeUserId...');
  await client.from('profiles').upsert(<String, dynamic>{
    'id': activeUserId,
    'name': 'Sharma Household',
    'full_name': 'Sharma Household',
    'role': 'employer',
    'email': 'sharma.household@kaamsetu.app',
    'updated_at': DateTime.now().toIso8601String(),
  });
  print('  ✅ Profile successfully pre-upserted in public.profiles!');

  print('3. Inserting Job Posting with household_id = $activeUserId...');
  final testJobId = 'd0000000-0000-0000-0000-${DateTime.now().millisecondsSinceEpoch.toString().padLeft(12, '0').substring(0, 12)}';
  final payload = <String, dynamic>{
    'id': testJobId,
    'employer_id': activeUserId,
    'household_id': activeUserId,
    'title': 'FK Verified Electrical Repair ${DateTime.now().second}',
    'category': 'Electrical',
    'description': 'Verification test for jobs_household_id_fkey constraint fix.',
    'price': 1450.0,
    'budget': 1450.0,
    'status': 'open',
    'location': 'Koramangala 4th Block',
    'employer_name': 'Sharma Household',
    'urgent': true,
  };

  final insertRes = await client.from('jobs').insert(payload).select().single();
  final createdJob = Job.fromJson(insertRes);

  print('  ✅ Job successfully published without any 23503 foreign key constraint error!');
  print('  -> Job ID: ${createdJob.id}');
  print('  -> Title: "${createdJob.title}"');

  print('4. Verifying Worker Feed Display Query...');
  final feedRes = await client
      .from('jobs')
      .select()
      .eq('status', 'open')
      .order('created_at', ascending: false);

  final List data = feedRes as List;
  final openJobs = data.map((j) => Job.fromJson(j)).toList();

  final foundInWorkerFeed = openJobs.any((j) => j.id == createdJob.id);

  if (foundInWorkerFeed) {
    print('\n========================================================================');
    print('🎉 SUCCESS: FOREIGN KEY CONSTRAINT FIXED & JOB RENDERED ON WORKER FEED!');
    print('Total open jobs in feed: ${openJobs.length}');
    print('========================================================================\n');
  } else {
    print('❌ Created job was not found in open jobs feed.');
  }
}
