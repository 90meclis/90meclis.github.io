import { useEffect, useState } from "react";

type BIP = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
const KEY = "90m-install-dismissed";

/** Tarayıcı "ana ekrana ekle" teklif ettiğinde (Android/Chrome) ince bir şerit; reddedilirse 30 gün sorulmaz. */
export function InstallPrompt() {
  const [ev, setEv] = useState<BIP | null>(null);
  useEffect(() => {
    const until = Number(localStorage.getItem(KEY) ?? 0);
    if (until > Date.now()) return;
    const on = (e: Event) => { e.preventDefault(); setEv(e as BIP); };
    window.addEventListener("beforeinstallprompt", on);
    const done = () => setEv(null);
    window.addEventListener("appinstalled", done);
    return () => { window.removeEventListener("beforeinstallprompt", on); window.removeEventListener("appinstalled", done); };
  }, []);
  if (!ev) return null;
  const close = () => { localStorage.setItem(KEY, String(Date.now() + 30 * 864e5)); setEv(null); };
  return (
    <div className="install" role="dialog" aria-label="Uygulamayı yükle">
      <img src={`${import.meta.env.BASE_URL}icon-192.png`} alt="" width={36} height={36} />
      <div><b>90 Meclis'i ana ekrana ekle</b><small>Günün Kararı tek dokunuşla, uygulama gibi.</small></div>
      <button className="btn primary" style={{ padding: "8px 14px" }} onClick={async () => { await ev.prompt(); await ev.userChoice; setEv(null); }}>Yükle</button>
      <button className="install-x" aria-label="Kapat" onClick={close}>×</button>
    </div>
  );
}
