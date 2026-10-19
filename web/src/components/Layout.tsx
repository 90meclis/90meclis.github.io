import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Logo } from "./Logo";
import { Disclaimer } from "./ui";

export const NAV = [
  { to: "/mac-merkezi", label: "Maç Merkezi", icon: "◎" },
  { to: "/tahmin-botu", label: "Tahmin Botu", icon: "◆" },
  { to: "/tahmin-arsivi", label: "Tahmin Arşivi", icon: "▤" },
  { to: "/guven-panosu", label: "Güven Panosu", icon: "◈" },
  { to: "/gundem-masasi", label: "Gündem Masası", icon: "◉" },
  { to: "/veri-laboratuvari", label: "Veri Laboratuvarı", icon: "▦" },
];

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
          <NavLink key={n.to} to={n.to} className="tab"><span aria-hidden="true">{n.icon}</span>{n.label.split(" ")[0]}</NavLink>
        ))}
        <NavLink to="/gundem-masasi" className="tab"><span aria-hidden="true">◉</span>Gündem</NavLink>
      </nav>
      <main id="main" tabIndex={-1} className="wrap main">
        <Outlet />
      </main>
      <footer className="footer">
        <div className="wrap footer-in">
          <div>
            <Logo />
            <p className="muted small">Her şey tek masada. Kayıtlar maçtan önce kilitlenir; kazanç da kayıp da herkesin önünde.</p>
          </div>
          <nav className="footer-nav" aria-label="Alt menü">
            {NAV.map((n) => <Link key={n.to} to={n.to}>{n.label}</Link>)}
            <Link to="/hakkinda">Yöntem ve Sorumlu Oyun</Link>
          </nav>
          <Disclaimer />
          <p className="muted tiny">Saatler Türkiye saatiyle (TSİ) gösterilir. Veriler açık kaynaklardan derlenir; haberlerin hakları yayıncılarına aittir. © {new Date().getFullYear()} 90 Meclis</p>
        </div>
      </footer>
    </div>
  );
}
