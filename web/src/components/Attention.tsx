import { ReactNode } from "react";
import { Link } from "react-router-dom";

export interface AttentionItem {
  key: string;
  tone: "red" | "amber" | "blue" | "green";
  title: string;
  detail?: ReactNode;
  cta?: string;
  /** Either a place to go... */
  to?: string;
  /** ...or something to do on this page. */
  onSelect?: () => void;
}

/** What needs this person's attention, as cards that go straight to it. Nothing to do is a good answer, said plainly. */
export default function Attention({ items, clear }: { items: AttentionItem[]; clear: string }) {
  if (items.length === 0) {
    return (
      <div className="allclear" role="status">
        <span className="check done">✓</span>
        <span>{clear}</span>
      </div>
    );
  }
  return (
    <div className="attention">
      {items.map((i) => {
        const inner = (
          <>
            <b>{i.title}</b>
            {i.detail && <span className="detail">{i.detail}</span>}
            <span className="cta">{i.cta ?? "Open"} →</span>
          </>
        );
        return i.to ? (
          <Link key={i.key} to={i.to} className={`attn ${i.tone}`}>{inner}</Link>
        ) : (
          <button key={i.key} type="button" className={`attn ${i.tone}`} onClick={i.onSelect}>{inner}</button>
        );
      })}
    </div>
  );
}
