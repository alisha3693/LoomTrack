import { useEffect, useState } from "react";

// Light is the theme. Dark is there for anyone who picks it with the toggle, and is remembered on that device.
// The choice is applied as data-theme on <html>; index.html applies it before first paint to avoid a flash.

export type ThemeChoice = "light" | "dark";
const KEY = "lt.theme.v2"; // a new key: everyone starts light, whatever an earlier version saved
const ORDER: ThemeChoice[] = ["light", "dark"];

function stored(): ThemeChoice {
  try {
    return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

function apply(choice: ThemeChoice) {
  document.documentElement.setAttribute("data-theme", choice);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", choice === "dark" ? "#0D0D11" : "#FFFFFF");
}

export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(stored);
  useEffect(() => {
    apply(choice);
    try {
      if (choice === "light") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, choice);
    } catch {
      /* private mode: choice lasts for this page only */
    }
  }, [choice]);
  const cycle = () => setChoice((c) => ORDER[(ORDER.indexOf(c) + 1) % ORDER.length]);
  return { choice, cycle };
}

const LABEL: Record<ThemeChoice, string> = { light: "Theme: light", dark: "Theme: dark" };

export function ThemeToggle() {
  const { choice, cycle } = useTheme();
  return (
    <button type="button" className="theme-toggle" onClick={cycle} title={LABEL[choice]} aria-label={`${LABEL[choice]}. Click to change.`}>
      {choice === "light" ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
        </svg>
      )}
    </button>
  );
}
