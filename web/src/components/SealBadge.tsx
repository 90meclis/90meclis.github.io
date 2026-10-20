import { Link } from "react-router-dom";
import { sealIndex } from "../lib/seal";
import { useAsync } from "../lib/useAsync";

/** Kayıt mühürlüyse "🔏 Mühürlü #n" rozeti (doğrulama sayfasına gider); mühür yoksa hiçbir şey. */
export function SealBadge({ id }: { id: string }) {
  const q = useAsync("seal:idx", sealIndex, []);
  const s = q.data?.get(id);
  if (!s) return null;
  return <Link to={`/kanit-muhru?id=${encodeURIComponent(id)}`} className="seal-b" title={`Kanıt Mührü #${s.seq} · ${s.sha256}`}>🔏 Mühürlü #{s.seq}</Link>;
}

/** Alt menü bağlantısı: yalnızca mühürlü kayıt varsa görünür. */
export function SealNavLink() {
  const q = useAsync("seal:idx", sealIndex, []);
  if (!q.data?.size) return null;
  return <Link to="/kanit-muhru">Kanıt Mührü · doğrula</Link>;
}
