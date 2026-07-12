// Data management: add exchanges/pairs at runtime, tune settings.
import { useState } from 'react';
import { apiDelete, apiGet, apiPost, usePoll } from '../api';
import { useLang } from '../i18n';
import { fmtDateTime } from '../util';

const SPEC_PLACEHOLDER = `{
  "orderbook_url": "https://api.example.com/depth?symbol={symbol}",
  "symbol_template": "{base}{quote}",
  "quote_name": "IRT",
  "bids_path": "bids",
  "asks_path": "asks",
  "price_scale": 1.0,
  "taker_fee_pct": 0.25
}`;

export default function Admin({ meta, refreshMeta }) {
  const { t, lang } = useLang();
  const [settings, setSettings] = useState(null);
  const [saved, setSaved] = useState(false);
  const [pairs, setPairs] = useState([]);
  const [customEx, setCustomEx] = useState([]);
  const [newPair, setNewPair] = useState('');
  const [newCgId, setNewCgId] = useState('');
  const [exName, setExName] = useState('');
  const [exSpec, setExSpec] = useState('');
  const [err, setErr] = useState('');

  usePoll('/settings', (s) => setSettings((prev) => prev ?? s), 60000);
  usePoll('/admin/pairs', setPairs, 30000);
  usePoll('/admin/exchanges', setCustomEx, 30000);

  const saveSettings = async () => {
    try {
      setSettings(await apiPost('/settings', settings));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) { setErr(e.message); }
  };

  const addPair = async () => {
    if (!newPair.trim()) return;
    try {
      await apiPost('/admin/pairs', {
        base: newPair.trim().toUpperCase(),
        coingecko_id: newCgId.trim() || null,
      });
      setNewPair(''); setNewCgId('');
      setPairs(await apiGet('/admin/pairs'));
      refreshMeta?.();
    } catch (e) { setErr(e.message); }
  };

  const addExchange = async () => {
    setErr('');
    try {
      const spec = JSON.parse(exSpec || '{}');
      await apiPost('/admin/exchanges', { name: exName.trim(), spec });
      setExName(''); setExSpec('');
      setCustomEx(await apiGet('/admin/exchanges'));
      refreshMeta?.();
    } catch (e) { setErr(e.message); }
  };

  const fields = [
    ['market_interval', 'marketInterval'], ['snapshot_interval', 'snapshotInterval'],
    ['news_interval', 'newsInterval'], ['calendar_interval', 'calendarInterval'],
    ['request_timeout', 'requestTimeout'], ['ui_refresh_interval', 'uiRefresh'],
    ['arb_min_edge_pct', 'arbMinEdge'],
  ];

  return (
    <div>
      <h2 style={{ fontSize: 18, marginBottom: 14 }}>{t('admin')}</h2>
      {err && <div className="toast critical" style={{ position: 'static', marginBottom: 12 }}>{err}</div>}

      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 360px), 1fr))' }}>
        {/* settings */}
        <div className="card">
          <h3>{t('settings')}</h3>
          {settings ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {fields.map(([key, label]) => (
                <label key={key} style={{ display: 'grid', gridTemplateColumns: '1fr 110px',
                                          gap: 8, alignItems: 'center', fontSize: 12.5 }}>
                  <span style={{ color: 'var(--text-2)' }}>{t(label)}</span>
                  <input className="input" type="number" value={settings[key]}
                         onChange={(e) => setSettings({ ...settings, [key]: +e.target.value })} />
                </label>
              ))}
              <button className="btn" onClick={saveSettings}>
                {saved ? '✓ ' + t('saved') : t('save')}
              </button>
            </div>
          ) : <div className="skel" style={{ height: 200 }} />}
        </div>

        {/* pairs */}
        <div className="card">
          <h3>{t('addPair')}</h3>
          <div style={{ display: 'grid', gap: 8, marginBottom: 12 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <input className="input" placeholder={t('baseAsset')} value={newPair}
                     onChange={(e) => setNewPair(e.target.value)}
                     onKeyDown={(e) => e.key === 'Enter' && addPair()} />
              <button className="btn" onClick={addPair}>{t('add')}</button>
            </div>
            <input className="input" placeholder={t('coingeckoId')} value={newCgId}
                   onChange={(e) => setNewCgId(e.target.value)}
                   onKeyDown={(e) => e.key === 'Enter' && addPair()} />
          </div>
          <h3>{t('customPairs')}</h3>
          {pairs.length ? pairs.map((p) => (
            <div key={p.base + p.quote}
                 style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
              <b>{p.base}/{p.quote}</b>
              <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                  {fmtDateTime(p.created_ts, lang)}
                </span>
                <button className="btn danger sm" onClick={async () => {
                  await apiDelete(`/admin/pairs/${p.base}`);
                  setPairs(await apiGet('/admin/pairs'));
                  refreshMeta?.();
                }}>×</button>
              </span>
            </div>
          )) : <div className="empty" style={{ padding: '12px 0' }}>—</div>}
          <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 10 }}>
            {t('exchanges')}: {meta?.assets?.join(', ')}
          </div>
        </div>

        {/* custom exchanges */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <h3>{t('addExchange')} — {t('dataManagement')}</h3>
          <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'minmax(200px, 300px) 1fr',
                        alignItems: 'start' }}>
            <div style={{ display: 'grid', gap: 10 }}>
              <input className="input" placeholder={t('exchangeName')} value={exName}
                     onChange={(e) => setExName(e.target.value)} />
              <button className="btn" onClick={addExchange} disabled={!exName.trim()}>
                {t('add')}
              </button>
              <div style={{ fontSize: 11.5, color: 'var(--text-3)', lineHeight: 1.6 }}>
                Declarative connector: point it at any REST order-book endpoint.
                <code style={{ color: 'var(--accent)' }}> {'{symbol}'}</code>,
                <code style={{ color: 'var(--accent)' }}> {'{base}'}</code>,
                <code style={{ color: 'var(--accent)' }}> {'{quote}'}</code> are substituted.
                Use <code>price_scale: 0.1</code> for Rial-quoted venues.
              </div>
            </div>
            <textarea className="input" placeholder={SPEC_PLACEHOLDER} value={exSpec}
                      onChange={(e) => setExSpec(e.target.value)} spellCheck={false} />
          </div>

          {customEx.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3>{t('customExchanges')}</h3>
              {customEx.map((x) => (
                <div key={x.name}
                     style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                              padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                  <span><b>{x.name}</b>
                    <span style={{ fontSize: 11, color: 'var(--text-3)', marginInlineStart: 8 }}>
                      {x.spec?.orderbook_url}
                    </span>
                  </span>
                  <button className="btn danger sm" onClick={async () => {
                    await apiDelete(`/admin/exchanges/${encodeURIComponent(x.name)}`);
                    setCustomEx(await apiGet('/admin/exchanges'));
                    refreshMeta?.();
                  }}>×</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
