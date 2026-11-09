import { ReactNode } from "react";

/** The one page width. Every home section sits in it, so edges line up top to bottom. */
export function Container({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`h-container ${className}`}>{children}</div>;
}

/** A section heading: small label across the top, the title on the left and the lede on the right. */
export function Head({ eyebrow, title, lede }: { eyebrow: string; title: string; lede: string }) {
  return (
    <header className="h-head">
      <p className="h-mono h-span-all">{eyebrow}</p>
      <h2>{title}</h2>
      <p className="h-lede">{lede}</p>
    </header>
  );
}

/** A row of knit stitches, the first `pct` percent filled in. Progress drawn as fabric. */
export function Stitches({ count, pct }: { count: number; pct: number }) {
  const filled = Math.round((count * pct) / 100);
  return (
    <div className="h-sts" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => <i key={i} className={i < filled ? "on" : ""} />)}
    </div>
  );
}

const WAVE = [8, 14, 22, 12, 26, 18, 10, 24, 16, 28, 12, 20, 8, 22, 14, 26, 10, 18, 24, 12, 20, 28, 14, 8, 22, 16, 10, 24, 12, 8];

/** The shape of a voice note. */
export function Waveform() {
  return <div className="h-wave" aria-hidden="true">{WAVE.map((h, i) => <i key={i} style={{ height: h }} />)}</div>;
}

export type SampleOrder = {
  po: string; style: string; stage: string; pct: number; due: string;
  tone: "green" | "amber" | "red";
};

// Sample orders used by the product pictures on this page.
export const ORDERS: SampleOrder[] = [
  { po: "B-PO-88240", style: "Men's polo, white", stage: "Stitching", pct: 38, due: "Sat 14 Nov", tone: "red" },
  { po: "B-PO-88213", style: "Crew neck tee, navy", stage: "Stitching", pct: 57, due: "Fri 20 Nov", tone: "green" },
  { po: "C-PO-0488", style: "Kids printed tee", stage: "Printing", pct: 31, due: "Sat 28 Nov", tone: "amber" },
];
