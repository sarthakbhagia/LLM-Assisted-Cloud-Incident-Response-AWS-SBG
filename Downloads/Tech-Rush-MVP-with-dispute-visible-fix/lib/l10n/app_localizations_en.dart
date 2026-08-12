// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appName => 'KaamSetu';

  @override
  String get appTagline => 'Daily Workforce Dispatch & Operations System';

  @override
  String get navDashboard => 'Dashboard';

  @override
  String get navJobPostings => 'Job Postings';

  @override
  String get navProfile => 'Profile';

  @override
  String get dashboardEmployerHeadline =>
      'What daily service do you need done today?';

  @override
  String get dashboardWorkerHeadline => 'Active Job Ledger & Direct Hires';

  @override
  String get dashboardEmployerSubhead =>
      'Connect with 1,200+ local daily-wage specialists';

  @override
  String get dashboardWorkerSubhead =>
      'Set your rate and view nearby daily postings';

  @override
  String get dashboardEmployerSearchPlaceholder =>
      'Search \"House Painting\", \"Plumbing\"...';

  @override
  String get dashboardWorkerSearchPlaceholder =>
      'Search jobs near Indiranagar...';

  @override
  String get dashboardEmployerBannerTitle => '100% Aadhaar Verified Daily Pros';

  @override
  String get dashboardWorkerBannerTitle => 'Guaranteed Same-Day UPI Payout';

  @override
  String get dashboardEmployerBannerSubhead =>
      'Book verified daily workers with instant response';

  @override
  String get dashboardWorkerBannerSubhead =>
      'Direct connection with verified local households';

  @override
  String get postNewJobByCategory => 'POST A NEW JOB BY CATEGORY';

  @override
  String get availableWorkCategories => 'AVAILABLE WORK CATEGORIES';

  @override
  String get postJobCta => '+ Post Job';

  @override
  String get categoriesCount => '6 Categories';

  @override
  String get categoryPainting => 'Painting';

  @override
  String get categoryCleaning => 'Cleaning';

  @override
  String get categoryPlumbing => 'Plumbing';

  @override
  String get categoryCooking => 'Cooking';

  @override
  String get categoryGardening => 'Gardening';

  @override
  String get categoryElectrical => 'Electrical';

  @override
  String get categoryCarpentry => 'Carpentry';

  @override
  String get categoryAll => 'All';

  @override
  String get badgeHighDemand => 'HIGH DEMAND';

  @override
  String get badgePopular => 'POPULAR';

  @override
  String get badgeUrgent => 'URGENT';

  @override
  String get badgeVerified => 'VERIFIED';

  @override
  String get badgePro => 'PRO';

  @override
  String get roleEmployer => 'EMPLOYER';

  @override
  String get roleWorker => 'WORKER';

  @override
  String get roleEmployerSubtitle => 'Hire local daily-wage workers for tasks';

  @override
  String get roleWorkerSubtitle => 'Find local daily jobs and earn same-day';

  @override
  String get authSignIn => 'Sign In';

  @override
  String get authSignUp => 'Sign Up';

  @override
  String get authWelcomeBack => 'Welcome Back';

  @override
  String get authCreateAccount => 'Create Account';

  @override
  String get authEmailAuth => 'EMAIL AUTH';

  @override
  String get authMobileOtp => 'MOBILE OTP';

  @override
  String get authEmail => 'EMAIL ADDRESS';

  @override
  String get authPassword => 'PASSWORD';

  @override
  String get authPhoneNumber => 'MOBILE NUMBER';

  @override
  String get authFullName => 'FULL NAME';

  @override
  String get authStreetAddress => 'STREET ADDRESS';

  @override
  String get authLocality => 'LOCALITY / AREA';

  @override
  String get authCity => 'CITY';

  @override
  String get authSelectRole => 'SELECT YOUR ROLE';

  @override
  String get authAlreadyHaveAccount => 'Already have an account? Sign In';

  @override
  String get authDontHaveAccount => 'Don\'t have an account? Sign Up';

  @override
  String get authSendOtpCta => 'SEND OTP & VERIFY';

  @override
  String get authCreateAccountCta => 'CREATE ACCOUNT & PROCEED';

  @override
  String get authSignInCta => 'SIGN IN TO KAAMSETU';

  @override
  String get authHeadingSignIn => 'SIGN IN TO KAAMSETU';

  @override
  String get authHeadingSignUp => 'CREATE AN ACCOUNT';

  @override
  String get jobListingsTitle => 'All Job Listings';

  @override
  String jobListingsCategoryTitle(String category) {
    return '$category Jobs';
  }

  @override
  String get searchPlaceholderListings => 'Search title, category, location...';

  @override
  String get filterButton => 'Filter';

  @override
  String get statusAll => 'ALL';

  @override
  String get statusOpen => 'OPEN';

  @override
  String get statusAssigned => 'ASSIGNED';

  @override
  String get statusCompleted => 'DONE';

  @override
  String get statusCompletedFull => 'COMPLETED';

  @override
  String get perDay => 'per day';

  @override
  String applicantsCount(int count) {
    return '$count applicants';
  }

  @override
  String get noListingsFound => 'No listings found matching filters.';

  @override
  String get resetFilters => 'Reset Filters';

  @override
  String get applyNow => 'Apply Now';

  @override
  String get splashModeEmployer => 'I NEED WORKERS';

  @override
  String get splashModeWorker => 'I\'M LOOKING FOR WORK';

  @override
  String get splashWorkerHeadline => 'Browse Open Daily Dispatches Nearby';

  @override
  String get splashSignInToBrowse => 'Sign In to Browse ->';

  @override
  String get statVerifiedPros => 'Verified Pros';

  @override
  String get statAvgDailyRate => 'Avg Daily Rate';

  @override
  String get statJobDispatch => 'Job Dispatch';

  @override
  String get splashFooterSecurity =>
      'RLS ENFORCED • AADHAAR VERIFIED WORKFORCE';

  @override
  String get jobDetailTitle => 'Job Dispatch Detail';

  @override
  String get jobOverviewSection => 'JOB OVERVIEW';

  @override
  String get jobLocationSection => 'JOB LOCATION';

  @override
  String get employerVerificationSection => 'EMPLOYER VERIFICATION';

  @override
  String get applicantsAssignmentSection => 'APPLICANTS & ASSIGNMENT';

  @override
  String get stepPosted => 'Posted';

  @override
  String get stepAssigned => 'Assigned';

  @override
  String get stepCompleted => 'Completed';

  @override
  String get dailyWageLabel => 'Daily Wage';

  @override
  String get postedDateLabel => 'Posted Date';

  @override
  String get categoryLabel => 'Category';

  @override
  String get urgencyLevelLabel => 'Urgency Level';

  @override
  String get aadhaarVerifiedEmployer => 'Aadhaar Verified Employer';

  @override
  String get applyForJobCta => 'Apply for this Job';

  @override
  String get alreadyApplied => 'Already Applied';

  @override
  String get assignWorkerCta => 'Assign Worker';

  @override
  String get markCompletedCta => 'Mark Job Completed';

  @override
  String get rateWorkerCta => 'Rate Worker';

  @override
  String jobAssignedTo(String name) {
    return 'Assigned to $name';
  }

  @override
  String get profileTitle => 'System Profile & Settings';

  @override
  String get verifiedUser => 'Verified User';

  @override
  String get verifiedEmployerBadge => 'Verified Employer';

  @override
  String get verifiedWorkerBadge => 'Verified Worker';

  @override
  String get trustAadhaar => 'Aadhaar Verified';

  @override
  String get trustBackground => 'Background Checked';

  @override
  String get trustSkill => 'Skill Certified';

  @override
  String get languageSettingTitle => 'App Language / भाषा';

  @override
  String get english => 'English';

  @override
  String get hindi => 'हिंदी';

  @override
  String get activeSkillsTitle => 'Active Skills & Certifications';

  @override
  String get portfolioGalleryTitle => 'Work Samples & Portfolio Gallery';

  @override
  String get portfolioInstruction =>
      'Tap any photo to view full resolution or update showcase';

  @override
  String get addWorkPhoto => '+ Add Work Photo';

  @override
  String get reviewsSectionTitle => 'Employer Reviews & Ratings';

  @override
  String get noReviewsYet => 'No reviews yet';

  @override
  String get noReviewsSubtext =>
      'Complete jobs to receive ratings and reviews from employers.';

  @override
  String get ratingBreakdownSubtext =>
      'Rating breakdown based on verified completed jobs';

  @override
  String get primaryAddressTitle => 'Primary Address & Location';

  @override
  String get editAddress => 'Edit Address';

  @override
  String get signOut => 'Sign Out';

  @override
  String get notificationsTitle => 'Notifications';

  @override
  String get markAllAsRead => 'Mark all as read';

  @override
  String get noNotifications => 'No notifications yet';

  @override
  String get noNotificationsSubtext =>
      'System alerts and dispatch updates will appear here.';

  @override
  String get recentSearches => 'RECENT SEARCHES';

  @override
  String get clearAll => 'Clear All';

  @override
  String get searchResults => 'Search Results';

  @override
  String get noSearchResults => 'No jobs match your query';

  @override
  String get postJobSheetTitle => 'Post a New Job';

  @override
  String get workCategoryLabel => 'WORK CATEGORY *';

  @override
  String get jobTitleLabel => 'JOB TITLE *';

  @override
  String get descriptionLabel => 'DESCRIPTION *';

  @override
  String get dailyWageInputLabel => 'DAILY WAGE (₹) *';

  @override
  String get photoAttachmentLabel => 'PHOTO ATTACHMENT';

  @override
  String get selectPhotoCta => 'Select Photo';

  @override
  String get postJobNowCta => 'POST JOB NOW';

  @override
  String get filterSheetTitle => 'Filter & Sort Jobs';

  @override
  String get priceRangeLabel => 'PRICE RANGE (DAILY WAGE)';

  @override
  String get sortByLabel => 'SORT BY';

  @override
  String get categoriesLabel => 'CATEGORIES';

  @override
  String get sortMostRecent => 'Most Recent';

  @override
  String get sortPriceLow => 'Price: Low to High';

  @override
  String get sortPriceHigh => 'Price: High to Low';

  @override
  String get sortRating => 'Rating';

  @override
  String get sortUrgency => 'Urgency';

  @override
  String get applyFiltersCta => 'APPLY FILTERS';

  @override
  String get rateWorkerSheetTitle => 'Rate Worker & Complete Job';

  @override
  String get rateWorkerSubtitle =>
      'How was the work quality performed by worker?';

  @override
  String get selectRatingLabel => 'Select Rating (1 to 5 Stars)';

  @override
  String get feedbackLabel => 'FEEDBACK / COMMENTS (OPTIONAL)';

  @override
  String get submitReviewCta => 'SUBMIT REVIEW & CLOSE JOB';

  @override
  String get updateAddressSheetTitle => 'Update Primary Address';

  @override
  String get saveAddressCta => 'SAVE ADDRESS';

  @override
  String get profileSystemReconfiguration => 'SYSTEM RECONFIGURATION';

  @override
  String get profileViewSystemGallery => 'View System Gallery & Widgets';

  @override
  String get profileTogglePalette => 'Toggle Dark/Warm Palette Tokens';

  @override
  String get profileClearCache => 'Clear Cached Dispatch Data';

  @override
  String get profileAccountCompliance => 'ACCOUNT & COMPLIANCE';

  @override
  String get profileAadhaarDoc => 'Aadhaar Document (Verified)';

  @override
  String get profileBankAccount => 'Bank Account for Instant UPI Payout';

  @override
  String get profileSignOut => 'Sign Out of Session';

  @override
  String get profileDispatchSpecs => 'WORKFORCE DISPATCH SPECS';

  @override
  String get profileExpectedDailyRate => 'Expected Daily Rate';

  @override
  String get profileDispatchRadius => 'Dispatch Radius';

  @override
  String get profilePreferredShift => 'Preferred Shift';

  @override
  String get profilePaymentMode => 'Payment Mode';

  @override
  String get profileEditSkills => 'Edit Skills ->';

  @override
  String get profileAddSample => '+ Add Sample';

  @override
  String get statActivePostings => 'Active Postings';

  @override
  String get statActivePostingsSubtext => '1 Painting, 1 Plumbing';

  @override
  String get statApplications => 'Applications';

  @override
  String get statApplicationsSubtext => '4 Verified Workers';

  @override
  String get statTotalDispatches => 'Total Dispatches';

  @override
  String get statTotalDispatchesSubtext => 'Completed Jobs';

  @override
  String get statAvgDailyPayout => 'Avg Daily Payout';

  @override
  String get statAvgDailyPayoutSubtext => 'Per Worker';

  @override
  String get statDailyWageRate => 'Daily Wage Rate';

  @override
  String get statSetByEmployer => 'Set by Employer';

  @override
  String get statRatingScore => 'Rating Score';

  @override
  String get stat24Reviews => '24 Reviews';

  @override
  String get statJobsCompleted => 'Jobs Completed';

  @override
  String get statOnTime => '100% On-Time';

  @override
  String get statApplicationsSent => 'Applications Sent';

  @override
  String get statPendingReview => 'Pending Review';

  @override
  String get headerRecentDispatchLedger => 'RECENT DISPATCH LEDGER';

  @override
  String get headerRecommendedJobsNearby => 'RECOMMENDED JOBS NEARBY';

  @override
  String get linkViewAll => 'View All ->';

  @override
  String get headerDispatchMetricsOverview => 'DISPATCH & METRICS OVERVIEW';

  @override
  String get headerMyWorkParameters => 'MY WORK PARAMETERS';

  @override
  String get headerActiveDispatchOps => 'Active Dispatch Operations';

  @override
  String get headerDailyAvailStatus => 'Daily Availability Status';

  @override
  String get subtextActiveDispatchOps =>
      'Open postings receiving applicant bids. Next dispatch scheduled for 09:00 AM tomorrow.';

  @override
  String get subtextDailyAvailStatus =>
      'Your profile is active in local dispatch pool. Employers nearby can view your skill certifications and call directly.';

  @override
  String get statusPostingsActive => 'POSTINGS ACTIVE';

  @override
  String get statusAvailable => 'AVAILABLE';

  @override
  String get jobDetailTaskRequirements => 'TASK & SITE REQUIREMENTS';

  @override
  String get jobDetailEmployerHeader => 'EMPLOYER & DISPATCH OWNER';

  @override
  String get jobDetailApplicantBids => 'APPLICANT BIDS & DISPATCH REGISTRY';

  @override
  String get jobDetailNoApps =>
      'No applications submitted yet. Workers nearby can express interest directly.';

  @override
  String get jobDetailAcceptCta => 'Accept';
}
