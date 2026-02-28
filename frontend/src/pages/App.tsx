import { FormEvent, useEffect, useMemo, useState } from 'react';
import { api, setSessionHeader } from '../services/api';

type ActionConfig = {
  id: string;
  label: string;
  method: 'get' | 'post' | 'delete';
  endpoint: string;
  bodyBuilder?: () => Record<string, unknown>;
  requires?: Array<'mediaId' | 'commentId' | 'message' | 'rawEndpoint'>;
};

const actions: ActionConfig[] = [
  { id: 'me', label: 'GET /me', method: 'get', endpoint: '/api/instagram/me' },
  { id: 'media', label: 'GET /media', method: 'get', endpoint: '/api/instagram/media' },
  {
    id: 'comments',
    label: 'GET /comments/{media_id}',
    method: 'get',
    endpoint: '/api/instagram/comments/{mediaId}',
    requires: ['mediaId'],
  },
  {
    id: 'comment',
    label: 'GET /comment/{comment_id}',
    method: 'get',
    endpoint: '/api/instagram/comment/{commentId}',
    requires: ['commentId'],
  },
  {
    id: 'replies',
    label: 'GET /replies/{comment_id}',
    method: 'get',
    endpoint: '/api/instagram/replies/{commentId}',
    requires: ['commentId'],
  },
  {
    id: 'add-comment',
    label: 'POST /comments/{media_id}',
    method: 'post',
    endpoint: '/api/instagram/comments/{mediaId}',
    requires: ['mediaId', 'message'],
    bodyBuilder: () => ({ message: stateCache.message }),
  },
  {
    id: 'reply',
    label: 'POST /reply/{comment_id}',
    method: 'post',
    endpoint: '/api/instagram/reply/{commentId}',
    requires: ['commentId', 'message'],
    bodyBuilder: () => ({ message: stateCache.message }),
  },
  {
    id: 'hide',
    label: 'POST /comments/{comment_id}/visibility (hide=true)',
    method: 'post',
    endpoint: '/api/instagram/comments/{commentId}/visibility',
    requires: ['commentId'],
    bodyBuilder: () => ({ hide: true }),
  },
  {
    id: 'delete-comment',
    label: 'DELETE /comments/{comment_id}',
    method: 'delete',
    endpoint: '/api/instagram/comments/{commentId}',
    requires: ['commentId'],
  },
  {
    id: 'raw',
    label: 'POST /raw',
    method: 'post',
    endpoint: '/api/instagram/raw',
    requires: ['rawEndpoint'],
    bodyBuilder: () => ({ endpoint: stateCache.rawEndpoint }),
  },
];

const stateCache = {
  message: '',
  rawEndpoint: '',
};

export function App() {
  const [sessionId, setSessionId] = useState<string | null>(localStorage.getItem('ig_session'));
  const [profile, setProfile] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>('');
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [mediaId, setMediaId] = useState('');
  const [commentId, setCommentId] = useState('');
  const [message, setMessage] = useState('Thanks for your comment! 🙌');
  const [rawEndpoint, setRawEndpoint] = useState('/me?fields=id,name,username');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const incomingSession = params.get('session');
    if (incomingSession) {
      setSessionId(incomingSession);
      localStorage.setItem('ig_session', incomingSession);
      window.history.replaceState({}, '', '/');
    }
  }, []);

  useEffect(() => {
    setSessionHeader(sessionId);
    if (!sessionId) {
      localStorage.removeItem('ig_session');
      setProfile(null);
      return;
    }
    localStorage.setItem('ig_session', sessionId);
    api
      .get('/api/instagram/session')
      .then((res) => setProfile(res.data))
      .catch(() => {
        setSessionId(null);
        setProfile(null);
        localStorage.removeItem('ig_session');
      });
  }, [sessionId]);

  stateCache.message = message;
  stateCache.rawEndpoint = rawEndpoint;

  const loginWithInstagram = async () => {
    try {
      const { data } = await api.get('/api/instagram/login-url');
      window.location.href = data.url;
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to start login');
    }
  };

  const logout = () => {
    setSessionId(null);
    setResult(null);
    setError('');
  };

  const executeAction = async (action: ActionConfig) => {
    const missing = (action.requires || []).filter((key) => {
      if (key === 'mediaId') return !mediaId.trim();
      if (key === 'commentId') return !commentId.trim();
      if (key === 'message') return !message.trim();
      if (key === 'rawEndpoint') return !rawEndpoint.trim();
      return false;
    });
    if (missing.length) {
      setError(`Missing fields: ${missing.join(', ')}`);
      return;
    }

    const endpoint = action.endpoint
      .replace('{mediaId}', mediaId.trim())
      .replace('{commentId}', commentId.trim());

    try {
      setLoadingAction(action.id);
      setError('');
      let response;
      if (action.method === 'get') response = await api.get(endpoint);
      else if (action.method === 'delete') response = await api.delete(endpoint);
      else response = await api.post(endpoint, action.bodyBuilder ? action.bodyBuilder() : {});
      setResult(response.data);
    } catch (err: any) {
      setResult(null);
      setError(err?.response?.data?.detail || err?.message || 'Request failed');
    } finally {
      setLoadingAction(null);
    }
  };

  const output = useMemo(() => JSON.stringify(result || { info: 'Run an action to see JSON output.' }, null, 2), [result]);

  if (!sessionId) {
    return (
      <main className="login-page">
        <section className="login-card">
          <p className="eyebrow">Instagram Wrapper</p>
          <h1>Login with Instagram</h1>
          <p className="subtext">Sign in with your Instagram Business account to test wrapper endpoints.</p>
          <button className="primary-btn" onClick={loginWithInstagram}>Login with Instagram</button>
          {error && <p className="error-text">{error}</p>}
        </section>
      </main>
    );
  }

  return (
    <main className="dashboard-page">
      <header className="topbar">
        <div>
          <p className="eyebrow">Connected</p>
          <h1>Instagram API Playground</h1>
          <p className="subtext">{profile?.username ? `@${profile.username}` : 'Session active'}</p>
        </div>
        <button className="ghost-btn" onClick={logout}>Logout</button>
      </header>

      <section className="inputs-panel">
        <label>
          Media ID
          <input value={mediaId} onChange={(e) => setMediaId(e.target.value)} placeholder="1789..." />
        </label>
        <label>
          Comment ID
          <input value={commentId} onChange={(e) => setCommentId(e.target.value)} placeholder="1790..." />
        </label>
        <label>
          Message
          <input value={message} onChange={(e) => setMessage(e.target.value)} />
        </label>
        <label>
          Raw endpoint
          <input value={rawEndpoint} onChange={(e) => setRawEndpoint(e.target.value)} placeholder="/me/media" />
        </label>
      </section>

      <section className="grid-layout">
        <div className="actions-grid">
          {actions.map((action) => (
            <button key={action.id} className="action-btn" onClick={() => executeAction(action)} disabled={loadingAction === action.id}>
              <strong>{action.label}</strong>
              <span>{loadingAction === action.id ? 'Loading...' : 'Run'}</span>
            </button>
          ))}
        </div>

        <div className="output-panel">
          <div className="output-head">
            <h2>JSON response</h2>
            {error && <p className="error-text">{error}</p>}
          </div>
          <pre>{output}</pre>
        </div>
      </section>
    </main>
  );
}
