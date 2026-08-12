import 'package:supabase/supabase.dart';

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
  print('🧪 Testing Supabase GoTrue Auth Login with real bcrypt hash...');

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

  try {
    final res = await client.auth.signInWithPassword(
      email: 'sharma.household@kaamsetu.app',
      password: 'password123',
    );
    print('\n================================================================');
    print('🎉 SUCCESS: LOGGED IN WITH DEMO ACCOUNT VIA GOTRUE API!');
    print('  User ID: ${res.user?.id}');
    print('  Email: ${res.user?.email}');
    print('  Session Access Token: ${res.session?.accessToken.substring(0, 30)}...');
    print('================================================================\n');
  } catch (e) {
    print('❌ LOGIN FAILED: $e');
  }
}
