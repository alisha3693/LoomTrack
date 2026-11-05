import { useEffect, useState } from "react";

// "system" follows the device; "light"/"dark" pin it. The choice is applied as
// data-theme on <html>; index.html applies it before first paint to avoid a flash.

export type ThemeChoice = "system" | "light" | "dark";
const KEY = "lt.theme";
const ORDER: ThemeChoice[] = ["system", "light", "dark"];

function stored(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function apply(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
  const dark = choice === "dark" || (choice === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#1b1b19" : "#ffffff");
}

export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(stored);
  useEffect(() => {
    apply(choice);
    try {
      if (choice === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, choice);
    } catch {
      /* private mode: choice lasts for this page only */
    }
    if (choice !== "system") return;
    // Keep the browser bar colour right if the device switches while the app is open.
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => apply("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [choice]);
  const cycle = () => setChoice((c) => ORDER[(ORDER.indexOf(c) + 1) % ORDER.length]);
  return { choice, cycle };
}

const LABEL: Record<ThemeChoice, string> = { system: "Theme: follows device", light: "Theme: light", dark: "Theme: dark" };

export function ThemeToggle() {
  const { choice, cycle } = useTheme();
  return (
    <button type="button" className="theme-toggle" onClick={cycle} title={LABEL[choice]} aria-label={`${LABEL[choice]}. Click to change.`}>
      {choice === "light" ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : choice === "dark" ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="12" cy="12" r="8" />
          <path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" />
        </svg>
      )}
    </button>
  );
}
