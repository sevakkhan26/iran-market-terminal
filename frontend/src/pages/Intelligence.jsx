// Competitive intelligence: TOB scoreboard, market share, opportunity ledger.
import { useEffect, useState } from 'react';
import { apiGet, usePoll } from '../api';
import { EmptyState, Seg } from '../components';
import { MultiLineChart } from '../charts';
import { IconClock, IconTrendDown, IconTrendUp, IconZap } from '../icons';
import { useLang } from '../i18n';
import { fmtCompact, fmtNum, timeAgo } from '../util';

const RANGES = ['1d', '1w', '1m'];
const FALLBACK_COLORS = ['#4a9eff', '#9c6bff', '#00d68f', '#ffb020', '#ff6b9d', '#38c6d9'];

export default function Intelligence({ assets, meta }) {
  const { t } = useLang();
  const [asset, setAsset] = useState('BTC');
  const [range, setRange] = useState('1d');

  const colorOf = (ex, i) =>
    meta?.exchanges?.find((e) => e.name === ex)?.color
    || FALLBACK_COLORS[i % FALLBACK_COLORS.length];

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 14, flexWrap: 'wrap' }}>
        <h2 style={{ fontSize: 'var(--fs-lg)' }}>{t('intelligence')}</h2>
        <Seg options={assets} value={asset} onChange={setAsset} />
        <Seg options={RANGES} value={range} onChange={setRange} />
      </div>

      <TobPanel asset={asset} range={range} colorOf={colorOf} t={t} />
      <div style={{ height: 14 }} />
      <SharePanel asset={asset} range={range} colorOf={colorOf} t={t} />
      <div style={{ height: 14 }} />
      <LedgerPanel t={t} />
    </div>
  );
}

/* ------------------------- 1 · TOB scoreboard ------------------------- */

function TobPanel({ asset, range, colorOf, t }) {
  const [data, setData] = useState(null);
  usePoll(`/tob-share?base=${asset}&range=${range}`, setData, 15000, [asset, range]);

  if (!data) return <div className="skel" style={{ height: 220 }} />;

  const seriesList = data.board.map((r, i) => ({
    name: r.exchange, color: colorOf(r.exchange, i),
    points: r.series.map((p) => ({ ts: p.ts, value: (p.bid + p.ask) / 2 })),
  })).filter((s) => s.points.length > 1);

  return (
    <div className="card">
      <h3>
        {t('tobShare')} — {asset}
        <span style={{ display: 'flex', gap: 12, fontSize: 11, textTransform: 'none',
                       letterSpacing: 0, fontWeight: 500 }}>
          <span>{t('bestBuy')}: <b style={{ color: 'var(--green)' }}>
            {(data.current_best_ask || []).join(', ') || '—'}</b></span>
          <span>{t('bestSell')}: <b style={{ color: 'var(--red)' }}>
            {(data.current_best_bid || []).join(', ') || '—'}</b></span>
        </span>
      </h3>

      {data.board.length ? (
        <>
          <table className="tbl" style={{ marginBottom: 14 }}>
            <thead><tr>
              <th>#</th><th>{t('exchange')}</th>
              <th>{t('bidShare')}</th><th>{t('askShare')}</th>
              <th style={{ width: '34%' }}>{t('combined')}</th>
            </tr></thead>
            <tbody>
              {data.board.map((r, i) => (
                <tr key={r.exchange}>
                  <td style={{ color: i === 0 ? 'var(--amber)' : 'var(--text-3)',
                               fontWeight: i === 0 ? 700 : 400 }}>{r.rank}</td>
                  <td><b style={{ color: colorOf(r.exchange, i) }}>{r.exchange}</b></td>
                  <td className="num">{r.bid_share_pct.toFixed(1)}%</td>
                  <td className="num">{r.ask_share_pct.toFixed(1)}%</td>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, width: '100%' }}>
                      <span style={{ background: 'var(--bg-2)', borderRadius: 4, height: 8,
                                     flex: 1, overflow: 'hidden' }}>
                        <span style={{ display: 'block', height: '100%', borderRadius: 4,
                                       width: `${Math.min(100, r.combined_pct)}%`,
                                       background: colorOf(r.exchange, i) }} />
                      </span>
                      <b className="num" style={{ minWidth: 48 }}>{r.combined_pct.toFixed(1)}%</b>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {seriesList.length > 0 &&
            <MultiLineChart seriesList={seriesList} percent height={210} />}
        </>
      ) : <EmptyState icon={<IconClock />} title={t('noData')} hint={t('tobHint')} />}
    </div>
  );
}

/* ------------------------- 2 · market share --------------------------- */

function SharePanel({ asset, range, colorOf, t }) {
  const [base, setBase] = useState('ALL');
  const [data, setData] = useState(null);
  useEffect(() => { setBase('ALL'); }, []);
  usePoll(`/market-share?base=${base === 'ALL' ? 'ALL' : asset}&range=${range}`,
          setData, 20000, [base, asset, range]);

  if (!data) return <div className="skel" style={{ height: 220 }} />;

  const maxShare = Math.max(...data.current.map((r) => r.share_pct), 1);
  const seriesList = Object.entries(data.series).map(([ex, pts], i) => ({
    name: ex, color: colorOf(ex, i),
    points: pts.map((p) => ({ ts: p.ts, value: p.share })),
  })).filter((s) => s.points.length > 1);

  return (
    <div className="card">
      <h3>
        {t('marketShare')} — {base === 'ALL' ? t('all') : asset}
        <Seg options={[{ value: 'ALL', label: t('all') }, { value: 'ASSET', label: asset }]}
             value={base} onChange={setBase} />
      </h3>
      {data.current.length ? (
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))' }}>
          <div>
            {data.current.map((r, i) => (
              <div key={r.exchange} style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                  <b style={{ color: colorOf(r.exchange, i) }}>{r.exchange}</b>
                  <span className="num" style={{ color: 'var(--text-2)' }}>
                    {fmtCompact(r.volume_quote)} · <b style={{ color: 'var(--text)' }}>{r.share_pct}%</b>
                    {r.trend !== 0 && (
                      <span style={{ color: r.trend > 0 ? 'var(--green)' : 'var(--red)', marginInlineStart: 5 }}>
                        {r.trend > 0 ? <IconTrendUp size={11} /> : <IconTrendDown size={11} />}
                        {Math.abs(r.trend).toFixed(1)}
                      </span>)}
                  </span>
                </div>
                <div style={{ background: 'var(--bg-2)', borderRadius: 4, height: 9, overflow: 'hidden' }}>
                  <div style={{ height: '100%', borderRadius: 4,
                                width: `${(r.share_pct / maxShare) * 100}%`,
                                background: colorOf(r.exchange, i) }} />
                </div>
              </div>
            ))}
            <div style={{ fontSize: 10.5, color: 'var(--text-3)', marginTop: 8 }}>{t('shareNote')}</div>
            {Object.keys(data.estimated || {}).length > 0 && (
              <div style={{ fontSize: 10.5, color: 'var(--accent)', marginTop: 4 }}>
                ≈ {t('volEstimated')}: {Object.entries(data.estimated)
                  .map(([ex, h]) => `${ex} (${h}h)`).join(', ')}
              </div>
            )}
            {data.not_reporting?.length > 0 && (
              <div style={{ fontSize: 10.5, color: 'var(--amber)', marginTop: 4 }}>
                ⚠ {t('notReporting')}: {data.not_reporting.join(', ')}
              </div>
            )}
          </div>
          <div>
            {seriesList.length > 0 &&
              <MultiLineChart seriesList={seriesList} percent height={230} />}
          </div>
        </div>
      ) : <EmptyState title={t('noData')} />}
    </div>
  );
}

/* ---------------------- 3 · opportunity ledger ------------------------ */

function LedgerPanel({ t }) {
  const { lang } = useLang();
  const [days, setDays] = useState(7);
  const [summary, setSummary] = useState(null);
  const [windows, setWindows] = useState([]);
  const [inventory, setInventory] = useState(null);

  usePoll(`/opportunities/summary?days=${days}`, setSummary, 15000, [days]);
  usePoll(`/opportunities/windows?days=${days}&limit=60`, setWindows, 15000, [days]);
  usePoll(`/opportunities/inventory?days=${days}`, setInventory, 30000, [days]);

  if (!summary) return <div className="skel" style={{ height: 260 }} />;

  const maxHour = Math.max(...summary.by_hour, 1);
  const invRows = inventory
    ? Object.entries(inventory.full).map(([ex, req]) => ({
        exchange: ex, ...req, p95: inventory.p95[ex] || { tmn: 0, assets: {} },
      }))
    : [];

  const fmtDur = (s) => s == null ? '—'
    : s < 60 ? `${Math.round(s)}s` : s < 3600 ? `${(s / 60).toFixed(1)}m` : `${(s / 3600).toFixed(1)}h`;

  return (
    <div className="card">
      <h3>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <IconZap size={14} /> {t('opportunities')}
        </span>
        <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 10.5, textTransform: 'none', letterSpacing: 0 }}>
            {t('minEdge')}: <b>{summary.min_edge_pct}%</b> · {t('minEdgeNote')}
          </span>
          <Seg options={[{ value: 1, label: '1D' }, { value: 7, label: '7D' }, { value: 30, label: '30D' }]}
               value={days} onChange={setDays} />
        </span>
      </h3>

      {/* KPIs */}
      <div className="metric-row">
        <div className="metric">
          <div className="label">{t('missedMoney')} · {days}D</div>
          <div className="value" style={{ color: 'var(--amber)' }}>
            {fmtCompact(summary.missed_profit_quote)} <span style={{ fontSize: 11 }}>TMN</span>
          </div>
        </div>
        <div className="metric">
          <div className="label">{t('missed24h')}</div>
          <div className="value">{fmtCompact(summary.missed_profit_24h)} <span style={{ fontSize: 11 }}>TMN</span></div>
        </div>
        <div className="metric">
          <div className="label">{t('windows')}</div>
          <div className="value">{summary.windows_total}
            {summary.open_now > 0 && <span className="badge critical" style={{ marginInlineStart: 8 }}>
              {summary.open_now} {t('openNow')}</span>}
          </div>
        </div>
        <div className="metric">
          <div className="label">{t('medianDuration')}</div>
          <div className="value">{fmtDur(summary.median_duration_sec)}</div>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))' }}>
        {/* hour-of-day distribution */}
        <div>
          <div className="cal-detail-h">{t('byHour')} ({t('iranTime')})</div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 90 }}>
            {summary.by_hour.map((v, h) => (
              <div key={h} title={`${h}:00 — ${fmtCompact(v)} TMN`}
                   style={{ flex: 1, background: v > 0 ? 'var(--accent)' : 'var(--bg-2)',
                            borderRadius: 2, minHeight: 2,
                            height: `${Math.max(2, (v / maxHour) * 100)}%`,
                            opacity: v > 0 ? 0.45 + 0.55 * (v / maxHour) : 1 }} />
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9.5,
                        color: 'var(--text-3)', marginTop: 3 }}>
            <span>00</span><span>06</span><span>12</span><span>18</span><span>23</span>
          </div>

          <div className="cal-detail-h" style={{ marginTop: 14 }}>{t('topRoutes')}</div>
          {summary.top_routes.map((r) => (
            <div key={r.route} style={{ display: 'flex', justifyContent: 'space-between',
                                        fontSize: 12, padding: '4px 0',
                                        borderBottom: '1px solid var(--border)' }}>
              <span>{r.route} <span style={{ color: 'var(--text-3)' }}>×{r.count}</span></span>
              <b className="num" style={{ color: 'var(--amber)' }}>{fmtCompact(r.profit)}</b>
            </div>
          ))}
          {!summary.top_routes.length && <div className="empty" style={{ padding: '14px 0' }}>{t('noData')}</div>}
        </div>

        {/* inventory requirements */}
        <div>
          <div className="cal-detail-h">{t('inventoryReq')} · {days}D</div>
          <div style={{ fontSize: 11, color: 'var(--text-2)', marginBottom: 8, lineHeight: 1.5 }}>
            {t('inventoryNote')}
          </div>
          {invRows.length ? (
            <table className="tbl">
              <thead><tr>
                <th>{t('exchange')}</th>
                <th>{t('capture100')}</th>
                <th>{t('capture95')}</th>
              </tr></thead>
              <tbody>
                {invRows.map((r) => (
                  <tr key={r.exchange}>
                    <td><b>{r.exchange}</b></td>
                    <td className="num" style={{ fontSize: 11.5 }}>
                      {r.tmn > 0 && <div>{fmtCompact(r.tmn)} TMN</div>}
                      {Object.entries(r.assets).map(([a, q]) =>
                        <div key={a}>{fmtNum(q, 4)} {a}</div>)}
                    </td>
                    <td className="num" style={{ fontSize: 11.5, color: 'var(--text-2)' }}>
                      {r.p95.tmn > 0 && <div>{fmtCompact(r.p95.tmn)} TMN</div>}
                      {Object.entries(r.p95.assets).map(([a, q]) =>
                        <div key={a}>{fmtNum(q, 4)} {a}</div>)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <div className="empty" style={{ padding: '14px 0' }}>{t('noData')}</div>}
        </div>

        {/* windows table */}
        <div style={{ gridColumn: '1 / -1' }}>
          <div className="cal-detail-h">{t('windows')}</div>
          <div className="tbl-scroll" style={{ maxHeight: 300, overflowY: 'auto' }}>
            <table className="tbl">
              <thead><tr>
                <th>{t('asset')}</th><th>{t('route')}</th>
                <th>{t('gross')} μ</th><th>Peak %</th>
                <th>{t('size')}</th><th>{t('profit')}</th>
                <th>{t('window')}</th><th />
              </tr></thead>
              <tbody>
                {windows.map((w) => {
                  const open = w.closed_ts == null;
                  return (
                    <tr key={w.id} style={open ? { background: 'var(--green-bg)' } : undefined}>
                      <td><b>{w.base}</b></td>
                      <td style={{ fontSize: 12 }}>
                        <span style={{ color: 'var(--green)' }}>{w.buy_exchange}</span>
                        {' → '}
                        <span style={{ color: 'var(--red)' }}>{w.sell_exchange}</span>
                      </td>
                      <td className="num">{w.avg_net_pct.toFixed(3)}%</td>
                      <td className="num" style={{ fontWeight: 700 }}>{w.peak_net_pct.toFixed(3)}%</td>
                      <td className="num">{fmtNum(w.max_size_base, 4)} {w.base}</td>
                      <td className="num" style={{ color: 'var(--amber)' }}>
                        {fmtCompact(w.peak_profit_quote)}
                      </td>
                      <td className="num" style={{ fontSize: 11 }}>
                        {fmtDur((w.closed_ts || Date.now() / 1000) - w.opened_ts)}
                        <span style={{ color: 'var(--text-3)' }}> · {timeAgo(w.opened_ts, lang)}</span>
                      </td>
                      <td>{open && <span className="badge critical cal-live">● {t('live')}</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!windows.length && <EmptyState icon={<IconZap />} title={t('noData')} hint={t('ledgerHint')} />}
          </div>
        </div>
      </div>
    </div>
  );
}
