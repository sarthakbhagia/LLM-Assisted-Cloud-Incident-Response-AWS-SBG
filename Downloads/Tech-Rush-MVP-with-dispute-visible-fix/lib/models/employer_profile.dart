class EmployerProfile {
  final String id;
  final String name;
  final String? phone;
  final String? photoUrl;
  final String location;
  final DateTime createdAt;

  const EmployerProfile({
    required this.id,
    required this.name,
    this.phone,
    this.photoUrl,
    required this.location,
    required this.createdAt,
  });
}
