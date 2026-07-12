// REST client + WebSocket live stream with automatic reconnect.
import { useEffect, useRef } from 'react';

const BASE = '/api';

// ------------------------------ auth token ------------------------------
export const getToken = () => localStorage.getItem('auth_token') || '';
export const setToken = (t) =>
  t ? localStorage.setItem('auth_token', t) : localStorage.removeItem('auth_token');

let onAuthError = null;
export const setAuthErrorHandler = (fn) => { onAuthError = fn; };

async function request(path, options = {}) {
  const token = getToken();
  const res = await fetch(BASE + path, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  if (res.status === 401 && !path.startsWith('/auth/login')) {
    onAuthError?.();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status}`);
  }
  return res.json();
}

export const apiGet = (path) => request(path);
export const apiPost = (path, body) =>
  request(path, { method: 'POST', body: JSON.stringify(body) });
export const apiDelete = (path) => request(path, { method: 'DELETE' });
export const apiPatch = (path) => request(path, { method: 'PATCH' });

/** Subscribe to the live WebSocket stream. handlers = {markets, alert} */
export function useLiveStream(handlers) {
  const ref = useRef(handlers);
  ref.current = handlers;
  useEffect(() => {
    let ws, timer, closed = false;
    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const token = getToken();
      ws = new WebSocket(`${proto}://${location.host}/ws${token ? `?token=${token}` : ''}`);
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          ref.current[msg.type]?.(msg);
        } catch { /* ignore malformed frames */ }
      };
      ws.onopen = () => { timer = setInterval(() => ws.send('ping'), 25000); };
      ws.onclose = () => {
        clearInterval(timer);
        if (!closed) setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => { closed = true; clearInterval(timer); ws?.close(); };
  }, []);
}

/** Poll an endpoint on an interval; returns nothing — calls cb.
 *  Stale-while-revalidate: cached data is delivered instantly on mount so
 *  switching tabs never flashes skeletons for data we already have. */
const swrCache = new Map();

export function usePoll(path, cb, intervalMs = 15000, deps = []) {
  const cbRef = useRef(cb);
  cbRef.current = cb;
  useEffect(() => {
    let alive = true;
    if (swrCache.has(path)) cbRef.current(swrCache.get(path));   // instant stale data
    const tick = () =>
      apiGet(path).then((d) => {
        swrCache.set(path, d);
        if (alive) cbRef.current(d);
      }).catch(() => {});
    tick();
    const id = setInterval(tick, intervalMs);
    return () => { alive = false; clearInterval(id); };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
}
