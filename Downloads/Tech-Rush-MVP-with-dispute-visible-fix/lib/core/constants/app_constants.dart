import '../../models/job_category.dart';

abstract class AppConstants {
  static const String appName = 'KaamSetu';
  static const String appTagline = 'Daily Workforce Dispatch & Operations System';
  static const String appVersion = 'v1.0';
  
  static List<String> get categories => AppCategories.categoryIdsWithAll;
}
