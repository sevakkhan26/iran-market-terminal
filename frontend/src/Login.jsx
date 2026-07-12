// Simple single-user login + change-credentials modal.
import { useState } from 'react';
import { apiPost, setToken } from './api';
import { useLang } from './i18n';

export default function Login({ onLogin }) {
  const { t, lang, setLang } = useLang();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e?.preventDefault();
    setError(''); setBusy(true);
    try {
      const res = await apiPost('/auth/login', { username, password });
      setToken(res.token);
      onLogin(res.user);
    } catch (err) {
      setError(err.message);
    } finally { setBusy(false); }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', padding: 20 }}>
      <div className="card" style={{ width: 'min(380px, 94vw)', padding: 28 }}>
        <div className="logo" style={{ justifyContent: 'center', marginBottom: 6 }}>
          <span className="pulse" />
          <span style={{ fontSize: 17 }}>Iran Market <span style={{ color: 'var(--accent)' }}>Terminal</span></span>
        </div>
        <div style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-3)', marginBottom: 20 }}>
          {t('signInPrompt')}
        </div>
        <form onSubmit={submit} style={{ display: 'grid', gap: 12 }}>
          <input className="input" placeholder={t('username')} value={username}
                 autoFocus autoComplete="username"
                 onChange={(e) => setUsername(e.target.value)} />
          <input className="input" type="password" placeholder={t('password')}
                 value={password} autoComplete="current-password"
                 onChange={(e) => setPassword(e.target.value)} />
          {error && <div style={{ color: 'var(--red)', fontSize: 12.5 }}>{error}</div>}
          <button className="btn" disabled={busy || !username || !password}>
            {busy ? '…' : t('signIn')}
          </button>
        </form>
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 18 }}>
          <div className="seg">
            <button className={lang === 'en' ? 'active' : ''} onClick={() => setLang('en')}>EN</button>
            <button className={lang === 'fa' ? 'active' : ''} onClick={() => setLang('fa')}>فا</button>
          </div>
        </div>
      </div>
    </div>
  );
}

