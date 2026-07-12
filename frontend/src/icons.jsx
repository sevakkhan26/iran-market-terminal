// Inline SVG icon set (Lucide-style paths) — consistent stroke iconography,
// no emoji/unicode glyphs, bundled with the app.
const I = ({ size = 16, children, ...props }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
       stroke="currentColor" strokeWidth="2" strokeLinecap="round"
       strokeLinejoin="round" aria-hidden="true"
       style={{ flexShrink: 0, verticalAlign: '-2px' }} {...props}>
    {children}
  </svg>
);

export const IconBell = (p) => (
  <I {...p}><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
    <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></I>
);
export const IconStar = ({ filled, ...p }) => (
  <I {...p} fill={filled ? 'var(--amber)' : 'none'}
     stroke={filled ? 'var(--amber)' : 'currentColor'}>
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26" />
  </I>
);
export const IconSearch = (p) => (
  <I {...p}><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></I>
);
export const IconX = (p) => (
  <I {...p}><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></I>
);
export const IconChevronDown = (p) => <I {...p}><polyline points="6 9 12 15 18 9" /></I>;
export const IconChevronRight = (p) => <I {...p}><polyline points="9 18 15 12 9 6" /></I>;
export const IconMaximize = (p) => (
  <I {...p}><polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" />
    <line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" /></I>
);
export const IconTrendUp = (p) => (
  <I {...p}><polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" /></I>
);
export const IconTrendDown = (p) => (
  <I {...p}><polyline points="22 17 13.5 8.5 8.5 13.5 2 7" /><polyline points="16 17 22 17 22 11" /></I>
);
export const IconAlert = (p) => (
  <I {...p}><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></I>
);
export const IconActivity = (p) => (
  <I {...p}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></I>
);
export const IconZap = (p) => (
  <I {...p}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></I>
);
export const IconClock = (p) => (
  <I {...p}><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></I>
);
export const IconCheck = (p) => <I {...p}><polyline points="20 6 9 17 4 12" /></I>;
export const IconDroplet = (p) => (
  <I {...p}><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" /></I>
);
export const IconLayers = (p) => (
  <I {...p}><polygon points="12 2 2 7 12 12 22 7 12 2" />
    <polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></I>
);
export const IconCommand = (p) => (
  <I {...p}><path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z" /></I>
);
export const IconRows = (p) => (
  <I {...p}><rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="3" y1="15" x2="21" y2="15" /></I>
);
export const IconCalc = (p) => (
  <I {...p}><rect x="4" y="2" width="16" height="20" rx="2" /><line x1="8" y1="6" x2="16" y2="6" />
    <line x1="8" y1="12" x2="8" y2="12.01" /><line x1="12" y1="12" x2="12" y2="12.01" />
    <line x1="16" y1="12" x2="16" y2="16" /><line x1="8" y1="16" x2="8" y2="16.01" />
    <line x1="12" y1="16" x2="12" y2="16.01" /></I>
);
export const IconInbox = (p) => (
  <I {...p}><polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
    <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" /></I>
);
export const IconBook = (p) => (
  <I {...p}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></I>
);
