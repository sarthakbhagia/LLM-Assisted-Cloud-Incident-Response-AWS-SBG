enum AvailabilityStatus { available, busy }

class WorkerProfile {
  final String id;
  final String name;
  final String? phone;
  final List<String> skills;
  final double expectedWage;
  final AvailabilityStatus availability;
  final String? bio;
  final double ratingAvg;
  final int ratingCount;
  final String? location;

  const WorkerProfile({
    required this.id,
    required this.name,
    this.phone,
    required this.skills,
    required this.expectedWage,
    required this.availability,
    this.bio,
    required this.ratingAvg,
    required this.ratingCount,
    this.location,
  });
}
