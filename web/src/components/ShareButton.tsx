import { useState } from "react";
import { shareBlob } from "../lib/share";

/** "Kartı paylaş": PNG üretir; Web Share destekliyse paylaşır, değilse indirir. Kaybeden kararlar da aynı kartla. */
export function ShareButton({ make, name, text }: { make: () => Promise<Blob>; name: string; text: string }) {
  const [busy, setBusy] = useState(false);
  return (
    <button type="button" className="share-btn" disabled={busy} onClick={async (e) => {
      e.preventDefault(); e.stopPropagation(); setBusy(true);
      try { await shareBlob(await make(), name, text); } finally { setBusy(false); }
    }}>{busy ? "Kart hazırlanıyor…" : "↗ Kartı paylaş"}</button>
  );
}
