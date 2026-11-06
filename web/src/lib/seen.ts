// "New since you last looked": a per-browser memory of the newest thing each person has seen.
// It only decides whether to draw a dot, so losing it (private window, cleared data) costs nothing.

const KEY = (k: string) => `lt.seen.${k}`;

export function seenAt(k: string): string | null {
  try {
    return localStorage.getItem(KEY(k));
  } catch {
    return null;
  }
}

export function markSeen(k: string, at: string | null | undefined) {
  if (!at) return;
  try {
    const have = localStorage.getItem(KEY(k));
    if (!have || at > have) localStorage.setItem(KEY(k), at);
  } catch {
    /* ignore */
  }
}

/** True when `at` is newer than anything seen under `k`. A first visit counts as seen: nothing is "new" yet. */
export function isNew(k: string, at: string | null | undefined): boolean {
  if (!at) return false;
  const have = seenAt(k);
  return have !== null && at > have;
}

/** True when `at` is newer than anything seen under `k`, including when nothing has been seen at all. For replies that must not be missed. */
export function unseen(k: string, at: string | null | undefined): boolean {
  if (!at) return false;
  const have = seenAt(k);
  return have === null || at > have;
}
