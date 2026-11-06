import { useEffect } from "react";

/** Something changed that the sidebar's counts depend on (a conversation was read, an approval decided). */
export function refreshBadges() {
  window.dispatchEvent(new Event("lt:badges"));
}

/** Call `reload` whenever the counts may have changed. */
export function useBadgeRefresh(reload: () => void) {
  useEffect(() => {
    window.addEventListener("lt:badges", reload);
    return () => window.removeEventListener("lt:badges", reload);
  }, [reload]);
}
