// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hindi (`hi`).
class AppLocalizationsHi extends AppLocalizations {
  AppLocalizationsHi([String locale = 'hi']) : super(locale);

  @override
  String get appName => 'कामसेतु';

  @override
  String get appTagline => 'दैनिक कार्यबल आवंटन और संचालन प्रणाली';

  @override
  String get navDashboard => 'मुख्य पृष्ठ';

  @override
  String get navJobPostings => 'काम की सूची';

  @override
  String get navProfile => 'प्रोफ़ाइल';

  @override
  String get dashboardEmployerHeadline => 'आज आपको कौन सी दैनिक सेवा चाहिए?';

  @override
  String get dashboardWorkerHeadline => 'सक्रिय काम बहीखाता और सीधी भर्ती';

  @override
  String get dashboardEmployerSubhead =>
      '1,200+ स्थानीय दैनिक मजदूरी विशेषज्ञों से जुड़ें';

  @override
  String get dashboardWorkerSubhead => 'अपनी दर तय करें और नजदीकी काम देखें';

  @override
  String get dashboardEmployerSearchPlaceholder =>
      'खोजें \"पेंटिंग\", \"प्लंबिंग\"...';

  @override
  String get dashboardWorkerSearchPlaceholder =>
      'इंदिरानगर के पास काम खोजें...';

  @override
  String get dashboardEmployerBannerTitle => '100% आधार सत्यापित दैनिक कारिगर';

  @override
  String get dashboardWorkerBannerTitle => 'उसी दिन गारंटीकृत यूपीआई भुगतान';

  @override
  String get dashboardEmployerBannerSubhead =>
      'तुरंत प्रतिक्रिया के साथ सत्यापित कारिगर बुक करें';

  @override
  String get dashboardWorkerBannerSubhead =>
      'सत्यापित स्थानीय परिवारों से सीधा संबंध';

  @override
  String get postNewJobByCategory => 'श्रेणी के अनुसार नया काम पोस्ट करें';

  @override
  String get availableWorkCategories => 'उपलब्ध काम की श्रेणियां';

  @override
  String get postJobCta => '+ काम पोस्ट करें';

  @override
  String get categoriesCount => '6 श्रेणियां';

  @override
  String get categoryPainting => 'पेंटिंग';

  @override
  String get categoryCleaning => 'सफाई';

  @override
  String get categoryPlumbing => 'प्लंबिंग';

  @override
  String get categoryCooking => 'खाना बनाना';

  @override
  String get categoryGardening => 'बागवानी';

  @override
  String get categoryElectrical => 'बिजली काम';

  @override
  String get categoryCarpentry => 'लकड़ी का काम';

  @override
  String get categoryAll => 'सभी';

  @override
  String get badgeHighDemand => 'उच्च मांग';

  @override
  String get badgePopular => 'लोकप्रिय';

  @override
  String get badgeUrgent => 'आपातकालीन';

  @override
  String get badgeVerified => 'सत्यापित';

  @override
  String get badgePro => 'प्रो';

  @override
  String get roleEmployer => 'नियोक्ता';

  @override
  String get roleWorker => 'कारिगर';

  @override
  String get roleEmployerSubtitle => 'दैनिक काम के लिए कारिगर रखें';

  @override
  String get roleWorkerSubtitle => 'दैनिक काम खोजें और रोज कमाएं';

  @override
  String get authSignIn => 'साइन इन';

  @override
  String get authSignUp => 'साइन अप';

  @override
  String get authWelcomeBack => 'वापसी पर स्वागत है';

  @override
  String get authCreateAccount => 'खाता बनाएं';

  @override
  String get authEmailAuth => 'ईमेल';

  @override
  String get authMobileOtp => 'मोबाइल ओटीपी';

  @override
  String get authEmail => 'ईमेल पता';

  @override
  String get authPassword => 'पासवर्ड';

  @override
  String get authPhoneNumber => 'मोबाइल नंबर';

  @override
  String get authFullName => 'पूरा नाम';

  @override
  String get authStreetAddress => 'सड़क का पता';

  @override
  String get authLocality => 'इलाका / क्षेत्र';

  @override
  String get authCity => 'शहर';

  @override
  String get authSelectRole => 'अपनी भूमिका चुनें';

  @override
  String get authAlreadyHaveAccount => 'पहले से खाता है? साइन इन करें';

  @override
  String get authDontHaveAccount => 'खाता नहीं है? साइन अप करें';

  @override
  String get authSendOtpCta => 'ओटीपी भेजें और सत्यापित करें';

  @override
  String get authCreateAccountCta => 'खाता बनाएं और आगे बढ़ें';

  @override
  String get authSignInCta => 'कामसेतु में साइन इन करें';

  @override
  String get authHeadingSignIn => 'कामसेतु में साइन इन करें';

  @override
  String get authHeadingSignUp => 'खाता बनाएं';

  @override
  String get jobListingsTitle => 'सभी काम की सूची';

  @override
  String jobListingsCategoryTitle(String category) {
    return '$category के काम';
  }

  @override
  String get searchPlaceholderListings => 'शीर्षक, श्रेणी, स्थान खोजें...';

  @override
  String get filterButton => 'फ़िल्टर';

  @override
  String get statusAll => 'सभी';

  @override
  String get statusOpen => 'खुले काम';

  @override
  String get statusAssigned => 'आवंटित';

  @override
  String get statusCompleted => 'पूरे काम';

  @override
  String get statusCompletedFull => 'पूरा हुआ';

  @override
  String get perDay => 'प्रति दिन';

  @override
  String applicantsCount(int count) {
    return '$count आवेदक';
  }

  @override
  String get noListingsFound => 'फ़िल्टर से मेल खाता कोई काम नहीं मिला।';

  @override
  String get resetFilters => 'फ़िल्टर रीसेट करें';

  @override
  String get applyNow => 'आवेदन करें';

  @override
  String get splashModeEmployer => 'मुझे कारीगर चाहिए';

  @override
  String get splashModeWorker => 'मुझे काम चाहिए';

  @override
  String get splashWorkerHeadline => 'आस-पास के खुले दैनिक काम देखें';

  @override
  String get splashSignInToBrowse => 'ब्राउज़ करने के लिए साइन इन करें ->';

  @override
  String get statVerifiedPros => 'सत्यापित कारीगर';

  @override
  String get statAvgDailyRate => 'औसत दैनिक दर';

  @override
  String get statJobDispatch => 'काम का प्रेषण';

  @override
  String get splashFooterSecurity => 'सुरक्षित प्रणाली • आधार सत्यापित कारीगर';

  @override
  String get jobDetailTitle => 'काम का विवरण';

  @override
  String get jobOverviewSection => 'काम का अवलोकन';

  @override
  String get jobLocationSection => 'काम का स्थान';

  @override
  String get employerVerificationSection => 'नियोक्ता सत्यापन';

  @override
  String get applicantsAssignmentSection => 'आवेदक और नियुक्ति';

  @override
  String get stepPosted => 'पोस्ट हुआ';

  @override
  String get stepAssigned => 'नियुक्त हुआ';

  @override
  String get stepCompleted => 'पूरा हुआ';

  @override
  String get dailyWageLabel => 'दैनिक मजदूरी';

  @override
  String get postedDateLabel => 'पोस्ट की तारीख';

  @override
  String get categoryLabel => 'श्रेणी';

  @override
  String get urgencyLevelLabel => 'प्राथमिकता स्तर';

  @override
  String get aadhaarVerifiedEmployer => 'आधार सत्यापित नियोक्ता';

  @override
  String get applyForJobCta => 'इस काम के लिए आवेदन करें';

  @override
  String get alreadyApplied => 'आवेदन जमा है';

  @override
  String get assignWorkerCta => 'कारिगर नियुक्त करें';

  @override
  String get markCompletedCta => 'काम पूरा चिह्नित करें';

  @override
  String get rateWorkerCta => 'रेटिंग दें';

  @override
  String jobAssignedTo(String name) {
    return '$name को नियुक्त किया गया';
  }

  @override
  String get profileTitle => 'सिस्टम प्रोफ़ाइल और सेटिंग्स';

  @override
  String get verifiedUser => 'सत्यापित उपयोगकर्ता';

  @override
  String get verifiedEmployerBadge => 'सत्यापित नियोक्ता';

  @override
  String get verifiedWorkerBadge => 'सत्यापित कारिगर';

  @override
  String get trustAadhaar => 'आधार सत्यापित';

  @override
  String get trustBackground => 'पृष्ठभूमि जांच पूरी';

  @override
  String get trustSkill => 'कौशल प्रमाणित';

  @override
  String get languageSettingTitle => 'App Language / भाषा';

  @override
  String get english => 'English';

  @override
  String get hindi => 'हिंदी';

  @override
  String get activeSkillsTitle => 'सक्रिय कौशल और प्रमाणन';

  @override
  String get portfolioGalleryTitle => 'काम के नमूने और पोर्टफोलियो गैलरी';

  @override
  String get portfolioInstruction =>
      'पूर्ण चित्र देखने या पोर्टफोलियो अपडेट करने के लिए किसी भी फोटो पर टैप करें';

  @override
  String get addWorkPhoto => '+ काम का फोटो जोड़ें';

  @override
  String get reviewsSectionTitle => 'नियोक्ता समीक्षाएं और रेटिंग';

  @override
  String get noReviewsYet => 'अभी तक कोई समीक्षा नहीं';

  @override
  String get noReviewsSubtext =>
      'नियोक्ताओं से रेटिंग और समीक्षाएं प्राप्त करने के लिए काम पूरा करें।';

  @override
  String get ratingBreakdownSubtext =>
      'सत्यापित पूर्ण कार्यों पर आधारित रेटिंग का विवरण';

  @override
  String get primaryAddressTitle => 'प्राथमिक पता और स्थान';

  @override
  String get editAddress => 'पता बदलें';

  @override
  String get signOut => 'साइन आउट करें';

  @override
  String get notificationsTitle => 'सूचनाएं';

  @override
  String get markAllAsRead => 'सभी को पढ़ा हुआ चिह्नित करें';

  @override
  String get noNotifications => 'अभी कोई सूचना नहीं है';

  @override
  String get noNotificationsSubtext =>
      'सिस्टम अलर्ट और अपडेट यहां दिखाई देंगे।';

  @override
  String get recentSearches => 'हाल ही की खोजें';

  @override
  String get clearAll => 'सब साफ करें';

  @override
  String get searchResults => 'खोज परिणाम';

  @override
  String get noSearchResults => 'आपकी खोज से मेल खाता कोई काम नहीं मिला';

  @override
  String get postJobSheetTitle => 'नया काम पोस्ट करें';

  @override
  String get workCategoryLabel => 'काम की श्रेणी *';

  @override
  String get jobTitleLabel => 'काम का शीर्षक *';

  @override
  String get descriptionLabel => 'विवरण *';

  @override
  String get dailyWageInputLabel => 'दैनिक मजदूरी (₹) *';

  @override
  String get photoAttachmentLabel => 'फोटो संलग्नक';

  @override
  String get selectPhotoCta => 'फोटो चुनें';

  @override
  String get postJobNowCta => 'अभी काम पोस्ट करें';

  @override
  String get filterSheetTitle => 'फ़िल्टर और क्रमबद्ध करें';

  @override
  String get priceRangeLabel => 'मूल्य सीमा (दैनिक मजदूरी)';

  @override
  String get sortByLabel => 'क्रमबद्ध करें';

  @override
  String get categoriesLabel => 'श्रेणियां';

  @override
  String get sortMostRecent => 'नवीनतम';

  @override
  String get sortPriceLow => 'मजदूरी: कम से अधिक';

  @override
  String get sortPriceHigh => 'मजदूरी: अधिक से कम';

  @override
  String get sortRating => 'रेटिंग';

  @override
  String get sortUrgency => 'प्राथमिकता';

  @override
  String get applyFiltersCta => 'फ़िल्टर लागू करें';

  @override
  String get rateWorkerSheetTitle => 'कारिगर को रेटिंग दें और काम पूरा करें';

  @override
  String get rateWorkerSubtitle =>
      'कारिगर द्वारा किए गए काम की गुणवत्ता कैसी थी?';

  @override
  String get selectRatingLabel => 'रेटिंग चुनें (1 से 5 स्टार)';

  @override
  String get feedbackLabel => 'समीक्षा / टिप्पणी (वैकल्पिक)';

  @override
  String get submitReviewCta => 'समीक्षा जमा करें और काम बंद करें';

  @override
  String get updateAddressSheetTitle => 'प्राथमिक पता अपडेट करें';

  @override
  String get saveAddressCta => 'पता सहेजें';

  @override
  String get profileSystemReconfiguration => 'सिस्टम पुनर्गठन (कॉन्फ़िगरेशन)';

  @override
  String get profileViewSystemGallery => 'सिस्टम गैलरी और विजेट्स देखें';

  @override
  String get profileTogglePalette => 'डार्क/वार्म पैलेट टोकन बदलें';

  @override
  String get profileClearCache => 'कैश किया गया काम का डेटा साफ़ करें';

  @override
  String get profileAccountCompliance => 'खाता और अनुपालन';

  @override
  String get profileAadhaarDoc => 'आधार दस्तावेज (सत्यापित)';

  @override
  String get profileBankAccount => 'तुरंत UPI भुगतान के लिए बैंक खाता';

  @override
  String get profileSignOut => 'सत्र से बाहर निकलें (साइन आउट)';

  @override
  String get profileDispatchSpecs => 'कार्यबल प्रेषण विनिर्देश';

  @override
  String get profileExpectedDailyRate => 'अपेक्षित दैनिक दर';

  @override
  String get profileDispatchRadius => 'काम का दायरा (त्रिज्या)';

  @override
  String get profilePreferredShift => 'पसंदीदा शिफ्ट';

  @override
  String get profilePaymentMode => 'भुगतान का तरीका';

  @override
  String get profileEditSkills => 'कौशल संपादित करें ->';

  @override
  String get profileAddSample => '+ नमूना जोड़ें';

  @override
  String get statActivePostings => 'सक्रिय पोस्टिंग';

  @override
  String get statActivePostingsSubtext => '1 पेंटिंग, 1 प्लंबिंग';

  @override
  String get statApplications => 'आवेदन';

  @override
  String get statApplicationsSubtext => '4 सत्यापित कारीगर';

  @override
  String get statTotalDispatches => 'कुल कार्य';

  @override
  String get statTotalDispatchesSubtext => 'पूरे किए गए काम';

  @override
  String get statAvgDailyPayout => 'औसत दैनिक भुगतान';

  @override
  String get statAvgDailyPayoutSubtext => 'प्रति कारीगर';

  @override
  String get statDailyWageRate => 'दैनिक मजदूरी दर';

  @override
  String get statSetByEmployer => 'नियोक्ता द्वारा निर्धारित';

  @override
  String get statRatingScore => 'रेटिंग स्कोर';

  @override
  String get stat24Reviews => '24 समीक्षाएं';

  @override
  String get statJobsCompleted => 'पूरे किए गए काम';

  @override
  String get statOnTime => '100% समय पर';

  @override
  String get statApplicationsSent => 'भेजे गए आवेदन';

  @override
  String get statPendingReview => 'समीक्षा के अधीन';

  @override
  String get headerRecentDispatchLedger => 'हाल के काम का ब्योरा (लेज़र)';

  @override
  String get headerRecommendedJobsNearby => 'आस-पास अनुशंसित काम';

  @override
  String get linkViewAll => 'सभी देखें ->';

  @override
  String get headerDispatchMetricsOverview => 'काम और मेट्रिक्स अवलोकन';

  @override
  String get headerMyWorkParameters => 'मेरे काम के मानदंड';

  @override
  String get headerActiveDispatchOps => 'सक्रिय काम संचालन';

  @override
  String get headerDailyAvailStatus => 'दैनिक उपलब्धता स्थिति';

  @override
  String get subtextActiveDispatchOps =>
      'खुली पोस्टिंग पर आवेदन प्राप्त हो रहे हैं। अगला कार्य कल सुबह 09:00 बजे निर्धारित है।';

  @override
  String get subtextDailyAvailStatus =>
      'आपकी प्रोफ़ाइल स्थानीय कार्य पूल में सक्रिय है। पास के घर मालिक आपके कौशल प्रमाणपत्र देख सकते हैं।';

  @override
  String get statusPostingsActive => 'पोस्टिंग सक्रिय';

  @override
  String get statusAvailable => 'उपलब्ध';

  @override
  String get jobDetailTaskRequirements => 'कार्य और स्थल की आवश्यकताएं';

  @override
  String get jobDetailEmployerHeader => 'नियोक्ता और काम के मालिक';

  @override
  String get jobDetailApplicantBids => 'आवेदक बोलियां और रजिस्टर';

  @override
  String get jobDetailNoApps =>
      'अभी तक कोई आवेदन सबमिट नहीं किया गया है। आस-पास के कारीगर सीधे रुचि व्यक्त कर सकते हैं।';

  @override
  String get jobDetailAcceptCta => 'स्वीकार करें';
}
