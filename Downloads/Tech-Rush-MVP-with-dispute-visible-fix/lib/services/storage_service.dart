import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'supabase_service.dart';

class StorageService {
  final SupabaseClient _client = SupabaseService().client;

  /// Uploads a profile photo to 'profile-photos' bucket and returns its public URL
  Future<String?> uploadProfilePhoto(XFile imageFile, {String? userId}) async {
    try {
      final user = _client.auth.currentUser;
      final uid = userId ?? user?.id ?? 'demo_user';
      final fileExt = imageFile.name.split('.').last;
      final fileName = 'photo_${DateTime.now().millisecondsSinceEpoch}.$fileExt';
      final path = '$uid/$fileName';

      final bytes = await imageFile.readAsBytes();

      if (kIsWeb) {
        await _client.storage.from('profile-photos').uploadBinary(path, bytes);
      } else {
        final file = File(imageFile.path);
        await _client.storage.from('profile-photos').upload(
              path,
              file,
              fileOptions: const FileOptions(cacheControl: '3600', upsert: true),
            );
      }

      final publicUrl = _client.storage.from('profile-photos').getPublicUrl(path);
      if (kDebugMode) {
        print('✅ [StorageService] Uploaded profile photo: $publicUrl');
      }
      return publicUrl;
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [StorageService] Error uploading profile photo: $e');
      }
      return null;
    }
  }

  /// Uploads a job posting image to 'job-images' bucket and returns its public URL
  Future<String?> uploadJobImage(XFile imageFile, String jobId) async {
    try {
      final fileExt = imageFile.name.split('.').last;
      final fileName = 'job_${DateTime.now().millisecondsSinceEpoch}.$fileExt';
      final path = '$jobId/$fileName';

      final bytes = await imageFile.readAsBytes();

      if (kIsWeb) {
        await _client.storage.from('job-images').uploadBinary(path, bytes);
      } else {
        final file = File(imageFile.path);
        await _client.storage.from('job-images').upload(
              path,
              file,
              fileOptions: const FileOptions(cacheControl: '3600', upsert: true),
            );
      }

      final publicUrl = _client.storage.from('job-images').getPublicUrl(path);
      if (kDebugMode) {
        print('✅ [StorageService] Uploaded job image: $publicUrl');
      }
      return publicUrl;
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [StorageService] Error uploading job image: $e');
      }
      return null;
    }
  }

  /// Uploads a worker past work sample photo to 'profile-photos' bucket and returns public URL
  Future<String?> uploadWorkSample(XFile imageFile, String workerId) async {
    try {
      final fileExt = imageFile.name.split('.').last;
      final fileName = 'sample_${DateTime.now().millisecondsSinceEpoch}.$fileExt';
      final path = '$workerId/samples/$fileName';

      final bytes = await imageFile.readAsBytes();

      if (kIsWeb) {
        await _client.storage.from('profile-photos').uploadBinary(path, bytes);
      } else {
        final file = File(imageFile.path);
        await _client.storage.from('profile-photos').upload(
              path,
              file,
              fileOptions: const FileOptions(cacheControl: '3600', upsert: true),
            );
      }

      final publicUrl = _client.storage.from('profile-photos').getPublicUrl(path);
      if (kDebugMode) {
        print('✅ [StorageService] Uploaded work sample: $publicUrl');
      }
      return publicUrl;
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [StorageService] Error uploading work sample: $e');
      }
      return null;
    }
  }
}
