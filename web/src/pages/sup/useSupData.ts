// Supervisor data that survives a dead network: the last stage list is kept
// in localStorage, and anything still in the outbox is added on top so the
// numbers on screen match what the supervisor has entered.

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { flushOutbox, onOutboxChange, outbox, OutboxItem, startOutboxSync } from "../../lib/outbox";
import type { SupStage } from "../../lib/types";

const CACHE_KEY = "lt.sup.stages";

interface Cached {
  today: string;
  stages: SupStage[];
  at: string;
}

function readCache(): Cached | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? (JSON.parse(raw) as Cached) : null;
  } catch {
    return null;
  }
}

function writeCache(c: Cached) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(c));
  } catch {
    /* storage full or blocked: fine, we just won't have an offline copy */
  }
}

export function useSupData() {
  const [data, setData] = useState<Cached | null>(readCache);
  const [queue, setQueue] = useState<OutboxItem[]>([]);
  const [online, setOnline] = useState(navigator.onLine);

  const refreshQueue = useCallback(() => outbox.all().then(setQueue).catch(() => setQueue([])), []);

  const refresh = useCallback(async () => {
    try {
      const r = await api<{ today: string; stages: SupStage[] }>("/api/s/orders");
      const c = { ...r, at: new Date().toISOString() };
      writeCache(c);
      setData(c);
      setOnline(true);
    } catch (e) {
      // The phone's own "online" flag is wrong on Wi-Fi with no internet, which is common on a floor.
      // A request that could not reach the server at all is the better sign. Keep showing the cached list.
      if (e instanceof TypeError) setOnline(false);
    }
  }, []);

  useEffect(() => {
    startOutboxSync();
    void refreshQueue();
    void refresh();
    const off = onOutboxChange(() => {
      void refreshQueue();
      void refresh();
    });
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      off();
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, [refresh, refreshQueue]);

  /** Pieces for a stage that are queued but not yet on the server. */
  const queuedQty = (milestoneId: number, workDate?: string) =>
    queue.filter((q) => q.milestoneId === milestoneId && !q.error && (!workDate || q.workDate === workDate)).reduce((a, q) => a + q.qty, 0);

  return { data, queue, online, queuedQty, refresh, refreshQueue, flush: flushOutbox };
}
