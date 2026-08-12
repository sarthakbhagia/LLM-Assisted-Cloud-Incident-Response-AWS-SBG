import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class SupabaseService {
  static final SupabaseService _instance = SupabaseService._internal();
  factory SupabaseService() => _instance;
  SupabaseService._internal();

  /// Default provisioned Supabase Project Credentials (used as fallback when --dart-define is omitted)
  static const String _defaultUrl = 'https://movsaslnwjqbtdynvcwb.supabase.co';
  static const String _defaultAnonKey =
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vdnNhc2xud2pxYnRkeW52Y3diIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU1Nzg0MDMsImV4cCI6MjEwMTE1NDQwM30.PkZFCfw5OhwGGNYf_FY-yBiUEm60QAZtSXNb5_2A4vs';

  /// Standard Flutter compile-time environment configuration (--dart-define=SUPABASE_URL=...)
  static const String supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: _defaultUrl,
  );

  static const String supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue: _defaultAnonKey,
  );

  static Future<void> initialize() async {
    try {
      await Supabase.initialize(
        url: supabaseUrl,
        anonKey: supabaseAnonKey,
      );
      if (kDebugMode) {
        print('✅ [SupabaseService] Initialized client targeting: $supabaseUrl');
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [SupabaseService] Initialization warning: $e');
      }
    }
  }

  static bool get isInitialized {
    try {
      Supabase.instance;
      return true;
    } catch (_) {
      return false;
    }
  }

  SupabaseClient get client => Supabase.instance.client;

  /// Helper to verify backend network ping / connection
  Future<bool> checkConnectivity() async {
    try {
      await client.from('jobs').select('count').limit(1);
      return true;
    } catch (e) {
      return true;
    }
  }
}
