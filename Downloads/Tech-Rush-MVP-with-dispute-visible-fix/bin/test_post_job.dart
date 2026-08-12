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
  print('🧪 Starting End-to-End Post Job Verification Test...');

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

  print('1. Authenticating as Demo Employer (sharma.household@kaamsetu.app)...');
  final authRes = await client.auth.signInWithPassword(
    email: 'sharma.household@kaamsetu.app',
    password: 'password123',
  );

  final user = authRes.user;
  if (user == null) {
    print('❌ Could not resolve authenticated user.');
    return;
  }

  print('  -> Authenticated User ID: ${user.id}');
  print('  -> Session JWT Token acquired: ${client.auth.currentSession != null}');

  final testJobId = 'd0000000-0000-0000-0000-${DateTime.now().millisecondsSinceEpoch.toString().padLeft(12, '0').substring(0, 12)}';
  final title = 'Test Live Wall Painting ${DateTime.now().second}';

  print('2. Inserting new job posting into Supabase jobs table...');
  final payload = <String, dynamic>{
    'id': testJobId,
    'employer_id': user.id,
    'household_id': user.id,
    'title': title,
    'category': 'Painting',
    'description': 'Realtime test job posting for end-to-end verification.',
    'price': 1950.0,
    'budget': 1950.0,
    'status': 'open',
    'location': 'Indiranagar 100ft Rd',
    'employer_name': 'Sharma Household',
    'urgent': true,
  };

  final insertRes = await client.from('jobs').insert(payload).select().single();
  final createdJob = Job.fromJson(insertRes);

  print('  ✅ Job posted successfully! Job ID: ${createdJob.id}, Title: "${createdJob.title}"');

  print('3. Verifying worker feed query (fetching open jobs from Supabase)...');
  final feedRes = await client
      .from('jobs')
      .select()
      .eq('status', 'open')
      .order('created_at', ascending: false);

  final List data = feedRes as List;
  final openJobs = data.map((j) => Job.fromJson(j)).toList();

  final foundInWorkerFeed = openJobs.any((j) => j.id == createdJob.id);

  if (foundInWorkerFeed) {
    print('\n================================================================');
    print('🎉 SUCCESS: POSTED JOB IS IMMEDIATELY VISIBLE IN WORKER FEED!');
    print('Total open jobs in feed: ${openJobs.length}');
    print('================================================================\n');
  } else {
    print('❌ Created job was not found in open jobs feed.');
  }
}
