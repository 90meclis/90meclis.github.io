export function LogoMark({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" className="logo-mark">
      <defs>
        <linearGradient id="lm-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#D7FF3F" />
          <stop offset="1" stopColor="#2EE6A6" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="16" fill="#0E141C" stroke="url(#lm-g)" strokeWidth="3" />
      {/* orta saha çizgisi + yuvarlak masa */}
      <line x1="32" y1="8" x2="32" y2="56" stroke="#1F2A38" strokeWidth="2" />
      <circle cx="32" cy="32" r="17" fill="none" stroke="#1F2A38" strokeWidth="2" />
      <text x="32" y="41.5" textAnchor="middle" fontFamily="'Barlow Condensed', system-ui, sans-serif" fontWeight="800"
        fontSize="27" fill="url(#lm-g)" letterSpacing="-0.5">90</text>
      <circle cx="49" cy="15" r="3.2" fill="#D7FF3F" />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="logo">
      <LogoMark />
      <span className="logo-word">
        <span className="logo-90">90</span>
        <span className="logo-meclis">MECLİS</span>
      </span>
    </span>
  );
}
