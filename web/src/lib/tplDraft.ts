/** Unsaved plan-template work, kept in this browser so leaving the editor does not lose it. */
const PREFIX = "loomtrack.tplDraft.";

export interface Draft<R = unknown> {
  name: string;
  rows: R[];
  savedAt: string;
}

export interface DraftEntry extends Draft {
  scope: string; // "new", "copy-3" or "edit-7"
  path: string; // where the editor for this draft lives
}

export const scopeOf = (id: string | undefined, copyOf: string | null): string => (id ? `edit-${id}` : copyOf ? `copy-${copyOf}` : "new");

export function pathOf(scope: string): string {
  const [kind, n] = scope.split("-");
  return kind === "edit" ? `/m/templates/${n}` : kind === "copy" ? `/m/templates/new?copy=${n}` : "/m/templates/new";
}

export function readDraft<R>(scope: string): Draft<R> | null {
  try {
    const raw = localStorage.getItem(PREFIX + scope);
    return raw ? (JSON.parse(raw) as Draft<R>) : null;
  } catch {
    return null;
  }
}

export function writeDraft<R>(scope: string, name: string, rows: R[]): void {
  try {
    localStorage.setItem(PREFIX + scope, JSON.stringify({ name, rows, savedAt: new Date().toISOString() }));
  } catch {
    /* storage unavailable: the editor still works, it just cannot keep a draft */
  }
}

export function clearDraft(scope: string): void {
  try {
    localStorage.removeItem(PREFIX + scope);
  } catch {
    /* nothing to clear */
  }
}

export function listDrafts(): DraftEntry[] {
  const found: DraftEntry[] = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key?.startsWith(PREFIX)) continue;
      const scope = key.slice(PREFIX.length);
      const d = readDraft(scope);
      if (d) found.push({ ...d, scope, path: pathOf(scope) });
    }
  } catch {
    return [];
  }
  return found.sort((a, b) => b.savedAt.localeCompare(a.savedAt));
}
