import { useEffect, useState } from 'react';
import { api, setToken } from '../services/api';

type Account = {
  id: number;
  platform: string;
  account_handle: string;
  prompt_persona: string;
  connected: boolean;
};

export function App() {
  const [token, setAuthToken] = useState<string | null>(localStorage.getItem('token'));
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [dashboard, setDashboard] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [platform, setPlatform] = useState('instagram');
  const [handle, setHandle] = useState('');
  const [persona, setPersona] = useState('Tono cercano, profesional y rápido.');
  const [connectingAccountId, setConnectingAccountId] = useState<number | null>(null);

  useEffect(() => {
    setToken(token);
    if (token) {
      localStorage.setItem('token', token);
      loadAccounts();
    } else {
      localStorage.removeItem('token');
      setAccounts([]);
      setDashboard(null);
    }
  }, [token]);

  async function register() {
    const { data } = await api.post('/api/auth/register', { email, password });
    setAuthToken(data.access_token);
  }

  async function login() {
    const { data } = await api.post('/api/auth/login', { email, password });
    setAuthToken(data.access_token);
  }

  async function loadAccounts() {
    const { data } = await api.get('/api/accounts');
    setAccounts(data);
    if (data.length) {
      setSelectedAccountId(data[0].id);
      await loadDashboard(data[0].id);
    }
  }

  async function createAccount() {
    await api.post('/api/accounts', {
      platform,
      account_handle: handle,
      prompt_persona: persona,
      auto_mode: 'auto',
    });
    setMessage('Cuenta guardada; cuando conectes Instagram nosotros hacemos el resto.');
    setHandle('');
    await loadAccounts();
  }

  async function connectInstagram(accountId: number) {
    try {
      setConnectingAccountId(accountId);
      const { data } = await api.get(`/api/meta/oauth/start/${accountId}`);
      window.open(data.url, '_blank', 'noopener');
      setMessage('Abrimos el flujo de Instagram en otra pestaña. Completa la conexión y vuelve aquí para actualizar.');
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'error desconocido';
      setMessage(`No se pudo iniciar la conexión: ${detail}`);
    } finally {
      setConnectingAccountId(null);
    }
  }

  async function syncAccount() {
    if (!selectedAccountId) return;
    try {
      const { data } = await api.post(`/api/dashboard/${selectedAccountId}/sync`);
      const auto = data.auto_reply || {};
      setMessage(`Sync OK ✅ posts:${data.created_posts ?? 0} comments:${data.created_comments ?? 0} | auto:${auto.sent ?? 0}`);
      await loadDashboard(selectedAccountId);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const reason = detail?.reason || err?.response?.data?.reason || 'error desconocido';
      const metaDetail = detail?.detail ? ` | meta: ${String(detail.detail).slice(0, 220)}` : '';
      setMessage(`Sync falló: ${reason}${metaDetail}`);
    }
  }

  async function loadDashboard(accountId: number) {
    const { data } = await api.get(`/api/dashboard/${accountId}`);
    setDashboard(data);
  }

  async function generateReply(commentId: number) {
    try {
      const { data } = await api.post(`/api/replies/generate/${commentId}`);
      const extra = data.publish_detail ? ` | ${String(data.publish_detail).slice(0, 140)}` : '';
      setMessage(`Respuesta generada ✅ status:${data.status} intent:${data.intent}${extra}`);
      if (selectedAccountId) await loadDashboard(selectedAccountId);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setMessage(`No se pudo generar respuesta: ${typeof detail === 'string' ? detail : JSON.stringify(detail || {})}`);
    }
  }

  if (!token) {
    return (
      <div className="auth-screen">
        <div className="auth-shell">
          <div className="auth-content">
            <p className="eyebrow">Proyecto 3</p>
            <h1>Social Auto-Reply</h1>
            <p className="subhead">Accede con tu cuenta para orquestar clientes y automatizaciones.</p>
          </div>
          <div className="auth-form">
            <label className="field-label">Email</label>
            <input className="field-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="tuno@cliente.com" />
            <label className="field-label">Contraseña</label>
            <input className="field-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            <div className="auth-actions">
              <button className="btn primary" onClick={register}>Registrarme</button>
              <button className="btn ghost" onClick={login}>Entrar</button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const posts = dashboard?.latest_posts || [];
  const reels = dashboard?.latest_reels || [];
  const comments = dashboard?.latest_comments || [];
  const replies = dashboard?.latest_replies || [];
  const selectedAccount = accounts.find((acc) => acc.id === selectedAccountId);
  const selectedConnected = Boolean(selectedAccount?.connected);

  const heroStats = [
    { label: 'Publicaciones monitorizadas', value: posts.length },
    { label: 'Reels en radar', value: reels.length },
    { label: 'Comentarios nuevos', value: comments.length },
    { label: 'Respuestas enviadas', value: replies.length },
  ];

  return (
    <div className="client-shell">
      <header className="client-hero">
        <div>
          <p className="hero-eyebrow">Panorama social · Proyecto 3</p>
          <h1>Tu cliente conecta con Instagram sin líos.</h1>
          <p className="hero-subhead">Nosotros gestionamos los tokens, la sincronización y las respuestas. Sólo necesitas dar permiso y revisar resultados.</p>
        </div>
        <div className="hero-actions">
          <button className="btn ghost" onClick={() => setAuthToken(null)}>Cerrar sesión</button>
          <button className="btn primary" onClick={syncAccount} disabled={!selectedConnected}>Sincronizar cuenta</button>
        </div>
      </header>

      <p className="status-row">{message || 'Selecciona una cuenta, vincúlala y los comentarios llegarán solos.'}</p>

      <div className="stats-row">
        {heroStats.map((stat) => (
          <article key={stat.label} className="stat-card">
            <div className="stat-value">{stat.value}</div>
            <p className="stat-label">{stat.label}</p>
          </article>
        ))}
      </div>

      <section className="client-grid">
        <article className="panel">
          <div className="panel-head">
            <div>
              <p className="panel-eyebrow">Onboarding rápido</p>
              <h2>Conecta un nuevo cliente</h2>
              <p className="panel-subhead">Solo necesitas el handle o ID. Nosotros generamos el token de Instagram y lo guardamos seguro.</p>
            </div>
          </div>

          <label className="field-label">Cuenta</label>
          <div className="input-row">
            <select className="field-input" value={platform} onChange={(e) => setPlatform(e.target.value)}>
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
              <option value="x">X</option>
            </select>
            <input className="field-input" placeholder="@nombre_cliente o ID numérico" value={handle} onChange={(e) => setHandle(e.target.value)} />
          </div>

          <label className="field-label">Tono sugerido</label>
          <textarea className="field-input" value={persona} onChange={(e) => setPersona(e.target.value)} rows={3} />

          <div className="panel-foot">
            <p className="panel-note">Nuestro backend guarda el app secret y la clave de OpenAI en .env. El token de Instagram se obtiene via OAuth y nunca sale de la base de datos.</p>
          </div>

          <button className="btn primary" onClick={createAccount} disabled={!handle}>Guardar y preparar</button>
        </article>

        <article className="panel panel--accent">
          <div className="panel-head">
            <div>
              <p className="panel-eyebrow">Cuentas activas</p>
              <h2>{selectedAccount ? `${selectedAccount.platform.toUpperCase()} · ${selectedAccount.account_handle}` : 'Elige una cuenta'}</h2>
              <p className="panel-subhead">Selecciona una cuenta para ver la actividad, vincular Instagram y generar respuestas.</p>
            </div>
            <button className="btn secondary" onClick={syncAccount} disabled={!selectedConnected}>
              Sync ahora
            </button>
          </div>

          <div className="account-list">
            {accounts.length ? (
              accounts.map((acc) => (
                <button
                  key={acc.id}
                  className={`account-pill ${selectedAccountId === acc.id ? 'account-pill--active' : ''}`}
                  onClick={() => {
                    setSelectedAccountId(acc.id);
                    loadDashboard(acc.id);
                  }}
                >
                  <div>
                    <strong>{acc.platform}</strong> · {acc.account_handle}
                    <br />
                    <small>ID #{acc.id}</small>
                  </div>
                  <div className="account-pill__meta">
                    <span className="pill-meta">{acc.prompt_persona}</span>
                    <span className={`status-badge ${acc.connected ? 'status-badge--connected' : ''}`}>
                      {acc.connected ? 'Conectada' : 'Pendiente'}
                    </span>
                  </div>
                </button>
              ))
            ) : (
              <p className="panel-note">Todavía no hay cuentas. Empieza creando una nueva y luego víncula Instagram.</p>
            )}
          </div>

          {selectedAccount && !selectedConnected && (
            <div className="connection-hint">
              <p>
                Esta cuenta todavía no tiene token válido. Pulsa <strong>Vincular Instagram</strong> para completar el OAuth y después refresca la lista.
              </p>
              <div className="connection-actions">
                <button
                  className="btn tertiary"
                  onClick={() => connectInstagram(selectedAccount.id)}
                  disabled={connectingAccountId === selectedAccount.id}
                >
                  {connectingAccountId === selectedAccount.id ? 'Abriendo conexión...' : 'Vincular Instagram'}
                </button>
                <button className="btn ghost" onClick={loadAccounts} disabled={connectingAccountId === selectedAccount.id}>
                  Actualizar cuentas
                </button>
              </div>
            </div>
          )}
        </article>
      </section>

      {selectedAccount && !selectedConnected && (
        <div className="connection-warning">
          La sincronización solo funciona cuando la cuenta está conectada. Usa el flujo de Instagram para obtener un token antes de sincronizar.
        </div>
      )}

      <section className="activity-panel">
        <div className="activity-head">
          <div>
            <p className="activity-eyebrow">Actividad reciente</p>
            <h2>Lo que estamos monitorizando</h2>
          </div>
          <button className="btn ghost" onClick={() => selectedAccountId && loadDashboard(selectedAccountId)} disabled={!selectedAccountId}>
            Actualizar datos
          </button>
        </div>

        <div className="activity-grid">
          <article className="activity-card">
            <h3>Publicaciones</h3>
            <ul className="activity-list">
              {posts.map((x: any) => (
                <li key={x.id}>
                  <strong>{x.text ? x.text.slice(0, 60) : '(sin caption)'}</strong>
                  <p className="small">{x.created_at}</p>
                </li>
              ))}
              {!posts.length && <li className="activity-empty">Sin publicaciones por ahora.</li>}
            </ul>
          </article>
          <article className="activity-card">
            <h3>Reels + historias</h3>
            <ul className="activity-list">
              {reels.map((x: any) => (
                <li key={x.id}>
                  <strong>{x.text ? x.text.slice(0, 60) : '(sin información)'}</strong>
                  <p className="small">{x.created_at}</p>
                </li>
              ))}
              {!reels.length && <li className="activity-empty">Sin reels recientes.</li>}
            </ul>
          </article>
          <article className="activity-card activity-card--stretch">
            <h3>Comentarios y respuestas automáticas</h3>
            <div className="comment-grid">
              {comments.length ? (
                comments.map((x: any) => {
                  const internalCommentId = x.comment_id ?? (Number.isFinite(Number(x.id)) ? Number(x.id) : null);
                  return (
                    <div key={`${x.id}-${x.comment_id ?? 'na'}`} className="comment-row">
                      <div>
                        <p className="comment-text">{x.text}</p>
                        <p className="small">{x.created_at}</p>
                      </div>
                      <button
                        className="btn tertiary"
                        onClick={() => internalCommentId && generateReply(Number(internalCommentId))}
                        disabled={!internalCommentId}
                      >
                        {internalCommentId ? 'Generar respuesta' : 'Falta comment_id'}
                      </button>
                    </div>
                  );
                })
              ) : (
                <p className="activity-empty">Los comentarios se llenan tras la primera sincronización.</p>
              )}
            </div>
          </article>
        </div>

        {replies.length > 0 && (
          <article className="activity-card">
            <h3>Respuestas enviadas</h3>
            <ul className="activity-list">
              {replies.map((x: any) => (
                <li key={x.id}>
                  <strong>{x.text.slice(0, 80)}</strong>
                  <p className="small">{x.created_at}</p>
                </li>
              ))}
            </ul>
          </article>
        )}
      </section>
    </div>
  );
}
