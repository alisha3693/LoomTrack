import { ReactNode, useEffect, useState } from "react";

export interface Anchor {
  id: string;
  label: string;
  badge?: ReactNode;
}

/** A sticky strip that jumps to the sections of a long page and shows which one is on screen. */
export default function AnchorNav({ items }: { items: Anchor[] }) {
  const [active, setActive] = useState(items[0]?.id ?? "");

  useEffect(() => {
    const seen = new Map<string, number>();
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) seen.set(e.target.id, e.isIntersecting ? e.boundingClientRect.top : Infinity);
        const visible = [...seen.entries()].filter(([, top]) => top !== Infinity).sort((a, b) => a[1] - b[1]);
        if (visible[0]) setActive(visible[0][0]);
      },
      { rootMargin: "-110px 0px -60% 0px" },
    );
    for (const a of items) {
      const el = document.getElementById(a.id);
      if (el) io.observe(el);
    }
    return () => io.disconnect();
  }, [items.map((i) => i.id).join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <nav className="anchor-nav no-print" aria-label="Sections on this page">
      {items.map((a) => (
        <a
          key={a.id} href={`#${a.id}`} aria-current={active === a.id}
          onClick={(e) => {
            e.preventDefault();
            document.getElementById(a.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
            setActive(a.id);
          }}
        >
          {a.label}{a.badge}
        </a>
      ))}
    </nav>
  );
}
