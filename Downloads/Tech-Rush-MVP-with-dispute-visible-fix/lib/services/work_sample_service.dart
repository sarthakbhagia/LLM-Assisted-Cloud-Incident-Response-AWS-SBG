import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'supabase_service.dart';
import 'storage_service.dart';

class WorkSampleService {
  final SupabaseClient _client = SupabaseService().client;
  final StorageService _storageService = StorageService();
  static final Map<String, List<String>> _localWorkSamples = {};
  static final RegExp _uuidRegExp = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  /// Fetches list of work sample image URLs for a worker
  Future<List<String>> fetchWorkSamples(String workerId) async {
    List<String> samples = [];

    if (_uuidRegExp.hasMatch(workerId)) {
      try {
        final res = await _client
            .from('work_samples')
            .select()
            .eq('worker_id', workerId)
            .order('created_at', ascending: false);
        final List data = res as List;
        samples = data.map((json) => json['image_url']?.toString() ?? '').where((url) => url.isNotEmpty).toList();
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ [WorkSampleService] Error fetching work samples: $e');
        }
      }
    }

    if (samples.isEmpty) {
      samples = _localWorkSamples[workerId] ?? [];
    }

    return samples;
  }

  /// Uploads and inserts a new work sample photo
  Future<String?> addWorkSample({
    required String workerId,
    required XFile imageFile,
  }) async {
    // 1. Upload photo to Supabase storage
    final publicUrl = await _storageService.uploadWorkSample(imageFile, workerId);
    if (publicUrl == null) return null;

    // Save locally
    _localWorkSamples.putIfAbsent(workerId, () => []);
    _localWorkSamples[workerId]!.insert(0, publicUrl);

    if (!_uuidRegExp.hasMatch(workerId)) {
      return publicUrl;
    }

    try {
      await _client.from('work_samples').insert({
        'worker_id': workerId,
        'image_url': publicUrl,
        'created_at': DateTime.now().toIso8601String(),
      });
      if (kDebugMode) {
        print('✅ [WorkSampleService] Inserted work sample for worker $workerId');
      }
      return publicUrl;
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [WorkSampleService] Error inserting work sample row: $e');
      }
      return publicUrl;
    }
  }
}
