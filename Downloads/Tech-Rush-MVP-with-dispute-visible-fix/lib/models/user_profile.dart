class UserProfile {
  final String? id;
  final String name;
  final String phone;
  final String email;
  final String role;
  final String streetAddress;
  final String locality;
  final String city;
  final String pincode;
  final String? photoUrl;
  final List<String> skills;
  final double dailyRate;
  final double dispatchRadiusKm;
  final String availabilityStatus; // 'available' or 'busy'
  final String? workerAddress;
  final String? workerName;
  final bool isLoggedIn;

  const UserProfile({
    this.id,
    this.name = '',
    this.phone = '',
    this.email = '',
    this.role = 'employer',
    this.streetAddress = '',
    this.locality = '',
    this.city = '',
    this.pincode = '',
    this.photoUrl,
    this.skills = const ['House Painting', 'Wall Tiling', 'Plumbing Leak Repair'],
    this.dailyRate = 650.0,
    this.dispatchRadiusKm = 15.0,
    this.availabilityStatus = 'available',
    this.workerAddress,
    this.workerName,
    this.isLoggedIn = false,
  });

  bool get isAvailable => availabilityStatus == 'available';

  String? get address => streetAddress.isNotEmpty ? streetAddress : (locality.isNotEmpty ? locality : null);

  String get shortAddress {
    if (address != null && address!.isNotEmpty) {
      return address!;
    }
    if (city.isNotEmpty) {
      return city;
    }
    return 'Select Location';
  }

  String get fullAddress {
    final parts = [streetAddress, locality, city, pincode].where((p) => p.trim().isNotEmpty).toList();
    if (parts.isEmpty) return 'Location not set';
    return parts.join(', ');
  }

  UserProfile copyWith({
    String? id,
    String? name,
    String? phone,
    String? email,
    String? role,
    String? streetAddress,
    String? locality,
    String? city,
    String? pincode,
    String? photoUrl,
    List<String>? skills,
    double? dailyRate,
    double? dispatchRadiusKm,
    String? availabilityStatus,
    String? workerAddress,
    String? workerName,
    bool? isLoggedIn,
  }) {
    return UserProfile(
      id: id ?? this.id,
      name: name ?? this.name,
      phone: phone ?? this.phone,
      email: email ?? this.email,
      role: role ?? this.role,
      streetAddress: streetAddress ?? this.streetAddress,
      locality: locality ?? this.locality,
      city: city ?? this.city,
      pincode: pincode ?? this.pincode,
      photoUrl: photoUrl ?? this.photoUrl,
      skills: skills ?? this.skills,
      dailyRate: dailyRate ?? this.dailyRate,
      dispatchRadiusKm: dispatchRadiusKm ?? this.dispatchRadiusKm,
      availabilityStatus: availabilityStatus ?? this.availabilityStatus,
      workerAddress: workerAddress ?? this.workerAddress,
      workerName: workerName ?? this.workerName,
      isLoggedIn: isLoggedIn ?? this.isLoggedIn,
    );
  }
}
