// Market intelligence feed.
import { useState } from 'react';
import { usePoll } from '../api';
import { Badge, Chips } from '../components';
import { useLang } from '../i18n';
import { timeAgo } from '../util';

export default function News() {
  const { t, lang } = useLang();
  const [items, setItems] = useState(null);
  const [minImpact, setMinImpact] = useState('ALL');
  const [cat, setCat] = useState('All');

  const impactParam = minImpact === 'HIGH' ? 3 : minImpact === 'MEDIUM' ? 2 : 1;
  usePoll(`/news?min_impact=${impactParam}&coin=${cat === 'All' ? 'ALL' : cat}`,
          setItems, 60000, [impactParam, cat]);

  if (!items) return <div className="skel" style={{ height: 300 }} />;

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 14, flexWrap: 'wrap' }}>
        <h2 style={{ fontSize: 18 }}>{t('news')}</h2>
        <Chips options={['ALL', 'HIGH', 'MEDIUM']} value={minImpact} onChange={setMinImpact} />
        <Chips options={['All', 'BTC', 'ETH', 'MARKET']} value={cat} onChange={setCat} />
      </div>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))' }}>
        {items.map((n, i) => (
          <a key={i} href={n.url} target="_blank" rel="noopener noreferrer"
             className="card" style={{ display: 'block', color: 'var(--text)',
               borderInlineStart: `3px solid ${n.impact === 'HIGH' ? 'var(--red)' : 'var(--amber)'}` }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <Badge level={n.impact === 'HIGH' ? 'high' : 'medium'}>{n.impact}</Badge>
              <Badge level="info">{n.category}</Badge>
              <span style={{ marginInlineStart: 'auto', fontSize: 11, color: 'var(--text-3)' }}>
                {timeAgo(n.timestamp, lang)}
              </span>
            </div>
            <div style={{ fontSize: 13.5, fontWeight: 600, lineHeight: 1.4 }}>{n.title}</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 7 }}>
              {t('source')}: {n.source}
            </div>
          </a>
        ))}
      </div>
      {!items.length && <div className="empty">{t('noData')}</div>}
    </div>
  );
}
