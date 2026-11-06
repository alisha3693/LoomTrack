import { useCallback, useEffect, useState } from "react";

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

export function useLang(fallback: Lang = "ta") {
  const [lang, setLangState] = useState<Lang>(() => storedLang(fallback));
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(LANG_KEY, l);
    } catch {
      /* ignore */
    }
  }, []);
  const t = useCallback((k: StringKey) => STRINGS[k][lang], [lang]);
  return { lang, setLang, t };
}
