import { useEffect, useState } from 'react';
import { apiGet, apiPost, getToken, setAuthErrorHandler, setToken,
         useLiveStream, usePoll } from './api';
import { Badge, Countdown } from './components';
import CommandPalette from './CommandPalette';
import NotificationCenter from './NotificationCenter';
import { IconBell, IconCheck, IconCommand, IconRows, IconX } from './icons';
import { useLang } from './i18n';
import Login from './Login';
import { eventFlag, fmtCompact, fmtNum, fmtPct, timeAgo } from './util';
import Overview from './pages/Overview';
import MarketDetail from './pages/MarketDetail';
import Analytics from './pages/Analytics';
import Desk from './pages/Desk';
import Calendar from './pages/Calendar';
import News from './pages/News';
import Admin from './pages/Admin';
import Help from './pages/Help';
import Intelligence from './pages/Intelligence';

const PAGES = ['overview', 'market', 'analytics', 'desk', 'intel', 'calendar', 'news', 'admin', 'help'];

/** Auth gate: shows the login screen until a valid session exists. */
export default function App() {
  const [authUser, setAuthUser] = useState(null);   // null=checking, false=logged out

  useEffect(() => {
    setAuthErrorHandler(() => { setToken(''); setAuthUser(false); });
    if (!getToken()) { setAuthUser(false); return; }
    apiGet('/auth/me').then(setAuthUser).catch(() => setAuthUser(false));
  }, []);

  if (authUser === null) {
    return <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center',
                         justifyContent: 'center' }}>
      <div className="skel" style={{ width: 320, height: 120 }} /></div>;
  }
  if (authUser === false) return <Login onLogin={setAuthUser} />;
  return <Terminal authUser={authUser} onUserUpdate={setAuthUser}
                   onLogout={async () => {
                     try { await apiPost('/auth/logout', {}); } catch { /* ignore */ }
                     setToken('');
                     setAuthUser(false);
                   }} />;
}

function Terminal({ authUser, onLogout, onUserUpdate }) {
  const { t, lang, setLang } = useLang();
  const [page, setPage] = useState(() => location.hash.slice(1).split('/')[0] || 'overview');
  const [asset, setAsset] = useState(() => location.hash.split('/')[1] || 'BTC');
  const [meta, setMeta] = useState(null);
  const [overview, setOverview] = useState([]);
  const [marketsSnap, setMarketsSnap] = useState([]);
  const [toasts, setToasts] = useState([]);
  const [wsLive, setWsLive] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [alertEvents, setAlertEvents] = useState([]);
  const [calendar, setCalendar] = useState([]);
  const [compact, setCompact] = useState(() => localStorage.getItem('density') === 'compact');
  const [userMenu, setUserMenu] = useState(false);

  const refreshMeta = () => apiGet('/meta').then(setMeta).catch(() => {});
  useEffect(() => { refreshMeta(); }, []);
  usePoll('/overview', setOverview, 10000);
  usePoll('/alerts/events?hours=24', setAlertEvents, 15000);
  usePoll('/calendar', setCalendar, 120000);

  useEffect(() => {
    document.body.classList.toggle('compact', compact);
    localStorage.setItem('density', compact ? 'compact' : 'comfortable');
  }, [compact]);

  useEffect(() => {
    const onHash = () => {
      const [p, a] = location.hash.slice(1).split('/');
      if (PAGES.includes(p)) setPage(p);
      if (a) setAsset(a.toUpperCase());
    };
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      } else if (e.key === 'Escape') {
        setPaletteOpen(false); setDrawerOpen(false);
      }
    };
    window.addEventListener('hashchange', onHash);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('hashchange', onHash);
      window.removeEventListener('keydown', onKey);
    };
  }, []);

  const go = (p, a) => { location.hash = a ? `${p}/${a}` : p; setPage(p); if (a) setAsset(a); };

  useLiveStream({
    markets: (msg) => { setWsLive(true); if (msg && msg.data) setMarketsSnap(msg.data); },
    alert: (msg) => {
      const item = { ...msg.data, key: Math.random() };
      setToasts((prev) => [...prev.slice(-3), item]);
      setAlertEvents((prev) => [msg.data, ...prev]);
      setTimeout(() => setToasts((prev) => prev.filter((x) => x.key !== item.key)), 9000);
    },
  });

  const btc = overview.find((r) => r.base === 'BTC');
  const usdt = overview.find((r) => r.base === 'USDT');
  const totalVol = overview.reduce((s, r) => s + (r.volume_24h_quote || 0), 0);
  const assets = meta?.assets?.length ? meta.assets : ['BTC', 'ETH', 'USDT'];
  const unread = alertEvents.filter((e) => !e.acknowledged).length;
  const now = Date.now() / 1000;
  const nextEvent = calendar
    .filter((e) => e.impact === 'High' && e.timestamp > now)
    .sort((a, b) => a.timestamp - b.timestamp)[0];

  const ackAll = async () => {
    await Promise.all(alertEvents.filter((e) => !e.acknowledged)
      .map((e) => apiPost(`/alerts/events/${e.id}/ack`, {}).catch(() => {})));
    setAlertEvents(await apiGet('/alerts/events?hours=24').catch(() => alertEvents));
  };

  const navItems = [
    ['overview', t('overview')], ['analytics', t('analytics')], ['desk', t('desk')],
    ['intel', t('intelligence')], ['calendar', t('calendar')], ['news', t('news')],
    ['admin', t('admin')], ['help', t('help')],
  ];

  return (
    <div className="app">
      <header className="topbar">
        <div className="logo">
          <span className="pulse" />
          <span>Iran Market <span style={{ color: 'var(--accent)' }}>Terminal</span></span>
          {meta?.demo_mode && <span className="badge warning">{t('demoMode')}</span>}
        </div>
        <nav className="nav">
          {navItems.map(([id, label]) => (
            <button key={id}
                    className={page === id || (id === 'overview' && page === 'market') ? 'active' : ''}
                    onClick={() => go(id)}>{label}</button>
          ))}
        </nav>
        <div className="topbar-right">
          <button className="icon-btn" title="Ctrl+K" aria-label="Command palette"
                  onClick={() => setPaletteOpen(true)}>
            <IconCommand />
          </button>
          <button className={`icon-btn ${compact ? 'active' : ''}`} title={t('density')}
                  aria-label={t('density')}
                  style={compact ? { color: 'var(--accent)' } : undefined}
                  onClick={() => setCompact(!compact)}>
            <IconRows />
          </button>
          <button className="icon-btn" aria-label={t('alerts')}
                  onClick={() => setDrawerOpen(true)}>
            <IconBell />
            {unread > 0 && <span className="count">{unread > 99 ? '99+' : unread}</span>}
          </button>
          <span className={`dot ${wsLive ? 'connected' : 'delayed'}`}
                title={wsLive ? 'WebSocket live' : 'Polling'} />
          <div className="seg">
            <button className={lang === 'en' ? 'active' : ''} onClick={() => setLang('en')}>EN</button>
            <button className={lang === 'fa' ? 'active' : ''} onClick={() => setLang('fa')}>فا</button>
          </div>
          <div style={{ position: 'relative' }}>
            <button className="chip" style={{ fontWeight: 600 }}
                    onClick={() => setUserMenu(!userMenu)}>
              {authUser.username} {authUser.role === 'admin' && '★'}
            </button>
            {userMenu && (
              <div className="card" style={{ position: 'absolute', top: '110%',
                    insetInlineEnd: 0, zIndex: 60, minWidth: 180, padding: 8,
                    boxShadow: '0 10px 34px #000000aa' }}>
                <button className="palette-item" style={{ color: 'var(--red)' }}
                        onClick={onLogout}>
                  {t('logout')}
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="statsbar">
        {btc && <span>BTC <b className="num">{fmtNum(btc.price, 0)}</b>{' '}
          <span className={`pill ${(btc.change_24h ?? 0) >= 0 ? 'up' : 'down'}`}
                style={{ padding: '0 5px', fontSize: 11 }}>{fmtPct(btc.change_24h)}</span></span>}
        {usdt && <span>{t('usdtRate')} <b className="num">{fmtNum(usdt.price, 0)}</b></span>}
        {meta?.usd_reference?.BTC && <span>{t('globalBtc')} <b className="num">${fmtNum(meta.usd_reference.BTC, 0)}</b></span>}
        {btc?.premium_pct != null && <span>{t('premium')} <b style={{ color: 'var(--amber)' }}>{fmtPct(btc.premium_pct)}</b></span>}
        <span>{t('totalVolume')} <b className="num">{fmtCompact(totalVol)}</b></span>
        {btc && <span>{t('liveVenues')} <b>{btc.exchanges_live}/{btc.exchanges_total}</b></span>}
        {nextEvent && (
          <span style={{ cursor: 'pointer' }} onClick={() => go('calendar')}
                title={nextEvent.title}>
            {eventFlag(nextEvent.country, nextEvent.title)}{' '}
            <b>{nextEvent.title.length > 26 ? nextEvent.title.slice(0, 25) + '…' : nextEvent.title}</b>{' '}
            <Countdown ts={nextEvent.timestamp} />
          </span>
        )}
      </div>

      <main className="main">
        {page === 'overview' && <Overview onSelectAsset={(a) => go('market', a)} />}
        {page === 'market' && (
          <MarketDetail asset={asset} assets={assets}
                        onSelectAsset={(a) => go('market', a)} />)}
        {page === 'analytics' && (
          <Analytics asset={asset} assets={assets} meta={meta}
                     onSelectAsset={setAsset} />)}
        {page === 'desk' && <Desk />}
        {page === 'intel' && <Intelligence assets={assets} meta={meta} />}
        {page === 'calendar' && <Calendar />}
        {page === 'news' && <News />}
        {page === 'admin' && <Admin meta={meta} refreshMeta={refreshMeta}
                                    isAdmin={authUser.role === 'admin'} />}
        {page === 'help' && <Help />}
      </main>

      {/* alert drawer */}
      {drawerOpen && (
        <>
          <div className="drawer-backdrop" onClick={() => setDrawerOpen(false)} />
          <aside className="drawer" role="dialog" aria-label={t('alerts')}>
            <div className="drawer-head">
              <IconBell /> {t('alerts')}
              {unread > 0 && <span className="badge critical">{unread}</span>}
              <span style={{ marginInlineStart: 'auto', display: 'flex', gap: 6 }}>
                {unread > 0 && (
                  <button className="btn ghost sm" onClick={ackAll}>
                    <IconCheck size={13} /> {t('ackAll')}
                  </button>)}
                <button className="icon-btn" aria-label="Close"
                        onClick={() => setDrawerOpen(false)}><IconX /></button>
              </span>
            </div>
            <div className="drawer-body">
              {alertEvents.length ? alertEvents.map((e, i) => (
                <div key={e.id ?? i}
                     style={{ display: 'flex', gap: 9, alignItems: 'flex-start',
                              padding: '9px 0', borderBottom: '1px solid var(--border)',
                              opacity: e.acknowledged ? 0.45 : 1 }}>
                  <Badge level={e.severity} />
                  <span style={{ flex: 1, fontSize: 12.5, lineHeight: 1.45 }}>
                    {e.message}
                    <div style={{ fontSize: 10.5, color: 'var(--text-3)', marginTop: 2 }}>
                      {timeAgo(e.ts, lang)}
                    </div>
                  </span>
                  {!e.acknowledged && e.id && (
                    <button className="btn ghost sm" onClick={async () => {
                      await apiPost(`/alerts/events/${e.id}/ack`, {});
                      setAlertEvents(await apiGet('/alerts/events?hours=24'));
                    }}>{t('acknowledge')}</button>)}
                </div>
              )) : (
                <div className="empty-state">
                  <div className="empty-state-icon"><IconBell /></div>
                  <div style={{ fontWeight: 600 }}>{t('noAlerts')}</div>
                </div>
              )}
            </div>
          </aside>
        </>
      )}

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)}
                      assets={assets} go={go}
                      actions={[{
                        icon: <IconRows />,
                        label: compact ? t('densityComfort') : t('densityCompact'),
                        run: () => setCompact(!compact),
                      }]} />
          onDone={(newUsername) => {
            setPwModal(false);
            onUserUpdate({ ...authUser, username: newUsername || authUser.username,
                           default_creds: false });
          }} />
      )}

      <div className="toast-wrap">
        {toasts.map((a) => (
          <div key={a.key} className={`toast ${a.severity}`}>
            <b style={{ textTransform: 'uppercase', fontSize: 10.5 }}>{a.severity}</b>
            <div>{a.message}</div>
          </div>
        ))}
      </div>

      {/* operational notifications: node disconnects, upcoming events, breaking news */}
      <NotificationCenter markets={marketsSnap} calendar={calendar}
                          venues={(meta?.exchanges || []).map((e) => e.name)} />
    </div>
  );
}
