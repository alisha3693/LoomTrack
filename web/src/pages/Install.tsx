import { useState } from "react";
import { Link } from "react-router-dom";
import { useLang } from "../lib/i18n";
import { useInstall } from "../lib/install";

const DISMISSED = "lt.install.dismissed";

function dismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED) === "1";
  } catch {
    return false;
  }
}

/** The page a supervisor is sent to once: one clear thing to do, in Tamil first. */
export default function Install() {
  const { lang, setLang, t } = useLang("ta");
  const i = useInstall();
  const [declined, setDeclined] = useState(false);

  return (
    <main className="login-wrap">
      <div className="login stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="brand">
            <img src="/icon.svg" alt="" />
            LoomTrack
          </div>
          <div className="lang-toggle" role="group" aria-label="Language">
            <button type="button" aria-pressed={lang === "ta"} onClick={() => setLang("ta")}>தமிழ்</button>
            <button type="button" aria-pressed={lang === "en"} onClick={() => setLang("en")}>English</button>
          </div>
        </div>

        <section className="card card-pad stack">
          <h1>{i.installed ? t("installedTitle") : t("installTitle")}</h1>
          <p className="muted" style={{ margin: 0 }}>{i.installed ? t("installedBody") : t("installBody")}</p>

          {i.installed && <Link className="btn btn-primary btn-lg btn-block" to="/login">{t("openApp")}</Link>}

          {!i.installed && !i.secure && (
            <p className="banner banner-warn" role="alert" style={{ margin: 0 }}>
              This page is not on a secure (https) address, so the phone will not offer to install it. Open the https address instead.
            </p>
          )}

          {!i.installed && i.secure && i.canPrompt && !declined && (
            <button
              className="btn btn-primary btn-lg btn-block"
              onClick={async () => {
                if (!(await i.prompt())) setDeclined(true);
              }}
            >
              {t("installButton")}
            </button>
          )}

          {!i.installed && i.secure && (!i.canPrompt || declined) && (
            <ol className="install-steps">
              {i.platform === "ios" ? (
                <>
                  <li>{t("iosStep1")}</li>
                  <li>{t("iosStep2")}</li>
                  <li>{t("iosStep3")}</li>
                </>
              ) : (
                <>
                  <li>{t("androidStep1")}</li>
                  <li>{t("androidStep2")}</li>
                  <li>{t("androidStep3")}</li>
                </>
              )}
            </ol>
          )}

          {!i.installed && i.platform === "ios" && i.secure && <p className="faint small" style={{ margin: 0 }}>{t("iosSafari")}</p>}
        </section>

        <p style={{ textAlign: "center", margin: 0 }}>
          <Link to="/login" className="small">{t("continueInBrowser")}</Link>
        </p>
      </div>
    </main>
  );
}

/** A quiet one-line offer at the top of the supervisor's home, until it is installed or sent away. */
export function InstallBanner() {
  const { t } = useLang("ta");
  const i = useInstall();
  const [hidden, setHidden] = useState(dismissed);
  if (i.installed || hidden || !i.secure || !(i.canPrompt || i.platform === "ios")) return null;

  const later = () => {
    try {
      localStorage.setItem(DISMISSED, "1");
    } catch {
      /* ignore */
    }
    setHidden(true);
  };
  return (
    <div className="card card-pad install-banner">
      <div style={{ minWidth: 0 }}>
        <b>{t("installTitle")}</b>
        <div className="faint small">{t("installBody")}</div>
      </div>
      <div className="row" style={{ flexWrap: "nowrap", gap: 6 }}>
        {i.canPrompt ? (
          <button className="btn btn-primary btn-sm" onClick={() => void i.prompt()}>{t("installButton")}</button>
        ) : (
          <Link className="btn btn-primary btn-sm" to="/install">{t("howTo")}</Link>
        )}
        <button className="btn btn-ghost btn-sm" onClick={later}>{t("later")}</button>
      </div>
    </div>
  );
}
