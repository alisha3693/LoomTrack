import { ReactNode } from "react";
import { Lang } from "../../lib/i18n";
import { ThemeToggle } from "../../lib/theme";

export function SupHeader({ title, sub, lang, setLang, left, right }: {
  title: string; sub?: string; lang: Lang; setLang: (l: Lang) => void; left?: ReactNode; right?: ReactNode;
}) {
  return (
    <header className="phone-top">
      {left}
      <div className="who">
        <b>{title}</b>
        {sub && <span className="faint small">{sub}</span>}
      </div>
      {right}
      <ThemeToggle />
      <div className="lang-toggle" role="group" aria-label="Language">
        <button aria-pressed={lang === "ta"} onClick={() => setLang("ta")}>தமிழ்</button>
        <button aria-pressed={lang === "en"} onClick={() => setLang("en")}>EN</button>
      </div>
    </header>
  );
}
