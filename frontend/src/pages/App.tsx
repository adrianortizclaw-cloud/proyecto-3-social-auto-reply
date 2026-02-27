
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
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [dashboard, setDashboard] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [platform, setPlatform] = useState('instagram');
  const [handle, setHandle] = useState('');
  const [persona, setPersona] = useState('Tono cercano, profesional y rápido.');
  const [connectingAccountId, setConnectingAccountId] = useState<number | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const backendOrigin = new URL(import.meta.env.VITE_API_BASE || 'http://localhost:8000').origin;

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

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.origin !== backendOrigin) {
        return;
      }
      const data = event.data || {};
      if (typeof data.token !== 'string') {
        return;
      }
      setAuthToken(data.token);
      setMessage('Instagram conectado. Cargando tus cuentas...');
      if (data.social_account_id) {
        setSelectedAccountId(Number(data.social_account_id));
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [backendOrigin]);

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

  async function startInstagramLogin() {
    const normalized = handle.trim().replace(/^@/, '');
    if (!normalized) {
      setMessage('Introduce el nombre de la cuenta de Instagram.');
      return;
    }
    try {
      const { data } = await api.post('/api/auth/instagram/start', { handle: normalized });
      const popup = window.open(data.url, 'instagram-login', 'width=600,height=700');
      if (!popup) {
        setMessage('Permite popups para continuar con Instagram.');
        return;
      }
      popup.focus();
      setMessage('Abrimos Instagram en otra pestaña para autenticarte.');
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'error desconocido';
      setMessage(`No pude iniciar el login de Instagram: ${detail}`);
    }
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
      <div className="login-screen">
        <div className="login-card">
          <p className="eyebrow">Proyecto 3</p>
          <h1>Conecta con Instagram</h1>
          <p className="subhead">Introduce el nombre de tu cuenta Business o Creator; usamos el nuevo flujo oficial de Instagram Login.</p>
          <label className="field-label">Cuenta de Instagram</label>
          <input
            className="field-input login-input"
            placeholder="@nombre_cliente"
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
          />
          <button className="btn primary login-btn" onClick={startInstagramLogin} disabled={!handle.trim()}>
            Continuar con Instagram
          </button>
          <p className="login-note">{message || 'Abriremos el login oficial de Instagram (scopes: instagram_business_basic, content_publish, manage_messages/comments). No necesitas Facebook ni email.'}</p>
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
  const lastSyncLabel = dashboard?.last_synced_at || dashboard?.last_sync || 'Nunca';
  const insights = [
    {
      label: 'Estado de conexión',
      value: selectedConnected ? 'Listo' : 'Pendiente',
      detail: selectedConnected ? 'Token activo' : 'Token requerido',
    },
    {
      label: 'Última sincronización',
      value: lastSyncLabel,
      detail: 'Verifica los datos si ha pasado mucho tiempo',
    },
    {
      label: 'Comentarios nuevos',
      value: comments.length,
      detail: `${comments.length} sin respuesta`,
    },
    {
      label: 'Respuestas enviadas',
      value: replies.length,
      detail: replies.length ? 'Última respuesta generada hace poco' : 'Aún no generadas',
    },
  ];

  const quickActions = [
    {
      label: 'Sincronizar ahora',
      action: syncAccount,
      disabled: !selectedConnected,
    },
    {
      label: 'Vincular Instagram',
      action: () => selectedAccount && connectInstagram(selectedAccount.id),
      disabled: !selectedAccount || connectingAccountId === selectedAccount.id,
    },
    {
      label: 'Actualizar dashboard',
      action: () => selectedAccountId && loadDashboard(selectedAccountId),
      disabled: !selectedAccountId,
    },
  ];

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

      <section className="insight-row">
        {insights.map((insight) => (
          <article key={insight.label} className="insight-card">
            <p className="insight-label">{insight.label}</p>
            <p className="insight-value">{insight.value}</p>
            <p className="insight-detail">{insight.detail}</p>
          </article>
        ))}
      </section>

      <div className="quick-actions">
        {quickActions.map((action) => (
          <button key={action.label} className="btn action-btn" onClick={action.action} disabled={action.disabled}>
            {action.label}
          </button>
        ))}
      </div>

      <p className="status-row">{message || 'Selecciona una cuenta, vincúlala y los comentarios llegarán solos.'}</p>

      <div className="stats-row">
        {heroStats.map((stat) => (
          <article key={stat.label} className="stat-card">
            <div className="stat-value">{stat.value}</div>
            <p className="stat-label">{stat.label}</p>
          </article>
        ))}
      </div>

      <section className="client-grid client-grid--stack">
        <article className="panel panel--accent accounts-panel">
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

        <article className="panel create-panel">
          <div className="panel-head">
            <div>
              <p className="panel-eyebrow">Agregar nuevas cuentas</p>
              <h2>Se hace solo 1-2 veces</h2>
              <p className="panel-subhead">Activamos este formulario cuando realmente necesites trackear otra cuenta.</p>
            </div>
            <button className="btn ghost" onClick={() => setShowCreateForm((prev) => !prev)}>
              {showCreateForm ? 'Ocultar formulario' : 'Abrir formulario'}
            </button>
          </div>

          <p className="panel-note panel-note--muted">Solo pedimos el handle. El token usa los nuevos scopes de Instagram Login y se guarda en backend sin exponerlo.</p>

          {showCreateForm && (
            <div className="create-form">
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

              <button className="btn primary" onClick={createAccount} disabled={!handle}>Guardar y preparar</button>
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
