
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
  const [lastSyncData, setLastSyncData] = useState<{ media_details: any[]; stories: any[] } | null>(null);
  const [instagramProfile, setInstagramProfile] = useState<{ username?: string; profile_picture_url?: string } | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [mediaTab, setMediaTab] = useState<'posts' | 'reels' | 'stories'>('posts');
  const [lastSyncPayload, setLastSyncPayload] = useState<any>(null);
  const backendOrigin = new URL(import.meta.env.VITE_API_BASE || 'http://localhost:8000').origin;
  const callbackOriginsRef = useRef<Set<string>>(new Set([backendOrigin]));
  const formatDateTime = (value: string | null) => {
    if (!value) return 'Nunca';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return 'Nunca';
    return parsed.toLocaleString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  };

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
      setLastSyncData(null);
      setInstagramProfile(null);
      setLastSyncedAt(null);
      setLastSyncPayload(null);
      setMediaTab('posts');
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
      if (data.media_summary) {
        setSyncSummary(data.media_summary);
      }
      if (data.insights) {
        setGraphInsights(data.insights);
      }
      setLastSyncData({ media_details: data.media_details || [], stories: data.stories || [] });
      setLastSyncPayload(data);
      if (data.user) {
        setInstagramProfile(data.user);
      }
      setLastSyncedAt(data.synced_at || new Date().toISOString());
      setMessage('Sincronización completada. Datos actualizados.');
      console.debug('sync response', data);
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
      if (data.last_synced_at) {
        setLastSyncedAt(data.last_synced_at);
      }
      if (data.profile) {
        setInstagramProfile(data.profile);
      }
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

  const comments = dashboard?.latest_comments || [];
  const replies = dashboard?.latest_replies || [];
  const selectedAccount = accounts.find((acc) => acc.id === selectedAccountId);
  const selectedConnected = Boolean(selectedAccount?.connected);
  const displayName = instagramProfile?.username ?? (selectedAccount ? selectedAccount.account_handle : 'Cuenta de Instagram');
  const heroAvatarLetter = displayName ? displayName.charAt(0).toUpperCase() : 'I';
  const lastSyncLabel = formatDateTime(lastSyncedAt);
  const insights = [
    {
      label: 'Estado de conexión',
      value: selectedConnected ? 'Listo' : 'Pendiente',
      detail: selectedConnected ? 'Token activo' : 'Token requerido',
    },
    {
      label: 'Última sincronización',
      value: lastSyncLabel,
      detail: lastSyncedAt ? 'Actualizado recientemente' : 'Sin sincronizaciones aún',
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

  const graphMetrics = [
    { label: 'Posts', value: summaryData.posts },
    { label: 'Reels', value: summaryData.reels },
    { label: 'Historias', value: summaryData.stories },
    { label: 'Likes', value: summaryData.total_likes },
  ];
  const maxGraphValue = Math.max(...graphMetrics.map((metric) => metric.value), 1);

  const mediaDetails = lastSyncData?.media_details || [];
  const reelMedia = mediaDetails.filter((media: any) => ['VIDEO', 'REEL'].includes(String(media.type || '').toUpperCase()));
  const postMedia = mediaDetails.filter((media: any) => !['VIDEO', 'REEL'].includes(String(media.type || '').toUpperCase()));
  const storyMedia = lastSyncData?.stories || [];

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

  const formatCommentError = (error: string) => {
    if (!error) return '';
    if (error.includes('missing_scope:instagram_business_manage_comments')) {
      return 'Falta el permiso instagram_business_manage_comments en el login.';
    }
    if (error.includes('OAuthException') || error.includes('code":190')) {
      return 'No autorizado para leer comentarios con este token.';
    }
    return error.slice(0, 120);
  };



  return (
    <div className="client-shell">
      <header className="client-hero client-hero--compact client-hero--premium">
        <div className="hero-identity">
          <div className="hero-avatar">
            {instagramProfile?.profile_picture_url ? (
              <img src={instagramProfile.profile_picture_url} alt={displayName} />
            ) : (
              <span>{heroAvatarLetter}</span>
            )}
          </div>
          <div>
            <p className="hero-eyebrow">{instagramProfile?.username ? 'Instagram · Conectado' : 'Instagram'}</p>
            <h1>{displayName}</h1>
            <p className="hero-subhead">
              {selectedConnected ? 'Cuenta conectada y lista para sincronizar.' : 'Sin token activo. Conecta primero para recibir comentarios.'}
            </p>
          </div>
        </div>
        <div className="hero-actions hero-actions--sync">
          <div className="hero-meta">
            <p>Última sincronización</p>
            <strong>{lastSyncLabel}</strong>
            <p className="hero-meta-detail">{lastSyncedAt ? 'actualizado recientemente' : 'nunca sincronizado'}</p>
          </div>
          <button className="btn primary" onClick={syncAccount} disabled={!selectedConnected}>
            Sincronizar ahora
          </button>
        </div>
      </header>

      <section className="graph-row">
        {graphMetrics.map((metric) => (
          <article key={metric.label} className="graph-card">
            <p className="graph-label">{metric.label}</p>
            <div className="graph-track" role="presentation">
              <div
                className="graph-bar"
                style={{ width: `${(metric.value / maxGraphValue) * 100}%` }}
              />
            </div>
            <p className="graph-value">{metric.value}</p>
          </article>
        ))}
      </section>

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

      {lastSyncPayload && (
        <details className="sync-debug-json-wrap">
          <summary>Ver salida de sincronización</summary>
          <pre className="sync-debug-json">{JSON.stringify(lastSyncPayload, null, 2)}</pre>
        </details>
      )}

      <section className="activity-panel">
        <div className="activity-head">
          <div>
            <p className="activity-eyebrow">Actividad reciente</p>
            <h2>Lo que estamos monitorizando</h2>
          </div>
        </div>

        <div className="activity-grid">
          <article className="activity-card activity-card--stretch">
            <div className="media-browser-head">
              <h3>Medios</h3>
              <div className="media-tabs">
                <button className={`media-tab ${mediaTab === 'posts' ? 'media-tab--active' : ''}`} onClick={() => setMediaTab('posts')}>Publicaciones</button>
                <button className={`media-tab ${mediaTab === 'reels' ? 'media-tab--active' : ''}`} onClick={() => setMediaTab('reels')}>Reels</button>
                <button className={`media-tab ${mediaTab === 'stories' ? 'media-tab--active' : ''}`} onClick={() => setMediaTab('stories')}>Historias</button>
              </div>
            </div>

            {mediaTab === 'posts' && (
              postMedia.length ? (
                <div className="media-grid media-grid--compact">
                  {postMedia.map((media: any) => (
                    <article key={media.id} className="media-preview-card">
                      <div className="media-preview-thumb media-preview-thumb--compact" style={media.media_url ? { backgroundImage: `url(${media.media_url})` } : undefined}>
                        {!media.media_url && <span>Sin preview</span>}
                      </div>
                      <p className="media-caption">{media.caption || '(sin caption)'}</p>
                      <p className="media-meta">{media.comments_fetched}/{media.comment_count} comentarios · {media.like_count} likes</p>
                      {media.comment_error && <p className="media-error">{formatCommentError(media.comment_error)}</p>}
                      {media.permalink && <a className="media-link" href={media.permalink} target="_blank" rel="noreferrer">Ver publicación</a>}
                    </article>
                  ))}
                </div>
              ) : <p className="activity-empty">Sin publicaciones recientes en el último sync.</p>
            )}

            {mediaTab === 'reels' && (
              reelMedia.length ? (
                <div className="media-grid media-grid--compact">
                  {reelMedia.map((media: any) => (
                    <article key={media.id} className="media-preview-card">
                      <div className="media-preview-thumb media-preview-thumb--compact" style={media.media_url ? { backgroundImage: `url(${media.media_url})` } : undefined}>
                        {!media.media_url && <span>Sin preview</span>}
                      </div>
                      <p className="media-caption">{media.caption || '(sin caption)'}</p>
                      <p className="media-meta">{media.comments_fetched}/{media.comment_count} comentarios · {media.like_count} likes</p>
                      {media.comment_error && <p className="media-error">{formatCommentError(media.comment_error)}</p>}
                      {media.permalink && <a className="media-link" href={media.permalink} target="_blank" rel="noreferrer">Ver reel</a>}
                    </article>
                  ))}
                </div>
              ) : <p className="activity-empty">Sin reels recientes en el último sync.</p>
            )}

            {mediaTab === 'stories' && (
              storyMedia.length ? (
                <div className="media-grid media-grid--compact">
                  {storyMedia.map((story: any) => (
                    <article key={story.id} className="media-preview-card media-preview-card--story">
                      <div className="media-preview-thumb media-preview-thumb--compact" style={story.media_url ? { backgroundImage: `url(${story.media_url})` } : undefined}>
                        {!story.media_url && <span>Sin preview</span>}
                      </div>
                      <p className="media-caption">{story.caption || '(sin caption)'}</p>
                      <p className="media-meta">{story.timestamp ? new Date(story.timestamp).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '—'}</p>
                      {story.permalink && <a className="media-link" href={story.permalink} target="_blank" rel="noreferrer">Ver historia</a>}
                    </article>
                  ))}
                </div>
              ) : <p className="activity-empty">Sin historias activas.</p>
            )}
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
                        <p className="comment-author">{x.author_handle ? `@${x.author_handle}` : 'Cliente'}</p>
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
                <p className="activity-empty">No hay comentarios sincronizados todavía.</p>
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
