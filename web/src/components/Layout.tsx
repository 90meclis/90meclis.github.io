import { SealNavLink } from "./SealBadge";
import { InstallPrompt } from "./InstallPrompt";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Logo } from "./Logo";
import { Disclaimer } from "./ui";
import { NAV } from "../lib/nav";
import { systemStatus } from "../lib/data";


export function Layout() {
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    setOpen(false);
    window.scrollTo({ top: 0 });
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [loc.pathname]);

  return (
    <div className="shell">
      <a href="#main" className="skip">İçeriğe geç</a>
      <header className="topbar">
        <div className="wrap topbar-in">
          <Link to="/" className="brand" aria-label="90 Meclis ana sayfa"><Logo /></Link>
          <nav className="nav-desktop" aria-label="Ana menü">
            {NAV.map((n) => <NavLink key={n.to} to={n.to} className="navlink">{n.label}</NavLink>)}
          </nav>
          <button className="menu-btn" aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen((o) => !o)}>
            <span className="sr-only">Menü</span>
            <span className={`burger ${open ? "x" : ""}`} aria-hidden="true"><i /><i /><i /></span>
          </button>
        </div>
        <nav id="mobile-nav" className={`nav-mobile ${open ? "open" : ""}`} aria-label="Mobil menü">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className="m-navlink"><span aria-hidden="true">{n.icon}</span>{n.label}</NavLink>
          ))}
          <NavLink to="/hakkinda" className="m-navlink"><span aria-hidden="true">ⓘ</span>Yöntem ve Sorumlu Oyun</NavLink>
        </nav>
      </header>
      <nav className="tabbar" aria-label="Hızlı erişim">
        {NAV.slice(0, 4).map((n) => (
          <NavLink key={n.to} to={n.to} className="tab"><span aria-hidden="true">{n.icon}</span>{n.short}</NavLink>
        ))}
        <NavLink to="/gundem-masasi" className="tab"><span aria-hidden="true">◉</span>Gündem</NavLink>
      </nav>
      <main id="main" tabIndex={-1} className="wrap main">
        <Outlet />
      </main>
      <InstallPrompt />
      <footer className="footer">
        <div className="wrap footer-in">
          <div>
            <Logo />
            <p className="muted small">Her şey tek masada. Kayıtlar maçtan önce kilitlenir; kazanç da kayıp da herkesin önünde.</p>
          </div>
          <nav className="footer-nav" aria-label="Alt menü">
            {NAV.map((n) => <Link key={n.to} to={n.to}>{n.label}</Link>)}
            <Link to="/hakkinda">Yöntem ve Sorumlu Oyun</Link>
            <SealNavLink />
          </nav>
          <Disclaimer />
          <SystemPulse />
          <p className="muted tiny">Saatler Türkiye saatiyle (TSİ) gösterilir. Veriler açık kaynaklardan derlenir; haberlerin hakları yayıncılarına aittir. © {new Date().getFullYear()} 90 Meclis</p>
        </div>
      </footer>
    </div>
  );
}


function SystemPulse() {
  const [st, setSt] = useState<{ ok: boolean; at: string | null } | null>(null);
  useEffect(() => {
    systemStatus().then((rows) => {
      const y = rows.find((r) => r.is_adi === "yayin");
      if (y) setSt({ ok: !rows.some((r) => r.gecikti), at: y.son_basari });
    }).catch(() => undefined);
  }, []);
  if (!st || !st.at) return null;
  const t = new Date(st.at).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  return <p className="muted tiny sys-pulse"><span className={st.ok ? "dot ok" : "dot warn"} aria-hidden="true" /> Bülten son güncelleme: {t} TSİ{st.ok ? "" : " · bazı işler gecikmeli"}</p>;
}
