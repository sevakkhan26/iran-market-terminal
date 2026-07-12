// ⌘K / Ctrl+K command palette: jump to pages, assets, and quick actions.
import { useEffect, useMemo, useRef, useState } from 'react';
import { IconActivity, IconBook, IconChevronRight, IconClock, IconCommand,
         IconInbox, IconLayers, IconSearch, IconStar, IconZap } from './icons';
import { useLang } from './i18n';

export default function CommandPalette({ open, onClose, assets, go, actions }) {
  const { t, lang, setLang } = useLang();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  const items = useMemo(() => {
    const pages = [
      { icon: <IconLayers />, label: t('overview'), kbd: 'G M', run: () => go('overview') },
      { icon: <IconActivity />, label: t('analytics'), run: () => go('analytics') },
      { icon: <IconZap />, label: t('desk'), run: () => go('desk') },
      { icon: <IconClock />, label: t('calendar'), run: () => go('calendar') },
      { icon: <IconInbox />, label: t('news'), run: () => go('news') },
      { icon: <IconBook />, label: t('help'), run: () => go('help') },
      { icon: <IconStar />, label: t('admin'), run: () => go('admin') },
    ];
    const assetItems = assets.map((a) => ({
      icon: <IconChevronRight />, label: `${a} — ${t('priceChart')}`,
      keywords: a.toLowerCase(), run: () => go('market', a),
    }));
    const actionItems = [
      { icon: <IconCommand />, label: lang === 'fa' ? 'Switch to English' : 'تغییر به فارسی',
        run: () => setLang(lang === 'fa' ? 'en' : 'fa') },
      ...(actions || []),
    ];
    return [...assetItems, ...pages, ...actionItems];
  }, [assets, t, lang, go, setLang, actions]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) =>
      i.label.toLowerCase().includes(q) || (i.keywords || '').includes(q));
  }, [items, query]);

  useEffect(() => { if (open) { setQuery(''); setActive(0); setTimeout(() => inputRef.current?.focus(), 30); } }, [open]);
  useEffect(() => { setActive(0); }, [query]);

  if (!open) return null;

  const select = (item) => { item.run(); onClose(); };

  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, filtered.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === 'Enter' && filtered[active]) select(filtered[active]);
    else if (e.key === 'Escape') onClose();
  };

  return (
    <div className="palette-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="palette" role="dialog" aria-label="Command palette">
        <div style={{ display: 'flex', alignItems: 'center', paddingInlineStart: 14, color: 'var(--text-3)' }}>
          <IconSearch />
          <input ref={inputRef} value={query} onKeyDown={onKey}
                 placeholder={lang === 'fa' ? 'جستجو: دارایی، صفحه، عملیات…' : 'Search assets, pages, actions…'}
                 onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="palette-list" ref={listRef}>
          {filtered.map((item, i) => (
            <button key={i} className={`palette-item ${i === active ? 'active' : ''}`}
                    onMouseEnter={() => setActive(i)} onClick={() => select(item)}>
              {item.icon}{item.label}
              {item.kbd && <span className="kbd">{item.kbd}</span>}
            </button>
          ))}
          {!filtered.length && (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>
              {lang === 'fa' ? 'موردی یافت نشد' : 'No matches'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
