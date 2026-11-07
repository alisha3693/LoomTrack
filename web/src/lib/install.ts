import { useEffect, useState } from "react";

// Installing the app to the home screen.
// Android (Chrome, Edge, Samsung Internet) sends `beforeinstallprompt` once, early, so it is caught here at load and kept.
// iPhone and iPad have no install button: the person has to use Share, Add to Home Screen, so we only explain it.

interface InstallEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

let deferred: InstallEvent | null = null;
const listeners = new Set<() => void>();
const tell = () => listeners.forEach((l) => l());

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault(); // keep it for our own button
    deferred = e as InstallEvent;
    tell();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    tell();
  });
}

export type Platform = "ios" | "android" | "other";

export function platform(): Platform {
  const ua = navigator.userAgent;
  // iPadOS 13+ says it is a Mac, but has touch points.
  if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return "ios";
  if (/Android/.test(ua)) return "android";
  return "other";
}

/** True when the app is already running from the home screen. */
export function isInstalled(): boolean {
  return matchMedia("(display-mode: standalone)").matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
}

export function useInstall() {
  const [, bump] = useState(0);
  useEffect(() => {
    const l = () => bump((n) => n + 1);
    listeners.add(l);
    return () => void listeners.delete(l);
  }, []);
  return {
    installed: isInstalled(),
    platform: platform(),
    /** The browser is ready to show its own install dialog. */
    canPrompt: deferred !== null,
    /** Pages need https (or localhost) to be installable at all. */
    secure: window.isSecureContext,
    async prompt(): Promise<boolean> {
      if (!deferred) return false;
      const ev = deferred;
      deferred = null; // it can be used once
      await ev.prompt();
      const { outcome } = await ev.userChoice;
      tell();
      return outcome === "accepted";
    },
  };
}
