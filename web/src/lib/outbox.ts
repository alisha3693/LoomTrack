// Offline outbox for supervisor updates. Every update is written to
// IndexedDB first, then sent. The id is generated here, so a retry after a
// dropped connection can never double-count pieces: the server ignores an id
// it already has.


export interface OutboxItem {
  id: string;
  milestoneId: number;
  workDate: string;
  qty: number;
  noteText: string;
  noteSource?: "text" | "voice";
  createdAt: string;
  photo?: Blob;
  audio?: Blob;
  /** Display only, so the queue can be shown without the network. */
  label: string;
  /** Set when the server refused it (not a network failure). */
  error?: string;
}

const DB_NAME = "loomtrack";
const STORE = "outbox";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const req = fn(db.transaction(STORE, mode).objectStore(STORE));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export const outbox = {
  put: (item: OutboxItem) => tx("readwrite", (s) => s.put(item)),
  remove: (id: string) => tx("readwrite", (s) => s.delete(id)),
  all: () => tx<OutboxItem[]>("readonly", (s) => s.getAll() as IDBRequest<OutboxItem[]>),
};

export function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

const listeners = new Set<() => void>();
export function onOutboxChange(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
const notify = () => listeners.forEach((fn) => fn());

let flushing: Promise<void> | null = null;

/** Send everything queued. Stops at the first network failure; keeps refused items with their error. */
export function flushOutbox(): Promise<void> {
  flushing ??= (async () => {
    try {
      const items = (await outbox.all()).filter((i) => !i.error).sort((a, b) => a.createdAt.localeCompare(b.createdAt));
      for (const item of items) {
        const form = new FormData();
        form.set("id", item.id);
        form.set("milestoneId", String(item.milestoneId));
        form.set("workDate", item.workDate);
        form.set("qty", String(item.qty));
        form.set("noteText", item.noteText);
        if (item.noteSource) form.set("noteSource", item.noteSource);
        form.set("createdAt", item.createdAt);
        if (item.photo) form.set("photo", item.photo, "photo.jpg");
        if (item.audio) form.set("audio", item.audio, `voice.${item.audio.type.includes("ogg") ? "ogg" : item.audio.type.includes("mp4") ? "m4a" : "webm"}`);

        let res: Response;
        try {
          res = await fetch("/api/s/updates", { method: "POST", body: form, credentials: "same-origin" });
        } catch {
          return; // network down: try again later
        }
        if (res.ok) {
          await outbox.remove(item.id);
        } else if (res.status === 401 || res.status === 408 || res.status === 429 || res.status >= 500) {
          return; // temporary: keep and retry
        } else {
          const data = await res.json().catch(() => ({}));
          await outbox.put({ ...item, error: data.error ?? `Error ${res.status}` });
        }
        notify();
      }
    } finally {
      flushing = null;
      notify();
    }
  })();
  return flushing;
}

let started = false;
/** Retry on reconnect, when the app comes back to the foreground, and every 30 s. */
export function startOutboxSync() {
  if (started) return;
  started = true;
  window.addEventListener("online", () => void flushOutbox());
  document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && void flushOutbox());
  setInterval(() => navigator.onLine && void flushOutbox(), 30_000);
  void flushOutbox();
}
