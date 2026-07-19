// Profile-menu dialogs:
//   • ChangePasswordModal — any signed-in user changes their own password.
//   • ManageUsersModal    — admins list / add (with role) / remove users.
// Backed by /api/auth/change-password and /api/users (admin-only).
import { useEffect, useState } from 'react';
import { apiDelete, apiGet, apiPost } from './api';
import { useLang } from './i18n';

function Modal({ title, onClose, children }) {
  return (
    <div className="umodal-overlay" onClick={onClose}>
      <div className="umodal" onClick={(e) => e.stopPropagation()}>
        <div className="umodal-head">
          <h3 style={{ margin: 0, fontSize: 15 }}>{title}</h3>
          <button className="notifc-x" onClick={onClose} aria-label="close">×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function ChangePasswordModal({ onClose }) {
  const { t } = useLang();
  const [cur, setCur] = useState('');
  const [nw, setNw] = useState('');
  const [nw2, setNw2] = useState('');
  const [err, setErr] = useState('');
  const [done, setDone] = useState(false);

  const submit = async () => {
    setErr('');
    if (nw.length < 6) { setErr(t('pwTooShort')); return; }
    if (nw !== nw2) { setErr(t('pwMismatch')); return; }
    try {
      await apiPost('/auth/change-password', { current_password: cur, new_password: nw });
      setDone(true);
    } catch (e) { setErr(e.message || 'error'); }
  };

  return (
    <Modal title={t('changePassword')} onClose={onClose}>
      {done ? (
        <div style={{ color: 'var(--green)', fontSize: 13, padding: '6px 0' }}>
          ✓ {t('pwChanged')}
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 10 }}>
          <input className="input" type="password" autoComplete="current-password"
                 placeholder={t('currentPassword')} value={cur}
                 onChange={(e) => setCur(e.target.value)} />
          <input className="input" type="password" autoComplete="new-password"
                 placeholder={t('newPassword')} value={nw}
                 onChange={(e) => setNw(e.target.value)} />
          <input className="input" type="password" autoComplete="new-password"
                 placeholder={t('confirmPassword')} value={nw2}
                 onChange={(e) => setNw2(e.target.value)} />
          {err && <div style={{ color: 'var(--red)', fontSize: 12 }}>{err}</div>}
          <button className="btn" onClick={submit}>{t('save')}</button>
        </div>
      )}
    </Modal>
  );
}

export function ManageUsersModal({ me, onClose }) {
  const { t } = useLang();
  const [users, setUsers] = useState([]);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('operator');
  const [err, setErr] = useState('');

  const load = () => apiGet('/users').then(setUsers).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const add = async () => {
    setErr('');
    try {
      await apiPost('/users', { username: username.trim(), password, role });
      setUsername(''); setPassword(''); setRole('operator');
      load();
    } catch (e) { setErr(e.message); }
  };

  const del = async (id) => {
    setErr('');
    try { await apiDelete(`/users/${id}`); load(); }
    catch (e) { setErr(e.message); }
  };

  return (
    <Modal title={t('manageUsers')} onClose={onClose}>
      <div style={{ display: 'grid', gap: 14 }}>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr>
              <th>{t('username')}</th><th>{t('role')}</th><th></th>
            </tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td><b>{u.username}</b></td>
                  <td>
                    <span className={`badge ${u.role === 'admin' ? 'info' : ''}`}>
                      {u.role === 'admin' ? t('roleAdmin') : t('roleOperator')}
                    </span>
                  </td>
                  <td style={{ textAlign: 'end' }}>
                    {u.username !== me?.username && (
                      <button className="btn ghost sm" style={{ color: 'var(--red)' }}
                              onClick={() => del(u.id)}>{t('remove')}</button>
                    )}
                  </td>
                </tr>
              ))}
              {!users.length && (
                <tr><td colSpan={3} style={{ color: 'var(--text-3)' }}>—</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12,
                      display: 'grid', gap: 8 }}>
          <div className="notifc-set-title">{t('addUser')}</div>
          <input className="input" placeholder={t('username')} value={username}
                 onChange={(e) => setUsername(e.target.value)} />
          <input className="input" type="password" autoComplete="new-password"
                 placeholder={t('password')} value={password}
                 onChange={(e) => setPassword(e.target.value)} />
          <label className="notifc-row" style={{ justifyContent: 'space-between' }}>
            <span>{t('role')}</span>
            <select className="input" style={{ width: 150 }} value={role}
                    onChange={(e) => setRole(e.target.value)}>
              <option value="operator">{t('roleOperator')}</option>
              <option value="admin">{t('roleAdmin')}</option>
            </select>
          </label>
          {err && <div style={{ color: 'var(--red)', fontSize: 12 }}>{err}</div>}
          <button className="btn" onClick={add}>{t('addUser')}</button>
        </div>
      </div>
    </Modal>
  );
}
