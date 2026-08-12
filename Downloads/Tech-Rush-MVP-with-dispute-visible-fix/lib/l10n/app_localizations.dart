import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_hi.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('hi')
  ];

  /// App Name
  ///
  /// In en, this message translates to:
  /// **'KaamSetu'**
  String get appName;

  /// App Tagline
  ///
  /// In en, this message translates to:
  /// **'Daily Workforce Dispatch & Operations System'**
  String get appTagline;

  /// Bottom navigation dashboard item label
  ///
  /// In en, this message translates to:
  /// **'Dashboard'**
  String get navDashboard;

  /// Bottom navigation job postings item label
  ///
  /// In en, this message translates to:
  /// **'Job Postings'**
  String get navJobPostings;

  /// Bottom navigation profile item label
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get navProfile;

  /// Dashboard hero headline for employer role
  ///
  /// In en, this message translates to:
  /// **'What daily service do you need done today?'**
  String get dashboardEmployerHeadline;

  /// Dashboard hero headline for worker role
  ///
  /// In en, this message translates to:
  /// **'Active Job Ledger & Direct Hires'**
  String get dashboardWorkerHeadline;

  /// Dashboard hero subhead for employer role
  ///
  /// In en, this message translates to:
  /// **'Connect with 1,200+ local daily-wage specialists'**
  String get dashboardEmployerSubhead;

  /// Dashboard hero subhead for worker role
  ///
  /// In en, this message translates to:
  /// **'Set your rate and view nearby daily postings'**
  String get dashboardWorkerSubhead;

  /// Search input placeholder for employer
  ///
  /// In en, this message translates to:
  /// **'Search \"House Painting\", \"Plumbing\"...'**
  String get dashboardEmployerSearchPlaceholder;

  /// Search input placeholder for worker
  ///
  /// In en, this message translates to:
  /// **'Search jobs near Indiranagar...'**
  String get dashboardWorkerSearchPlaceholder;

  /// Value proposition banner title for employer
  ///
  /// In en, this message translates to:
  /// **'100% Aadhaar Verified Daily Pros'**
  String get dashboardEmployerBannerTitle;

  /// Value proposition banner title for worker
  ///
  /// In en, this message translates to:
  /// **'Guaranteed Same-Day UPI Payout'**
  String get dashboardWorkerBannerTitle;

  /// Value proposition banner subhead for employer
  ///
  /// In en, this message translates to:
  /// **'Book verified daily workers with instant response'**
  String get dashboardEmployerBannerSubhead;

  /// Value proposition banner subhead for worker
  ///
  /// In en, this message translates to:
  /// **'Direct connection with verified local households'**
  String get dashboardWorkerBannerSubhead;

  /// Category section title for employer
  ///
  /// In en, this message translates to:
  /// **'POST A NEW JOB BY CATEGORY'**
  String get postNewJobByCategory;

  /// Category section title for worker
  ///
  /// In en, this message translates to:
  /// **'AVAILABLE WORK CATEGORIES'**
  String get availableWorkCategories;

  /// Post job button text
  ///
  /// In en, this message translates to:
  /// **'+ Post Job'**
  String get postJobCta;

  /// Category count label
  ///
  /// In en, this message translates to:
  /// **'6 Categories'**
  String get categoriesCount;

  /// Painting category name
  ///
  /// In en, this message translates to:
  /// **'Painting'**
  String get categoryPainting;

  /// Cleaning category name
  ///
  /// In en, this message translates to:
  /// **'Cleaning'**
  String get categoryCleaning;

  /// Plumbing category name
  ///
  /// In en, this message translates to:
  /// **'Plumbing'**
  String get categoryPlumbing;

  /// Cooking category name
  ///
  /// In en, this message translates to:
  /// **'Cooking'**
  String get categoryCooking;

  /// Gardening category name
  ///
  /// In en, this message translates to:
  /// **'Gardening'**
  String get categoryGardening;

  /// Electrical category name
  ///
  /// In en, this message translates to:
  /// **'Electrical'**
  String get categoryElectrical;

  /// Carpentry category name
  ///
  /// In en, this message translates to:
  /// **'Carpentry'**
  String get categoryCarpentry;

  /// All categories label
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get categoryAll;

  /// High demand badge text
  ///
  /// In en, this message translates to:
  /// **'HIGH DEMAND'**
  String get badgeHighDemand;

  /// Popular badge text
  ///
  /// In en, this message translates to:
  /// **'POPULAR'**
  String get badgePopular;

  /// Urgent badge text
  ///
  /// In en, this message translates to:
  /// **'URGENT'**
  String get badgeUrgent;

  /// Verified badge text
  ///
  /// In en, this message translates to:
  /// **'VERIFIED'**
  String get badgeVerified;

  /// Pro badge text
  ///
  /// In en, this message translates to:
  /// **'PRO'**
  String get badgePro;

  /// Employer role label
  ///
  /// In en, this message translates to:
  /// **'EMPLOYER'**
  String get roleEmployer;

  /// Worker role label
  ///
  /// In en, this message translates to:
  /// **'WORKER'**
  String get roleWorker;

  /// Role selection subtitle for employer
  ///
  /// In en, this message translates to:
  /// **'Hire local daily-wage workers for tasks'**
  String get roleEmployerSubtitle;

  /// Role selection subtitle for worker
  ///
  /// In en, this message translates to:
  /// **'Find local daily jobs and earn same-day'**
  String get roleWorkerSubtitle;

  /// Sign in button label
  ///
  /// In en, this message translates to:
  /// **'Sign In'**
  String get authSignIn;

  /// Sign up button label
  ///
  /// In en, this message translates to:
  /// **'Sign Up'**
  String get authSignUp;

  /// Welcome back message
  ///
  /// In en, this message translates to:
  /// **'Welcome Back'**
  String get authWelcomeBack;

  /// Create account message
  ///
  /// In en, this message translates to:
  /// **'Create Account'**
  String get authCreateAccount;

  /// Email auth tab label
  ///
  /// In en, this message translates to:
  /// **'EMAIL AUTH'**
  String get authEmailAuth;

  /// Mobile OTP tab label
  ///
  /// In en, this message translates to:
  /// **'MOBILE OTP'**
  String get authMobileOtp;

  /// Email address input label
  ///
  /// In en, this message translates to:
  /// **'EMAIL ADDRESS'**
  String get authEmail;

  /// Password input label
  ///
  /// In en, this message translates to:
  /// **'PASSWORD'**
  String get authPassword;

  /// Phone number input label
  ///
  /// In en, this message translates to:
  /// **'MOBILE NUMBER'**
  String get authPhoneNumber;

  /// Full name input label
  ///
  /// In en, this message translates to:
  /// **'FULL NAME'**
  String get authFullName;

  /// Street address label
  ///
  /// In en, this message translates to:
  /// **'STREET ADDRESS'**
  String get authStreetAddress;

  /// Locality label
  ///
  /// In en, this message translates to:
  /// **'LOCALITY / AREA'**
  String get authLocality;

  /// City label
  ///
  /// In en, this message translates to:
  /// **'CITY'**
  String get authCity;

  /// Select role label
  ///
  /// In en, this message translates to:
  /// **'SELECT YOUR ROLE'**
  String get authSelectRole;

  /// Already have an account switch prompt
  ///
  /// In en, this message translates to:
  /// **'Already have an account? Sign In'**
  String get authAlreadyHaveAccount;

  /// Don't have an account switch prompt
  ///
  /// In en, this message translates to:
  /// **'Don\'t have an account? Sign Up'**
  String get authDontHaveAccount;

  /// Send OTP CTA button text
  ///
  /// In en, this message translates to:
  /// **'SEND OTP & VERIFY'**
  String get authSendOtpCta;

  /// Create account CTA button text
  ///
  /// In en, this message translates to:
  /// **'CREATE ACCOUNT & PROCEED'**
  String get authCreateAccountCta;

  /// Sign in CTA button text
  ///
  /// In en, this message translates to:
  /// **'SIGN IN TO KAAMSETU'**
  String get authSignInCta;

  /// Sign in screen title
  ///
  /// In en, this message translates to:
  /// **'SIGN IN TO KAAMSETU'**
  String get authHeadingSignIn;

  /// Sign up screen title
  ///
  /// In en, this message translates to:
  /// **'CREATE AN ACCOUNT'**
  String get authHeadingSignUp;

  /// Job listings screen title
  ///
  /// In en, this message translates to:
  /// **'All Job Listings'**
  String get jobListingsTitle;

  /// Category specific job listings title
  ///
  /// In en, this message translates to:
  /// **'{category} Jobs'**
  String jobListingsCategoryTitle(String category);

  /// Job listings search placeholder
  ///
  /// In en, this message translates to:
  /// **'Search title, category, location...'**
  String get searchPlaceholderListings;

  /// Filter button label
  ///
  /// In en, this message translates to:
  /// **'Filter'**
  String get filterButton;

  /// All status tab label
  ///
  /// In en, this message translates to:
  /// **'ALL'**
  String get statusAll;

  /// Open status tab label
  ///
  /// In en, this message translates to:
  /// **'OPEN'**
  String get statusOpen;

  /// Assigned status tab label
  ///
  /// In en, this message translates to:
  /// **'ASSIGNED'**
  String get statusAssigned;

  /// Completed status tab label
  ///
  /// In en, this message translates to:
  /// **'DONE'**
  String get statusCompleted;

  /// Completed full word label
  ///
  /// In en, this message translates to:
  /// **'COMPLETED'**
  String get statusCompletedFull;

  /// Per day wage label
  ///
  /// In en, this message translates to:
  /// **'per day'**
  String get perDay;

  /// Applicants count label
  ///
  /// In en, this message translates to:
  /// **'{count} applicants'**
  String applicantsCount(int count);

  /// Empty state text for listings
  ///
  /// In en, this message translates to:
  /// **'No listings found matching filters.'**
  String get noListingsFound;

  /// Reset filters button text
  ///
  /// In en, this message translates to:
  /// **'Reset Filters'**
  String get resetFilters;

  /// Apply now button text
  ///
  /// In en, this message translates to:
  /// **'Apply Now'**
  String get applyNow;

  /// Splash screen employer guest mode toggle button text
  ///
  /// In en, this message translates to:
  /// **'I NEED WORKERS'**
  String get splashModeEmployer;

  /// Splash screen worker guest mode toggle button text
  ///
  /// In en, this message translates to:
  /// **'I\'M LOOKING FOR WORK'**
  String get splashModeWorker;

  /// Splash screen worker mode hero headline
  ///
  /// In en, this message translates to:
  /// **'Browse Open Daily Dispatches Nearby'**
  String get splashWorkerHeadline;

  /// Splash screen sign in to browse link text
  ///
  /// In en, this message translates to:
  /// **'Sign In to Browse ->'**
  String get splashSignInToBrowse;

  /// Stats bar verified pros label
  ///
  /// In en, this message translates to:
  /// **'Verified Pros'**
  String get statVerifiedPros;

  /// Stats bar average daily rate label
  ///
  /// In en, this message translates to:
  /// **'Avg Daily Rate'**
  String get statAvgDailyRate;

  /// Stats bar job dispatch speed label
  ///
  /// In en, this message translates to:
  /// **'Job Dispatch'**
  String get statJobDispatch;

  /// Splash screen security footer text
  ///
  /// In en, this message translates to:
  /// **'RLS ENFORCED • AADHAAR VERIFIED WORKFORCE'**
  String get splashFooterSecurity;

  /// Job detail screen appbar title
  ///
  /// In en, this message translates to:
  /// **'Job Dispatch Detail'**
  String get jobDetailTitle;

  /// Job overview section title
  ///
  /// In en, this message translates to:
  /// **'JOB OVERVIEW'**
  String get jobOverviewSection;

  /// Job location section title
  ///
  /// In en, this message translates to:
  /// **'JOB LOCATION'**
  String get jobLocationSection;

  /// Employer verification section title
  ///
  /// In en, this message translates to:
  /// **'EMPLOYER VERIFICATION'**
  String get employerVerificationSection;

  /// Applicants and assignment section title
  ///
  /// In en, this message translates to:
  /// **'APPLICANTS & ASSIGNMENT'**
  String get applicantsAssignmentSection;

  /// Step tracker posted status
  ///
  /// In en, this message translates to:
  /// **'Posted'**
  String get stepPosted;

  /// Step tracker assigned status
  ///
  /// In en, this message translates to:
  /// **'Assigned'**
  String get stepAssigned;

  /// Step tracker completed status
  ///
  /// In en, this message translates to:
  /// **'Completed'**
  String get stepCompleted;

  /// Daily wage label
  ///
  /// In en, this message translates to:
  /// **'Daily Wage'**
  String get dailyWageLabel;

  /// Posted date label
  ///
  /// In en, this message translates to:
  /// **'Posted Date'**
  String get postedDateLabel;

  /// Category label
  ///
  /// In en, this message translates to:
  /// **'Category'**
  String get categoryLabel;

  /// Urgency level label
  ///
  /// In en, this message translates to:
  /// **'Urgency Level'**
  String get urgencyLevelLabel;

  /// Aadhaar verified employer badge text
  ///
  /// In en, this message translates to:
  /// **'Aadhaar Verified Employer'**
  String get aadhaarVerifiedEmployer;

  /// Apply for job CTA text
  ///
  /// In en, this message translates to:
  /// **'Apply for this Job'**
  String get applyForJobCta;

  /// Already applied status text
  ///
  /// In en, this message translates to:
  /// **'Already Applied'**
  String get alreadyApplied;

  /// Assign worker CTA button text
  ///
  /// In en, this message translates to:
  /// **'Assign Worker'**
  String get assignWorkerCta;

  /// Mark job completed CTA button text
  ///
  /// In en, this message translates to:
  /// **'Mark Job Completed'**
  String get markCompletedCta;

  /// Rate worker CTA button text
  ///
  /// In en, this message translates to:
  /// **'Rate Worker'**
  String get rateWorkerCta;

  /// Job assigned to worker text
  ///
  /// In en, this message translates to:
  /// **'Assigned to {name}'**
  String jobAssignedTo(String name);

  /// Profile page title
  ///
  /// In en, this message translates to:
  /// **'System Profile & Settings'**
  String get profileTitle;

  /// Verified user status
  ///
  /// In en, this message translates to:
  /// **'Verified User'**
  String get verifiedUser;

  /// Verified employer badge
  ///
  /// In en, this message translates to:
  /// **'Verified Employer'**
  String get verifiedEmployerBadge;

  /// Verified worker badge
  ///
  /// In en, this message translates to:
  /// **'Verified Worker'**
  String get verifiedWorkerBadge;

  /// Trust badge Aadhaar
  ///
  /// In en, this message translates to:
  /// **'Aadhaar Verified'**
  String get trustAadhaar;

  /// Trust badge background checked
  ///
  /// In en, this message translates to:
  /// **'Background Checked'**
  String get trustBackground;

  /// Trust badge skill certified
  ///
  /// In en, this message translates to:
  /// **'Skill Certified'**
  String get trustSkill;

  /// Language selection setting label
  ///
  /// In en, this message translates to:
  /// **'App Language / भाषा'**
  String get languageSettingTitle;

  /// English language label
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get english;

  /// Hindi language label
  ///
  /// In en, this message translates to:
  /// **'हिंदी'**
  String get hindi;

  /// Active skills section title
  ///
  /// In en, this message translates to:
  /// **'Active Skills & Certifications'**
  String get activeSkillsTitle;

  /// Portfolio gallery section title
  ///
  /// In en, this message translates to:
  /// **'Work Samples & Portfolio Gallery'**
  String get portfolioGalleryTitle;

  /// Portfolio instruction text
  ///
  /// In en, this message translates to:
  /// **'Tap any photo to view full resolution or update showcase'**
  String get portfolioInstruction;

  /// Add work photo CTA button text
  ///
  /// In en, this message translates to:
  /// **'+ Add Work Photo'**
  String get addWorkPhoto;

  /// Reviews section title
  ///
  /// In en, this message translates to:
  /// **'Employer Reviews & Ratings'**
  String get reviewsSectionTitle;

  /// No reviews empty state title
  ///
  /// In en, this message translates to:
  /// **'No reviews yet'**
  String get noReviewsYet;

  /// No reviews empty state subtext
  ///
  /// In en, this message translates to:
  /// **'Complete jobs to receive ratings and reviews from employers.'**
  String get noReviewsSubtext;

  /// Rating breakdown subtext
  ///
  /// In en, this message translates to:
  /// **'Rating breakdown based on verified completed jobs'**
  String get ratingBreakdownSubtext;

  /// Primary address section title
  ///
  /// In en, this message translates to:
  /// **'Primary Address & Location'**
  String get primaryAddressTitle;

  /// Edit address button text
  ///
  /// In en, this message translates to:
  /// **'Edit Address'**
  String get editAddress;

  /// Sign out button label
  ///
  /// In en, this message translates to:
  /// **'Sign Out'**
  String get signOut;

  /// Notifications title
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get notificationsTitle;

  /// Mark all as read action text
  ///
  /// In en, this message translates to:
  /// **'Mark all as read'**
  String get markAllAsRead;

  /// No notifications title
  ///
  /// In en, this message translates to:
  /// **'No notifications yet'**
  String get noNotifications;

  /// No notifications subtext
  ///
  /// In en, this message translates to:
  /// **'System alerts and dispatch updates will appear here.'**
  String get noNotificationsSubtext;

  /// Recent searches title
  ///
  /// In en, this message translates to:
  /// **'RECENT SEARCHES'**
  String get recentSearches;

  /// Clear all button text
  ///
  /// In en, this message translates to:
  /// **'Clear All'**
  String get clearAll;

  /// Search results section title
  ///
  /// In en, this message translates to:
  /// **'Search Results'**
  String get searchResults;

  /// No search results text
  ///
  /// In en, this message translates to:
  /// **'No jobs match your query'**
  String get noSearchResults;

  /// Post job bottom sheet title
  ///
  /// In en, this message translates to:
  /// **'Post a New Job'**
  String get postJobSheetTitle;

  /// Work category input label
  ///
  /// In en, this message translates to:
  /// **'WORK CATEGORY *'**
  String get workCategoryLabel;

  /// Job title input label
  ///
  /// In en, this message translates to:
  /// **'JOB TITLE *'**
  String get jobTitleLabel;

  /// Description input label
  ///
  /// In en, this message translates to:
  /// **'DESCRIPTION *'**
  String get descriptionLabel;

  /// Daily wage input label
  ///
  /// In en, this message translates to:
  /// **'DAILY WAGE (₹) *'**
  String get dailyWageInputLabel;

  /// Photo attachment label
  ///
  /// In en, this message translates to:
  /// **'PHOTO ATTACHMENT'**
  String get photoAttachmentLabel;

  /// Select photo button text
  ///
  /// In en, this message translates to:
  /// **'Select Photo'**
  String get selectPhotoCta;

  /// Post job submit button text
  ///
  /// In en, this message translates to:
  /// **'POST JOB NOW'**
  String get postJobNowCta;

  /// Filter sheet title
  ///
  /// In en, this message translates to:
  /// **'Filter & Sort Jobs'**
  String get filterSheetTitle;

  /// Price range filter label
  ///
  /// In en, this message translates to:
  /// **'PRICE RANGE (DAILY WAGE)'**
  String get priceRangeLabel;

  /// Sort by filter label
  ///
  /// In en, this message translates to:
  /// **'SORT BY'**
  String get sortByLabel;

  /// Categories filter label
  ///
  /// In en, this message translates to:
  /// **'CATEGORIES'**
  String get categoriesLabel;

  /// Sort option most recent
  ///
  /// In en, this message translates to:
  /// **'Most Recent'**
  String get sortMostRecent;

  /// Sort option price low to high
  ///
  /// In en, this message translates to:
  /// **'Price: Low to High'**
  String get sortPriceLow;

  /// Sort option price high to low
  ///
  /// In en, this message translates to:
  /// **'Price: High to Low'**
  String get sortPriceHigh;

  /// Sort option rating
  ///
  /// In en, this message translates to:
  /// **'Rating'**
  String get sortRating;

  /// Sort option urgency
  ///
  /// In en, this message translates to:
  /// **'Urgency'**
  String get sortUrgency;

  /// Apply filters button text
  ///
  /// In en, this message translates to:
  /// **'APPLY FILTERS'**
  String get applyFiltersCta;

  /// Rate worker sheet title
  ///
  /// In en, this message translates to:
  /// **'Rate Worker & Complete Job'**
  String get rateWorkerSheetTitle;

  /// Rate worker sheet subtitle
  ///
  /// In en, this message translates to:
  /// **'How was the work quality performed by worker?'**
  String get rateWorkerSubtitle;

  /// Select rating label
  ///
  /// In en, this message translates to:
  /// **'Select Rating (1 to 5 Stars)'**
  String get selectRatingLabel;

  /// Feedback label
  ///
  /// In en, this message translates to:
  /// **'FEEDBACK / COMMENTS (OPTIONAL)'**
  String get feedbackLabel;

  /// Submit review CTA text
  ///
  /// In en, this message translates to:
  /// **'SUBMIT REVIEW & CLOSE JOB'**
  String get submitReviewCta;

  /// Update address sheet title
  ///
  /// In en, this message translates to:
  /// **'Update Primary Address'**
  String get updateAddressSheetTitle;

  /// Save address CTA button text
  ///
  /// In en, this message translates to:
  /// **'SAVE ADDRESS'**
  String get saveAddressCta;

  /// No description provided for @profileSystemReconfiguration.
  ///
  /// In en, this message translates to:
  /// **'SYSTEM RECONFIGURATION'**
  String get profileSystemReconfiguration;

  /// No description provided for @profileViewSystemGallery.
  ///
  /// In en, this message translates to:
  /// **'View System Gallery & Widgets'**
  String get profileViewSystemGallery;

  /// No description provided for @profileTogglePalette.
  ///
  /// In en, this message translates to:
  /// **'Toggle Dark/Warm Palette Tokens'**
  String get profileTogglePalette;

  /// No description provided for @profileClearCache.
  ///
  /// In en, this message translates to:
  /// **'Clear Cached Dispatch Data'**
  String get profileClearCache;

  /// No description provided for @profileAccountCompliance.
  ///
  /// In en, this message translates to:
  /// **'ACCOUNT & COMPLIANCE'**
  String get profileAccountCompliance;

  /// No description provided for @profileAadhaarDoc.
  ///
  /// In en, this message translates to:
  /// **'Aadhaar Document (Verified)'**
  String get profileAadhaarDoc;

  /// No description provided for @profileBankAccount.
  ///
  /// In en, this message translates to:
  /// **'Bank Account for Instant UPI Payout'**
  String get profileBankAccount;

  /// No description provided for @profileSignOut.
  ///
  /// In en, this message translates to:
  /// **'Sign Out of Session'**
  String get profileSignOut;

  /// No description provided for @profileDispatchSpecs.
  ///
  /// In en, this message translates to:
  /// **'WORKFORCE DISPATCH SPECS'**
  String get profileDispatchSpecs;

  /// No description provided for @profileExpectedDailyRate.
  ///
  /// In en, this message translates to:
  /// **'Expected Daily Rate'**
  String get profileExpectedDailyRate;

  /// No description provided for @profileDispatchRadius.
  ///
  /// In en, this message translates to:
  /// **'Dispatch Radius'**
  String get profileDispatchRadius;

  /// No description provided for @profilePreferredShift.
  ///
  /// In en, this message translates to:
  /// **'Preferred Shift'**
  String get profilePreferredShift;

  /// No description provided for @profilePaymentMode.
  ///
  /// In en, this message translates to:
  /// **'Payment Mode'**
  String get profilePaymentMode;

  /// No description provided for @profileEditSkills.
  ///
  /// In en, this message translates to:
  /// **'Edit Skills ->'**
  String get profileEditSkills;

  /// No description provided for @profileAddSample.
  ///
  /// In en, this message translates to:
  /// **'+ Add Sample'**
  String get profileAddSample;

  /// No description provided for @statActivePostings.
  ///
  /// In en, this message translates to:
  /// **'Active Postings'**
  String get statActivePostings;

  /// No description provided for @statActivePostingsSubtext.
  ///
  /// In en, this message translates to:
  /// **'1 Painting, 1 Plumbing'**
  String get statActivePostingsSubtext;

  /// No description provided for @statApplications.
  ///
  /// In en, this message translates to:
  /// **'Applications'**
  String get statApplications;

  /// No description provided for @statApplicationsSubtext.
  ///
  /// In en, this message translates to:
  /// **'4 Verified Workers'**
  String get statApplicationsSubtext;

  /// No description provided for @statTotalDispatches.
  ///
  /// In en, this message translates to:
  /// **'Total Dispatches'**
  String get statTotalDispatches;

  /// No description provided for @statTotalDispatchesSubtext.
  ///
  /// In en, this message translates to:
  /// **'Completed Jobs'**
  String get statTotalDispatchesSubtext;

  /// No description provided for @statAvgDailyPayout.
  ///
  /// In en, this message translates to:
  /// **'Avg Daily Payout'**
  String get statAvgDailyPayout;

  /// No description provided for @statAvgDailyPayoutSubtext.
  ///
  /// In en, this message translates to:
  /// **'Per Worker'**
  String get statAvgDailyPayoutSubtext;

  /// No description provided for @statDailyWageRate.
  ///
  /// In en, this message translates to:
  /// **'Daily Wage Rate'**
  String get statDailyWageRate;

  /// No description provided for @statSetByEmployer.
  ///
  /// In en, this message translates to:
  /// **'Set by Employer'**
  String get statSetByEmployer;

  /// No description provided for @statRatingScore.
  ///
  /// In en, this message translates to:
  /// **'Rating Score'**
  String get statRatingScore;

  /// No description provided for @stat24Reviews.
  ///
  /// In en, this message translates to:
  /// **'24 Reviews'**
  String get stat24Reviews;

  /// No description provided for @statJobsCompleted.
  ///
  /// In en, this message translates to:
  /// **'Jobs Completed'**
  String get statJobsCompleted;

  /// No description provided for @statOnTime.
  ///
  /// In en, this message translates to:
  /// **'100% On-Time'**
  String get statOnTime;

  /// No description provided for @statApplicationsSent.
  ///
  /// In en, this message translates to:
  /// **'Applications Sent'**
  String get statApplicationsSent;

  /// No description provided for @statPendingReview.
  ///
  /// In en, this message translates to:
  /// **'Pending Review'**
  String get statPendingReview;

  /// No description provided for @headerRecentDispatchLedger.
  ///
  /// In en, this message translates to:
  /// **'RECENT DISPATCH LEDGER'**
  String get headerRecentDispatchLedger;

  /// No description provided for @headerRecommendedJobsNearby.
  ///
  /// In en, this message translates to:
  /// **'RECOMMENDED JOBS NEARBY'**
  String get headerRecommendedJobsNearby;

  /// No description provided for @linkViewAll.
  ///
  /// In en, this message translates to:
  /// **'View All ->'**
  String get linkViewAll;

  /// No description provided for @headerDispatchMetricsOverview.
  ///
  /// In en, this message translates to:
  /// **'DISPATCH & METRICS OVERVIEW'**
  String get headerDispatchMetricsOverview;

  /// No description provided for @headerMyWorkParameters.
  ///
  /// In en, this message translates to:
  /// **'MY WORK PARAMETERS'**
  String get headerMyWorkParameters;

  /// No description provided for @headerActiveDispatchOps.
  ///
  /// In en, this message translates to:
  /// **'Active Dispatch Operations'**
  String get headerActiveDispatchOps;

  /// No description provided for @headerDailyAvailStatus.
  ///
  /// In en, this message translates to:
  /// **'Daily Availability Status'**
  String get headerDailyAvailStatus;

  /// No description provided for @subtextActiveDispatchOps.
  ///
  /// In en, this message translates to:
  /// **'Open postings receiving applicant bids. Next dispatch scheduled for 09:00 AM tomorrow.'**
  String get subtextActiveDispatchOps;

  /// No description provided for @subtextDailyAvailStatus.
  ///
  /// In en, this message translates to:
  /// **'Your profile is active in local dispatch pool. Employers nearby can view your skill certifications and call directly.'**
  String get subtextDailyAvailStatus;

  /// No description provided for @statusPostingsActive.
  ///
  /// In en, this message translates to:
  /// **'POSTINGS ACTIVE'**
  String get statusPostingsActive;

  /// No description provided for @statusAvailable.
  ///
  /// In en, this message translates to:
  /// **'AVAILABLE'**
  String get statusAvailable;

  /// No description provided for @jobDetailTaskRequirements.
  ///
  /// In en, this message translates to:
  /// **'TASK & SITE REQUIREMENTS'**
  String get jobDetailTaskRequirements;

  /// No description provided for @jobDetailEmployerHeader.
  ///
  /// In en, this message translates to:
  /// **'EMPLOYER & DISPATCH OWNER'**
  String get jobDetailEmployerHeader;

  /// No description provided for @jobDetailApplicantBids.
  ///
  /// In en, this message translates to:
  /// **'APPLICANT BIDS & DISPATCH REGISTRY'**
  String get jobDetailApplicantBids;

  /// No description provided for @jobDetailNoApps.
  ///
  /// In en, this message translates to:
  /// **'No applications submitted yet. Workers nearby can express interest directly.'**
  String get jobDetailNoApps;

  /// No description provided for @jobDetailAcceptCta.
  ///
  /// In en, this message translates to:
  /// **'Accept'**
  String get jobDetailAcceptCta;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'hi'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'hi':
      return AppLocalizationsHi();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
