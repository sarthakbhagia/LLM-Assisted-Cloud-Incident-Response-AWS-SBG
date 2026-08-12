import 'package:supabase/supabase.dart';
import 'package:kaamsetu/models/job.dart';
import 'package:kaamsetu/models/user_profile.dart';

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
  print('🧪 Starting Full Job Posting Trace & Worker Feed Display Verification...');
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

  print('[STEP 1] Auditing User Session & Global State...');
  final session = client.auth.currentSession;
  final currentUser = client.auth.currentUser;
  final userProfile = const UserProfile();

  print('  -> currentSession: ${session != null}');
  print('  -> currentUser: ${currentUser?.id}');
  print('  -> userProfile.id: ${userProfile.id}');

  final String targetEmployerId = currentUser?.id ?? userProfile.id ?? 'e0000000-0000-0000-0000-000000000001';
  print('  -> Resolved target employerId for payload: $targetEmployerId\n');

  print('[STEP 2] Publishing New Job Posting to Supabase...');
  final testJobId = 'd0000000-0000-0000-0000-${DateTime.now().millisecondsSinceEpoch.toString().padLeft(12, '0').substring(0, 12)}';
  final jobTitle = 'Verified Deep House Painting ${DateTime.now().second}';

  final payload = <String, dynamic>{
    'id': testJobId,
    'employer_id': targetEmployerId,
    'household_id': targetEmployerId,
    'title': jobTitle,
    'category': 'Painting',
    'description': 'Full trace verification job insertion payload.',
    'price': 1850.0,
    'budget': 1850.0,
    'status': 'open',
    'location': 'Indiranagar 100ft Rd',
    'employer_name': userProfile.name,
    'urgent': true,
  };

  final res = await client.from('jobs').insert(payload).select().single();
  final createdJob = Job.fromJson(res);

  print('  ✅ Job successfully published to Supabase!');
  print('  -> Job ID: ${createdJob.id}');
  print('  -> Title: "${createdJob.title}"');
  print('  -> Employer ID: ${createdJob.employerId}');
  print('  -> Status: ${createdJob.status}\n');

  print('[STEP 3] Verifying Worker Feed Display Query...');
  final feedRes = await client
      .from('jobs')
      .select()
      .eq('status', 'open')
      .order('created_at', ascending: false);

  final List data = feedRes as List;
  final openJobs = data.map((j) => Job.fromJson(j)).toList();

  final isVisibleOnWorkerFeed = openJobs.any((j) => j.id == createdJob.id);

  if (isVisibleOnWorkerFeed) {
    print('========================================================================');
    print('🎉 FULL TRACE SUCCESSFUL: JOB PUBLISHED & VISIBLE ON WORKER FEED!');
    print('Total Open Jobs in Worker Feed: ${openJobs.length}');
    print('========================================================================');
  } else {
    print('❌ ERROR: Posted job was not found in open worker feed.');
  }
}
