// Per-asset view: candles + indicators, exchange comparison, DOM ladder,
// depth chart, slippage calculator, arbitrage.
import { useEffect, useRef, useState } from 'react';
import { apiGet, usePoll } from '../api';
import { AssetIcon, ChangePill, EmptyState, FlashNum, Seg, ScoreBar, StatusDot } from '../components';
import { CandleChart, DepthChart } from '../charts';
import { IconCalc, IconMaximize, IconZap } from '../icons';
import { useLang } from '../i18n';
import { fmtCompact, fmtNum, fmtPct, timeAgo } from '../util';

// Timeframe = the REAL candle interval (label matches what you get).
const TIMEFRAMES = [
  { value: '1min', label: '1m' }, { value: '5min', label: '5m' },
  { value: '15min', label: '15m' }, { value: '1h', label: '1H' },
  { value: '4h', label: '4H' }, { value: '1d', label: '1D' },
];

export default function MarketDetail({ asset, assets, onSelectAsset }) {
  const { t, lang } = useLang();
  const [detail, setDetail] = useState(null);
  const [tf, setTf] = useState('15min');
  const [chartEx, setChartEx] = useState('composite');
  const [candles, setCandles] = useState(null);
  const [overlays, setOverlays] = useState({ sma: false, ema: false, vwap: false });
  const [compareEx, setCompareEx] = useState('');
  const [compareCandles, setCompareCandles] = useState(null);
  const [depthEx, setDepthEx] = useState(null);
  const [depth, setDepth] = useState(null);
  const chartCardRef = useRef(null);

  usePoll(`/pair/${asset}`, setDetail, 5000, [asset]);

  useEffect(() => {
    setCandles(null);
    const load = () => apiGet(`/candles/${asset}?tf=${tf}&exchange=${chartEx}`)
      .then(setCandles).catch(() => setCandles([]));
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [asset, tf, chartEx]);

  useEffect(() => {
    if (!compareEx) { setCompareCandles(null); return; }
    apiGet(`/candles/${asset}?tf=${tf}&exchange=${compareEx}`)
      .then(setCompareCandles).catch(() => setCompareCandles(null));
  }, [asset, tf, compareEx]);

  const liveExchanges = (detail?.exchanges || []).filter((e) => e.mid > 0);
  const effDepthEx = depthEx || liveExchanges[0]?.exchange;

  useEffect(() => {
    if (!effDepthEx) return;
    const load = () => apiGet(`/depth/${effDepthEx}/${asset}`).then(setDepth).catch(() => {});
    load();
    const id = setInterval(load, 6000);
    return () => clearInterval(id);
  }, [effDepthEx, asset]);

  if (!detail) return <div className="skel" style={{ height: 400 }} />;

  const bestAsk = liveExchanges.reduce((a, b) =>
    (!a || (b.best_ask > 0 && b.best_ask < a.best_ask)) ? b : a, null);
  const bestBid = liveExchanges.reduce((a, b) =>
    (!a || b.best_bid > a.best_bid) ? b : a, null);

  const toggleOverlay = (key) => setOverlays((o) => ({ ...o, [key]: !o[key] }));
  const fullscreen = () => {
    const el = chartCardRef.current;
    if (!el) return;
    document.fullscreenElement ? document.exitFullscreen() : el.requestFullscreen?.();
  };

  return (
    <div>
      {/* header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
        <Seg options={assets} value={asset} onChange={onSelectAsset} />
        <AssetIcon symbol={asset} size={38} />
        <div>
          <div className="hero-price">
            <FlashNum value={detail.price} bold />{' '}
            <span style={{ fontSize: 'var(--fs-md)', color: 'var(--text-3)', fontWeight: 500 }}>{detail.quote}</span>
          </div>
          {detail.usd_reference && (
            <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-3)', marginTop: 2 }}>
              ${fmtNum(detail.usd_reference)} ·{' '}
              <span style={{ color: (detail.premium_pct ?? 0) > 0 ? 'var(--amber)' : 'var(--green)' }}>
                {fmtPct(detail.premium_pct)} {t('vsGlobal')}
              </span>
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span title="1h"><ChangePill value={detail.change_1h} /></span>
          <span title="24h"><ChangePill value={detail.change_24h} /></span>
          <span title="7d"><ChangePill value={detail.change_7d} /></span>
        </div>
      </div>

      {/* price chart */}
      <div className="card" style={{ marginBottom: 14 }} ref={chartCardRef}>
        <h3>
          {t('priceChart')} — {chartEx === 'composite' ? t('composite') : chartEx}
          <span style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {['sma', 'ema', 'vwap'].map((k) => (
              <button key={k} className={`chip ${overlays[k] ? 'active' : ''}`}
                      onClick={() => toggleOverlay(k)}>
                {k === 'sma' ? 'MA20' : k === 'ema' ? 'EMA20' : 'VWAP'}
              </button>
            ))}
            <select className="input" style={{ width: 'auto', padding: '3px 8px', fontSize: 12 }}
                    value={compareEx} onChange={(e) => setCompareEx(e.target.value)}
                    title={t('compare')}>
              <option value="">{t('compare')}: {t('none')}</option>
              {liveExchanges.filter((e) => e.exchange !== chartEx)
                .map((e) => <option key={e.exchange} value={e.exchange}>{e.exchange}</option>)}
            </select>
            <Seg options={[{ value: 'composite', label: t('composite') },
                           ...liveExchanges.map((e) => ({ value: e.exchange, label: e.exchange }))]}
                 value={chartEx} onChange={setChartEx} />
            <Seg options={TIMEFRAMES} value={tf} onChange={setTf} />
            <button className="icon-btn" onClick={fullscreen} aria-label="Fullscreen">
              <IconMaximize size={15} />
            </button>
          </span>
        </h3>
        {candles === null ? <div className="skel" style={{ height: 380 }} />
          : candles.length ? (
            <CandleChart candles={candles} overlays={overlays}
                         compare={compareEx && compareCandles?.length
                           ? { name: compareEx, candles: compareCandles } : null} />)
          : <EmptyState title={t('noData')} />}
      </div>

      {/* exchange comparison */}
      <div className="card" style={{ padding: 0, marginBottom: 14 }}>
        <h3 style={{ padding: '14px 16px 0' }}>{asset}/{detail.quote} — {t('exchanges')}</h3>
        <table className="tbl">
          <thead>
            <tr>
              <th>{t('exchange')}</th><th>{t('status')}</th>
              <th>{t('bid')}</th><th>{t('ask')}</th>
              <th>{t('spread')}</th><th>{t('spreadStats1h')}</th>
              <th>{t('depth')}</th><th>{t('imbalance')}</th>
              <th>{t('liquidityScore')}</th><th>{t('volume24')}</th>
              <th>{t('fee')}</th><th>{t('latency')}</th>
            </tr>
          </thead>
          <tbody>
            {detail.exchanges.map((e) => {
              const isBestAsk = bestAsk && e.exchange === bestAsk.exchange;
              const isBestBid = bestBid && e.exchange === bestBid.exchange;
              const st = e.spread_stats_1h || {};
              return (
                <tr key={e.exchange}>
                  <td>
                    <b style={{ color: e.color }}>{e.exchange}</b>
                    {isBestAsk && <span className="badge info" style={{ marginInlineStart: 6 }}>{t('bestBuy')}</span>}
                    {isBestBid && <span className="badge high" style={{ marginInlineStart: 6 }}>{t('bestSell')}</span>}
                  </td>
                  <td><StatusDot status={e.status} /> <span style={{ fontSize: 11.5, color: 'var(--text-2)' }}>{t(e.status)}</span></td>
                  <td style={{ color: 'var(--green)' }}><FlashNum value={e.best_bid} /></td>
                  <td style={{ color: 'var(--red)' }}><FlashNum value={e.best_ask} /></td>
                  <td className="num">{e.spread_pct ? e.spread_pct.toFixed(3) + '%' : '—'}</td>
                  <td className="num" style={{ fontSize: 11, color: 'var(--text-2)' }}>
                    {st.avg != null
                      ? `μ ${st.avg.toFixed(2)} · ${st.min.toFixed(2)}–${st.max.toFixed(2)} · σ ${st.stdev.toFixed(2)}`
                      : '—'}
                  </td>
                  <td className="num">{fmtCompact(e.bid_depth_quote + e.ask_depth_quote)}</td>
                  <td className="num" style={{ color: e.depth_imbalance > 0 ? 'var(--green)' : 'var(--red)' }}>
                    {(e.depth_imbalance * 100).toFixed(0)}%
                  </td>
                  <td><ScoreBar score={e.liquidity_score} /></td>
                  <td className="num" title={e.volume_estimated ? t('volEstimated') : undefined}>
                    {e.volume_estimated && <span style={{ color: 'var(--accent)' }}>≈</span>}
                    {fmtCompact(e.volume_24h_quote)}
                  </td>
                  <td className="num">{e.taker_fee_pct}%</td>
                  <td className="num" style={{ color: 'var(--text-3)' }}>
                    {e.latency_ms ? Math.round(e.latency_ms) + 'ms' : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))' }}>
        {/* order book ladder */}
        <div className="card">
          <h3>
            {t('orderBook')} — {effDepthEx}
            <Seg options={liveExchanges.map((e) => e.exchange)} value={effDepthEx}
                 onChange={setDepthEx} />
          </h3>
          {depth?.bids?.length ? <Ladder depth={depth} t={t} /> : <EmptyState title={t('noData')} />}
        </div>

        {/* depth chart */}
        <div className="card">
          <h3>{t('depthChart')}</h3>
          {depth?.bids?.length
            ? <DepthChart bids={depth.bids} asks={depth.asks} />
            : <EmptyState title={t('noData')} />}
          {depth && (
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 6 }}>
              {t('lastUpdate')}: {timeAgo(depth.timestamp, lang)}
            </div>
          )}
        </div>

        {/* slippage calculator */}
        <SlippageCalc asset={asset} t={t} />

        {/* arbitrage */}
        <div className="card" style={{ padding: 0 }}>
          <h3 style={{ padding: '14px 16px 0' }}>{t('arbitrage')}</h3>
          <table className="tbl">
            <thead>
              <tr>
                <th>{t('buyAt')}</th><th>{t('sellAt')}</th>
                <th>{t('gross')}</th><th>{t('net')}</th>
                <th>{t('size')}</th><th>{t('profit')}</th>
              </tr>
            </thead>
            <tbody>
              {detail.arbitrage.filter((o) => o.net_pct > 0).map((o, i) => (
                <tr key={i}>
                  <td><b style={{ color: 'var(--green)' }}>{o.buy_exchange}</b>
                    <div className="num" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{fmtNum(o.buy_price, 0)}</div>
                  </td>
                  <td><b style={{ color: 'var(--red)' }}>{o.sell_exchange}</b>
                    <div className="num" style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{fmtNum(o.sell_price, 0)}</div>
                  </td>
                  <td className="num">{o.gross_pct.toFixed(3)}%</td>
                  <td className="num" style={{ color: 'var(--green)', fontWeight: 700 }}>
                    {o.net_pct.toFixed(3)}%
                  </td>
                  <td className="num">{o.max_size_base} {asset}</td>
                  <td className="num">{fmtCompact(o.est_profit_quote)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!detail.arbitrage.filter((o) => o.net_pct > 0).length && (
            <EmptyState icon={<IconZap />} title={t('noData')} hint={t('arbHint')} />)}
        </div>
      </div>
    </div>
  );
}

/* --------------------------- DOM ladder ------------------------------ */

function Ladder({ depth, t }) {
  const N = 12;
  const bids = depth.bids.slice(0, N);
  const asks = depth.asks.slice(0, N);
  const maxQty = Math.max(...bids.map(([, q]) => q), ...asks.map(([, q]) => q), 1e-12);
  const spreadPct = bids[0] && asks[0]
    ? ((asks[0][0] - bids[0][0]) / asks[0][0] * 100).toFixed(3) : null;
  return (
    <div>
      <div className="ladder">
        <div>
          <div className="ladder-head" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>{t('qty')}</span><span style={{ color: 'var(--green)' }}>{t('bid')}</span>
          </div>
          {bids.map(([p, q], i) => (
            <div key={i} className="ladder-row bid">
              <span className="bar" style={{ width: `${(q / maxQty) * 100}%` }} />
              <span style={{ color: 'var(--text-2)' }}>{q.toFixed(4)}</span>
              <span style={{ color: 'var(--green)' }}>{fmtNum(p, 0)}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="ladder-head" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--red)' }}>{t('ask')}</span><span>{t('qty')}</span>
          </div>
          {asks.map(([p, q], i) => (
            <div key={i} className="ladder-row ask">
              <span className="bar" style={{ width: `${(q / maxQty) * 100}%` }} />
              <span style={{ color: 'var(--red)' }}>{fmtNum(p, 0)}</span>
              <span style={{ color: 'var(--text-2)' }}>{q.toFixed(4)}</span>
            </div>
          ))}
        </div>
      </div>
      {spreadPct && (
        <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-3)', marginTop: 7 }}>
          {t('spread')}: <b className="num">{spreadPct}%</b>
        </div>
      )}
    </div>
  );
}

/* ----------------------- slippage calculator ------------------------- */

function SlippageCalc({ asset, t }) {
  const [sizeB, setSizeB] = useState(2);
  const [rows, setRows] = useState(null);

  useEffect(() => {
    const notional = Math.max(0.05, sizeB) * 1e9;
    const load = () => apiGet(`/impact/${asset}?notional=${notional}`)
      .then(setRows).catch(() => setRows([]));
    const id = setTimeout(load, 300);   // debounce typing
    return () => clearTimeout(id);
  }, [asset, sizeB]);

  const best = rows?.find((r) => r.buy_impact_pct != null);

  return (
    <div className="card">
      <h3>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <IconCalc size={14} /> {t('slippageCalc')}
        </span>
      </h3>
      <label style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, fontSize: 12.5 }}>
        <span style={{ color: 'var(--text-2)', flex: 1 }}>{t('sizeB')}</span>
        <input className="input" type="number" min="0.1" step="0.5" value={sizeB}
               style={{ maxWidth: 110 }}
               onChange={(e) => setSizeB(+e.target.value || 0.1)} />
      </label>
      <table className="tbl">
        <thead><tr>
          <th>{t('exchange')}</th><th>{t('buyImpact')}</th><th>{t('sellImpact')}</th><th>{t('effPrice')}</th>
        </tr></thead>
        <tbody>
          {(rows || []).map((r) => (
            <tr key={r.exchange}
                style={best && r.exchange === best.exchange ? { background: 'var(--accent-glow)' } : undefined}>
              <td>
                <b>{r.exchange}</b>
                {best && r.exchange === best.exchange &&
                  <span className="badge info" style={{ marginInlineStart: 6 }}>{t('bestVenue')}</span>}
              </td>
              <td className="num" style={{
                color: r.buy_impact_pct == null ? 'var(--red)'
                     : r.buy_impact_pct >= 0.5 ? 'var(--amber)' : 'var(--green)' }}>
                {r.buy_impact_pct == null ? t('bookTooThin') : r.buy_impact_pct.toFixed(3) + '%'}
              </td>
              <td className="num" style={{
                color: r.sell_impact_pct == null ? 'var(--red)'
                     : r.sell_impact_pct >= 0.5 ? 'var(--amber)' : 'var(--green)' }}>
                {r.sell_impact_pct == null ? t('bookTooThin') : r.sell_impact_pct.toFixed(3) + '%'}
              </td>
              <td className="num">{r.buy_price ? fmtNum(r.buy_price, 0) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows && !rows.length && <EmptyState title={t('noData')} />}
    </div>
  );
}
