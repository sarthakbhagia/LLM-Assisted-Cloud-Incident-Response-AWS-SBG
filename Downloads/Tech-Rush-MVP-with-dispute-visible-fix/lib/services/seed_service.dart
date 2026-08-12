import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'supabase_service.dart';

class SeedService {
  final SupabaseClient _client = SupabaseService().client;

  /// Executes database seeding programmatically from Flutter client.
  /// Upserts realistic demo jobs, profiles, applications, reviews, and notifications.
  Future<bool> seedDemoData() async {
    try {
      final currentUser = _client.auth.currentUser;
      final String activeUserId = currentUser?.id ?? 'e0000000-0000-0000-0000-000000000001';

      if (kDebugMode) {
        print('🌱 [SeedService] Starting database seed for active user: $activeUserId');
      }

      // 1. Upsert Employer Profiles (e0000000-...)
      await _client.from('profiles').upsert([
        {
          'id': 'e0000000-0000-0000-0000-000000000001',
          'full_name': 'Sharma Household',
          'phone': '+919876543210',
          'email': 'sharma.household@kaamsetu.app',
          'role': 'employer',
          'street_address': 'Flat 302, Green Acres',
          'locality': 'Indiranagar',
          'city': 'BLR',
          'pincode': '560038',
          'photo_url': 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150',
        },
        {
          'id': 'e0000000-0000-0000-0000-000000000002',
          'full_name': 'Ananya Rao',
          'phone': '+919876543211',
          'email': 'ananya.rao@kaamsetu.app',
          'role': 'employer',
          'street_address': 'Villa 14, Palm Grove',
          'locality': 'Koramangala 4th Block',
          'city': 'BLR',
          'pincode': '560034',
          'photo_url': 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150',
        },
        {
          'id': 'e0000000-0000-0000-0000-000000000003',
          'full_name': 'Rajesh Varma',
          'phone': '+919876543212',
          'email': 'rajesh.varma@kaamsetu.app',
          'role': 'employer',
          'street_address': 'No. 88, 27th Main',
          'locality': 'HSR Layout Sector 1',
          'city': 'BLR',
          'pincode': '560102',
          'photo_url': 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150',
        },
      ]);

      // 2. Upsert Worker Profiles (f0000000-...)
      await _client.from('profiles').upsert([
        {
          'id': 'f0000000-0000-0000-0000-000000000001',
          'full_name': 'Ramesh Kumar',
          'phone': '+919123456780',
          'email': 'ramesh.painter@kaamsetu.app',
          'role': 'worker',
          'locality': 'Murugeshpalya',
          'city': 'BLR',
          'skills': ['House Painting', 'Wall Tiling', 'Waterproofing'],
          'daily_rate': 850.0,
          'dispatch_radius_km': 12.0,
          'availability_status': 'available',
          'photo_url': 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150',
        },
        {
          'id': 'f0000000-0000-0000-0000-000000000002',
          'full_name': 'Suresh Patel',
          'phone': '+919123456781',
          'email': 'suresh.electrician@kaamsetu.app',
          'role': 'worker',
          'locality': 'BTM Layout',
          'city': 'BLR',
          'skills': ['Wiring', 'MCB Repairs', 'Appliance Servicing'],
          'daily_rate': 950.0,
          'dispatch_radius_km': 15.0,
          'availability_status': 'available',
          'photo_url': 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150',
        },
        {
          'id': 'f0000000-0000-0000-0000-000000000003',
          'full_name': 'Lakshmi Devi',
          'phone': '+919123456782',
          'email': 'lakshmi.cleaner@kaamsetu.app',
          'role': 'worker',
          'locality': 'Ejipura',
          'city': 'BLR',
          'skills': ['Kitchen Deep Clean', 'South Indian Cooking', 'Carpet Steam Wash'],
          'daily_rate': 700.0,
          'dispatch_radius_km': 10.0,
          'availability_status': 'available',
          'photo_url': 'https://images.unsplash.com/photo-1567532939604-b6b5b0db2604?w=150',
        },
      ]);

      // 3. Upsert Jobs Across 6 Categories (d0000000-...)
      await _client.from('jobs').upsert([
        {
          'id': 'd0000000-0000-0000-0000-000000000001',
          'employer_id': 'e0000000-0000-0000-0000-000000000001',
          'title': 'Living Room Wall Painting & Asian Paints Touchup',
          'category': 'Painting',
          'description': 'Looking for an experienced painter to complete two accent wall coats using Asian Paints Royal. Primer included.',
          'price': 1800.0,
          'original_price': 2200.0,
          'status': 'open',
          'rating': 4.9,
          'review_count': 14,
          'location': 'Indiranagar 100ft Rd',
          'date': 'Today, 2:00 PM',
          'employer_name': 'Sharma Household',
          'verified': true,
          'urgent': true,
        },
        {
          'id': 'd0000000-0000-0000-0000-000000000002',
          'employer_id': 'e0000000-0000-0000-0000-000000000002',
          'title': 'Balcony Waterproofing & Texture Coating',
          'category': 'Painting',
          'description': 'Balcony ceiling has minor dampness. Need crack filling & Dr. Fixit waterproof coating.',
          'price': 2200.0,
          'original_price': 2500.0,
          'status': 'assigned',
          'rating': 4.8,
          'review_count': 9,
          'location': 'Koramangala 4th Block',
          'date': 'Tomorrow, 10:00 AM',
          'employer_name': 'Ananya Rao',
          'worker_name': 'Ramesh Kumar',
          'verified': true,
          'urgent': false,
        },
        {
          'id': 'd0000000-0000-0000-0000-000000000004',
          'employer_id': 'e0000000-0000-0000-0000-000000000001',
          'title': '3BHK Post-Renovation Deep Cleaning',
          'category': 'Cleaning',
          'description': 'Urgent post-renovation dust cleanup. Includes window glass wiping, balcony scrubbing & floor mopping.',
          'price': 1200.0,
          'original_price': 1500.0,
          'status': 'open',
          'rating': 4.9,
          'review_count': 18,
          'location': 'Indiranagar 12th Main',
          'date': 'Today, 4:00 PM',
          'employer_name': 'Sharma Household',
          'verified': true,
          'urgent': true,
        },
        {
          'id': 'd0000000-0000-0000-0000-000000000007',
          'employer_id': 'e0000000-0000-0000-0000-000000000003',
          'title': 'Overhead Water Tank Leakage Fix',
          'category': 'Plumbing',
          'description': 'Water tank overflow sensor and valve leak needs immediate repair before evening.',
          'price': 650.0,
          'original_price': 800.0,
          'status': 'open',
          'rating': 4.8,
          'review_count': 12,
          'location': 'HSR Layout Sector 1',
          'date': 'Today, Urgent',
          'employer_name': 'Rajesh Varma',
          'verified': true,
          'urgent': true,
        },
        {
          'id': 'd0000000-0000-0000-0000-000000000009',
          'employer_id': 'e0000000-0000-0000-0000-000000000001',
          'title': 'Weekend House Gathering Banquet Chef',
          'category': 'Cooking',
          'description': 'Prepare traditional South Indian feast (Biryani, Starters, Payasam) for 15 guests.',
          'price': 1500.0,
          'original_price': 1800.0,
          'status': 'open',
          'rating': 5.0,
          'review_count': 20,
          'location': 'Indiranagar 100ft Rd',
          'date': 'Saturday, 12:00 PM',
          'employer_name': 'Sharma Household',
          'verified': true,
          'urgent': false,
        },
        {
          'id': 'd0000000-0000-0000-0000-000000000011',
          'employer_id': 'e0000000-0000-0000-0000-000000000001',
          'title': 'Terrace Organic Garden Setup & Pruning',
          'category': 'Gardening',
          'description': 'Trimming potted plants, adding Vermicompost, and setting up drip lines.',
          'price': 750.0,
          'original_price': 900.0,
          'status': 'open',
          'rating': 4.9,
          'review_count': 7,
          'location': 'Indiranagar 100ft Rd',
          'date': 'Tomorrow, 8:00 AM',
          'employer_name': 'Sharma Household',
          'verified': true,
          'urgent': false,
        },
        {
          'id': 'd0000000-0000-0000-0000-000000000013',
          'employer_id': 'e0000000-0000-0000-0000-000000000002',
          'title': 'Main Switchboard & MCB Tripping Diagnostic',
          'category': 'Electrical',
          'description': 'Power trips whenever AC is turned on. Need licensed electrician to inspect distribution box.',
          'price': 1100.0,
          'original_price': 1400.0,
          'status': 'open',
          'rating': 4.8,
          'review_count': 19,
          'location': 'Koramangala 4th Block',
          'date': 'Today, Urgent',
          'employer_name': 'Ananya Rao',
          'verified': true,
          'urgent': true,
        },
      ]);

      // 4. Also attach 1-2 jobs to active logged in user
      if (currentUser != null) {
        await _client.from('jobs').upsert([
          {
            'employer_id': currentUser.id,
            'title': 'Emergency Kitchen Sink Drain Unclogging',
            'category': 'Plumbing',
            'description': 'Sink is overflowing. Need heavy duty drain snake clearance immediately.',
            'price': 750.0,
            'original_price': 900.0,
            'status': 'open',
            'rating': 5.0,
            'review_count': 1,
            'location': 'My Home Address',
            'date': 'Today, Urgent',
            'employer_name': 'Me (Employer)',
            'verified': true,
            'urgent': true,
          },
        ]);

        await _client.from('notifications').upsert([
          {
            'id': 'c0000000-0000-0000-0000-000000000008',
            'user_id': currentUser.id,
            'type': 'system',
            'title': 'Welcome to KaamSetu Demo Mode!',
            'body': 'Your database has been populated with seed jobs, active workers, and dispatch metrics.',
            'is_read': false,
            'created_at': DateTime.now().toIso8601String(),
          },
          {
            'id': 'c0000000-0000-0000-0000-000000000009',
            'user_id': currentUser.id,
            'type': 'application_received',
            'title': 'New Applicant Interested',
            'body': 'Ramesh Kumar is available for immediate dispatch in your area.',
            'is_read': false,
            'created_at': DateTime.now().subtract(const Duration(minutes: 45)).toIso8601String(),
          },
        ]);
      }

      // 5. Seed Notifications (c0000000-...)
      await _client.from('notifications').upsert([
        {
          'id': 'c0000000-0000-0000-0000-000000000001',
          'user_id': 'e0000000-0000-0000-0000-000000000001',
          'type': 'application_received',
          'title': 'New Application Received',
          'body': 'Ramesh Kumar submitted interest for "Living Room Wall Painting"',
          'related_job_id': 'd0000000-0000-0000-0000-000000000001',
          'is_read': false,
        },
        {
          'id': 'c0000000-0000-0000-0000-000000000002',
          'user_id': 'f0000000-0000-0000-0000-000000000001',
          'type': 'job_accepted',
          'title': 'Job Dispatch Assigned!',
          'body': 'Ananya Rao accepted your bid for "Balcony Waterproofing"',
          'related_job_id': 'd0000000-0000-0000-0000-000000000002',
          'is_read': false,
        },
      ]);

      if (kDebugMode) {
        print('✅ [SeedService] Database successfully populated with realistic demo data.');
      }
      return true;
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [SeedService] Seeding notice: $e');
      }
      return false;
    }
  }
}
