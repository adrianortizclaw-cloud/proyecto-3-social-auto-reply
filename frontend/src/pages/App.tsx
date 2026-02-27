
import { useEffect, useRef, useState } from 'react';
import { api, setToken } from '../services/api';

type Account = {
  id: number;
  platform: string;
  account_handle: string;
  prompt_persona: string;
  connected: boolean;
};



type SyncSummary = {
  stories: number;
  reels: number;
  posts: number;
  total_likes: number;
  synced_comments: number;
};

export function App() {
  const [token, setAuthToken] = useState<string | null>(localStorage.getItem('token'));
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [dashboard, setDashboard] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [handle, setHandle] = useState('');
  const [syncSummary, setSyncSummary] = useState<SyncSummary | null>(null);
  const [graphInsights, setGraphInsights] = useState<Record<string, any> | null>(null);
  const backendOrigin = new URL(import.meta.env.VITE_API_BASE || 'http://localhost:8000').origin;
  const callbackOriginsRef = useRef<Set<string>>(new Set([backendOrigin]));

  useEffect(() => {
    setToken(token);
    if (token) {
      localStorage.setItem('token', token);
      loadAccounts();
    } else {
      localStorage.removeItem('token');
      setAccounts([]);
      setDashboard(null);
      setSyncSummary(null);
      setGraphInsights(null);
    }
  }, [token]);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (!callbackOriginsRef.current.has(event.origin)) {
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
    try {
      const { data } = await api.get('/api/accounts');
      setAccounts(data);
      if (data.length) {
        setSelectedAccountId(data[0].id);
        await loadDashboard(data[0].id);
      }
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setMessage('Tu sesión expiró. Vuelve a conectar desde la pantalla de login.');
        setAuthToken(null);
      }
    }
  }

  async function startInstagramLogin() {
    const normalized = handle.trim().replace(/^@/, '');
    if (!normalized) {
      setMessage('Introduce el nombre de la cuenta de Instagram.');
      return;
    }
    try {
      const { data } = await api.post('/api/auth/instagram/start', { handle: normalized });
      if (data.callback_origin) {
        callbackOriginsRef.current.add(data.callback_origin);
      }
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

  async function syncAccount() {
    if (!selectedAccountId) return;
    try {
      const { data } = await api.post(`/api/dashboard/${selectedAccountId}/sync`);
      const auto = data.auto_reply || {};
      if (data.media_summary) {
        setSyncSummary(data.media_summary);
      }
      if (data.insights) {
        setGraphInsights(data.insights);
      }
      const summaryDetail = data.media_summary
        ? ` | posts:${data.media_summary.posts ?? 0} reels:${data.media_summary.reels ?? 0} historias:${data.media_summary.stories ?? 0} likes:${data.media_summary.total_likes ?? 0}`
        : '';
      setMessage(`Sync OK ✅ posts:${data.created_posts ?? 0} comments:${data.created_comments ?? 0} | auto:${auto.sent ?? 0}${summaryDetail}`);
      await loadDashboard(selectedAccountId);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const reason = detail?.reason || err?.response?.data?.reason || 'error desconocido';
      const metaDetail = detail?.detail ? ` | meta: ${String(detail.detail).slice(0, 220)}` : '';
      setMessage(`Sync falló: ${reason}${metaDetail}`);
    }
  }

  async function loadDashboard(accountId: number) {
    try {
      const { data } = await api.get(`/api/dashboard/${accountId}`);
      console.debug('dashboard response', { posts: data.latest_posts?.length, comments: data.latest_comments?.length });
      setDashboard(data);
    } catch (err: any) {
      console.error('dashboard load failed', err?.response?.data || err?.message);
      if (err?.response?.status === 401) {
        setMessage('Tu sesión expiró. Vuelve a conectar desde la pantalla de login.');
        setAuthToken(null);
      }
    }
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
  const summaryData = {
    stories: syncSummary?.stories ?? 0,
    reels: syncSummary?.reels ?? 0,
    posts: syncSummary?.posts ?? 0,
    total_likes: syncSummary?.total_likes ?? 0,
    synced_comments: syncSummary?.synced_comments ?? 0,
  };

  const summaryCards = [
    { label: 'Historias', value: summaryData.stories },
    { label: 'Reels', value: summaryData.reels },
    { label: 'Publicaciones', value: summaryData.posts },
    { label: 'Likes totales', value: summaryData.total_likes },
  ];

  const graphInsightCards = graphInsights
    ? Object.entries(graphInsights).map(([name, values]) => {
        const candidate = Array.isArray(values) && values.length ? values[0] : null;
        const rawValue = candidate?.value ?? '—';
        const formattedValue = typeof rawValue === 'number' ? rawValue.toLocaleString() : rawValue;
        const detail = candidate?.end_time ? new Date(candidate.end_time).toLocaleDateString('es-ES', { month: 'short', day: 'numeric' }) : '';
        return {
          label: name.replace(/_/g, ' '),
          value: formattedValue,
          detail,
        };
      })
    : [];



  return (
    <div className="client-shell">
      <header className="client-hero client-hero--compact">
        <div>
          <p className="hero-eyebrow">Estado de conexión</p>
          <h1>
            {selectedAccount ? `${selectedAccount.platform.toUpperCase()} · ${selectedAccount.account_handle}` : 'Cuenta de Instagram'}
          </h1>
          <p className="hero-subhead">
            {selectedConnected ? 'Cuenta conectada y lista para sincronizar.' : 'Sin token activo. Conecta primero para recibir comentarios.'}
          </p>
        </div>
        <div className="hero-actions hero-actions--sync">
          <div className="hero-meta">
            <p>Última sincronización</p>
            <strong>{lastSyncLabel}</strong>
          </div>
          <button className="btn primary" onClick={syncAccount} disabled={!selectedConnected}>
            Sincronizar ahora
          </button>
        </div>
      </header>

      <div className="stats-row">
        {summaryCards.map((stat) => (
          <article key={stat.label} className="stat-card">
            <div className="stat-value">{stat.value}</div>
            <p className="stat-label">{stat.label}</p>
          </article>
        ))}
      </div>

      <section className="insight-row">
        {insights.map((insight) => (
          <article key={insight.label} className="insight-card">
            <p className="insight-label">{insight.label}</p>
            <p className="insight-value">{insight.value}</p>
            <p className="insight-detail">{insight.detail}</p>
          </article>
        ))}
      </section>

      {graphInsightCards.length > 0 && (
        <section className="insight-row insight-row--graph">
          {graphInsightCards.map((insight) => (
            <article key={insight.label} className="insight-card">
              <p className="insight-label">{insight.label}</p>
              <p className="insight-value">{insight.value}</p>
              {insight.detail && <p className="insight-detail">{insight.detail}</p>}
            </article>
          ))}
        </section>
      )}

      <p className="status-row">
        {message || (selectedConnected ? 'Todo está listo. Pulsa Sincronizar si quieres forzar un refresco ahora.' : 'Activa la conexión desde el login para empezar a recoger datos.')}
      </p>

      <section className="activity-panel">
        <div className="activity-head">
          <div>
            <p className="activity-eyebrow">Actividad reciente</p>
            <h2>Lo que estamos monitorizando</h2>
          </div>
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
