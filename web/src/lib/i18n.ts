import { useCallback, useEffect, useSyncExternalStore } from "react";

// Supervisor-facing strings. Office screens are English (the office team
// works in English with buyers); the floor works in Tamil by default.

const STRINGS = {
  signIn: { ta: "உள்நுழை", en: "Sign in" },
  loginLabel: { ta: "தொலைபேசி எண் / மின்னஞ்சல்", en: "Phone or email" },
  secretLabel: { ta: "PIN / கடவுச்சொல்", en: "PIN or password" },
  myOrders: { ta: "என் ஆர்டர்கள்", en: "My orders" },
  todayEntered: { ta: "இன்று பதிவு", en: "Today" },
  notYet: { ta: "இன்னும் இல்லை", en: "Not yet" },
  done: { ta: "முடிந்தது", en: "Done" },
  waitingOffice: { ta: "அலுவலகம் இவற்றை முடித்ததாகக் குறிக்கக் காத்திருக்கிறது", en: "Waiting for the office to mark done" },
  target: { ta: "இன்றைய இலக்கு", en: "Target today" },
  leftToday: { ta: "இன்று மீதம்", en: "Left to do today" },
  targetDone: { ta: "இன்றைய இலக்கு முடிந்தது", en: "Today's target done" },
  perDay: { ta: "ஒரு நாளுக்கு", en: "a day" },
  readyFrom: { ta: "தயார்", en: "ready from" },
  waitingFor: { ta: "முந்தைய நிலை முடிய காத்திருக்கிறது", en: "waiting for the stage before" },
  notMoreThanBefore: { ta: "முந்தைய நிலையில் முடிந்ததை விட அதிகம் பதிவு செய்ய முடியாது", en: "More than the stage before has finished" },
  dueBy: { ta: "முடிக்க வேண்டியது", en: "Due" },
  todayQty: { ta: "இன்று எத்தனை பீஸ்?", en: "Pieces today" },
  photo: { ta: "புகைப்படம்", en: "Photo" },
  files: { ta: "இந்த ஆர்டருக்கான கோப்புகள்", en: "Files for this order" },
  takePhoto: { ta: "படம் எடு", en: "Take photo" },
  retake: { ta: "மீண்டும் எடு", en: "Retake" },
  issue: { ta: "பிரச்சனை ஏதாவது?", en: "Any issue?" },
  issuePlaceholder: { ta: "எழுதுங்கள் அல்லது மைக் அழுத்தி பேசுங்கள்", en: "Type, or press the mic and speak" },
  record: { ta: "பேசு", en: "Speak" },
  stop: { ta: "நிறுத்து", en: "Stop" },
  voiceSaved: { ta: "குரல் பதிவு சேர்க்கப்பட்டது", en: "Voice note attached" },
  remove: { ta: "நீக்கு", en: "Remove" },
  send: { ta: "அனுப்பு", en: "Send" },
  sent: { ta: "அனுப்பப்பட்டது", en: "Sent" },
  queued: { ta: "சேமிக்கப்பட்டது. இணையம் வந்ததும் அனுப்பப்படும்.", en: "Saved. It will send when the network is back." },
  waiting: { ta: "அனுப்பக் காத்திருக்கிறது", en: "waiting to send" },
  failed: { ta: "அனுப்ப முடியவில்லை", en: "could not send" },
  offline: { ta: "இணையம் இல்லை", en: "Offline" },
  back: { ta: "பின்", en: "Back" },
  signOut: { ta: "வெளியேறு", en: "Sign out" },
  nothingToday: { ta: "இன்று பதிவு செய்ய ஆர்டர் இல்லை", en: "No orders to update" },
  of: { ta: "/", en: "of" },
  workDate: { ta: "தேதி", en: "Date" },
  enterQty: { ta: "அளவை உள்ளிடவும்", en: "Enter a quantity" },
  tooMany: { ta: "ஆர்டர் அளவை விட அதிகம்", en: "More than the order quantity" },
  discard: { ta: "நீக்கு", en: "Discard" },
  lastSync: { ta: "கடைசியாகப் புதுப்பித்தது", en: "Last updated" },
  // Installing the app, and the first-time welcome
  installTitle: { ta: "உங்கள் ஃபோனில் LoomTrack நிறுவுங்கள்", en: "Put LoomTrack on your phone" },
  installBody: { ta: "முகப்புத் திரையில் ஐகான் வரும். இணையம் இல்லாவிட்டாலும் திறக்கும்.", en: "An icon is added to your home screen. It opens even without internet." },
  installButton: { ta: "நிறுவு", en: "Install" },
  later: { ta: "பிறகு", en: "Later" },
  howTo: { ta: "எப்படி?", en: "How?" },
  installedTitle: { ta: "செயலி நிறுவப்பட்டுவிட்டது", en: "The app is installed" },
  installedBody: { ta: "இனி முகப்புத் திரையில் உள்ள LoomTrack ஐகானை அழுத்தவும்.", en: "From now on, tap the LoomTrack icon on your home screen." },
  openApp: { ta: "செயலியைத் திற", en: "Open the app" },
  continueInBrowser: { ta: "நிறுவாமல் தொடர்க", en: "Continue without installing" },
  iosStep1: { ta: "Safari-யில் கீழே உள்ள பகிர் (Share) பொத்தானை அழுத்தவும்", en: "In Safari, tap the Share button at the bottom" },
  iosStep2: { ta: "“Add to Home Screen” ஐத் தேர்ந்தெடுக்கவும்", en: "Choose “Add to Home Screen”" },
  iosStep3: { ta: "“Add” அழுத்தவும்", en: "Tap “Add”" },
  iosSafari: { ta: "iPhone-இல் இது Safari-யில் மட்டுமே வேலை செய்யும்.", en: "On an iPhone this only works in Safari." },
  androidStep1: { ta: "Chrome-இன் மெனுவை (⋮) திறக்கவும்", en: "Open the Chrome menu (⋮)" },
  androidStep2: { ta: "“Install app” அல்லது “Add to Home screen” ஐ அழுத்தவும்", en: "Tap “Install app” or “Add to Home screen”" },
  androidStep3: { ta: "“Install” அழுத்தவும்", en: "Tap “Install”" },
  welcomeTitle: { ta: "வணக்கம்! LoomTrack-ஐ இப்படிப் பயன்படுத்துங்கள்", en: "Welcome. How to use LoomTrack" },
  welcome1: { ta: "தினமும் உங்கள் ஆர்டரைத் திறந்து, இன்று எத்தனை பீஸ் முடிந்தது என்று பதிவு செய்யுங்கள்.", en: "Each day, open your order and enter how many pieces were done." },
  welcome2: { ta: "படம் எடுக்கும்போதும் பேசும்போதும் ஃபோன் கேமரா, மைக் அனுமதி கேட்கும். “Allow” அழுத்தவும்.", en: "When you take a photo or speak, the phone asks for the camera and microphone. Tap Allow." },
  welcome3: { ta: "இணையம் இல்லாவிட்டாலும் பதிவு செய்யலாம். இணையம் வந்ததும் தானாக அனுப்பப்படும்.", en: "No internet? Enter it anyway. It is sent when the network is back." },
  gotIt: { ta: "புரிந்தது", en: "Got it" },
} as const;

export type Lang = "ta" | "en";
export type StringKey = keyof typeof STRINGS;

const LANG_KEY = "lt.lang";

function storedLang(fallback: Lang): Lang {
  try {
    const v = localStorage.getItem(LANG_KEY);
    return v === "ta" || v === "en" ? v : fallback;
  } catch {
    return fallback;
  }
}

// One language for the whole app: every component that calls useLang follows the same choice, so switching it in
// the header changes the welcome card, the install offer and the order list together.
let chosen: Lang | null = null;
const listeners = new Set<() => void>();
const subscribe = (fn: () => void) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};

export function useLang(fallback: Lang = "ta") {
  const lang = useSyncExternalStore(subscribe, () => chosen ?? storedLang(fallback));
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = useCallback((l: Lang) => {
    chosen = l;
    try {
      localStorage.setItem(LANG_KEY, l);
    } catch {
      /* ignore */
    }
    listeners.forEach((fn) => fn());
  }, []);
  const t = useCallback((k: StringKey) => STRINGS[k][lang], [lang]);
  return { lang, setLang, t };
}
