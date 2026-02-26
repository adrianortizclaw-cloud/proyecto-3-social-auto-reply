import { useEffect, useState } from 'react';
import { api, setToken } from '../services/api';

type Account = { id: number; platform: string; account_handle: string; prompt_persona: string };

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
  const [instagramToken, setInstagramToken] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');

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
      instagram_token: instagramToken || null,
      openai_api_key: openaiKey || null,
      auto_mode: 'auto',
    });
    setMessage('Cuenta creada ✅');
    setHandle('');
    setInstagramToken('');
    setOpenaiKey('');
    await loadAccounts();
  }

  async function syncAccount() {
    if (!selectedAccountId) return;
    try {
      const { data } = await api.post(`/api/dashboard/${selectedAccountId}/sync`);
      const auto = data.auto_reply || {};
      setMessage(`Sync OK ✅ posts:${data.created_posts ?? 0} comments:${data.created_comments ?? 0} | auto sent:${auto.sent ?? 0} skipped:${auto.skipped ?? 0} failed:${auto.failed ?? 0}`);
      await loadDashboard(selectedAccountId);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const reason = detail?.reason || err?.response?.data?.reason || 'unknown_error';
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
      <div className="login-wrap">
        <main className="card login-card">
          <h1 className="title">Social Auto Reply</h1>
          <p className="subtitle">Accede al panel para gestionar cuentas y respuestas.</p>
          <label className="label">Email</label>
          <input className="input" placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <label className="label">Password</label>
          <input className="input" placeholder="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn" onClick={register}>Register</button>
            <button className="btn ghost" onClick={login}>Login</button>
          </div>
        </main>
      </div>
    );
  }

  const posts = dashboard?.latest_posts || [];
  const reels = dashboard?.latest_reels || [];
  const comments = dashboard?.latest_comments || [];
  const replies = dashboard?.latest_replies || [];

  return (
    <main className="app">
      <div className="header">
        <div>
          <h1 className="title">Dashboard</h1>
          <p className="subtitle">Gestiona cuentas, sincroniza Instagram y revisa actividad reciente.</p>
        </div>
        <button className="btn ghost" onClick={() => setAuthToken(null)}>Logout</button>
      </div>

      <p className="status">{message}</p>

      <section className="grid">
        <article className="card">
          <h2>Nueva cuenta social</h2>
          <label className="label">Plataforma + Instagram User ID (numérico)</label>
          <div className="row">
            <select className="select" value={platform} onChange={(e) => setPlatform(e.target.value)}>
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
              <option value="x">X</option>
            </select>
            <input className="input" placeholder="IG User ID o Page ID (numérico)" value={handle} onChange={(e) => setHandle(e.target.value)} />
          </div>

          <label className="label">Prompt de personalidad</label>
          <textarea className="textarea" value={persona} onChange={(e) => setPersona(e.target.value)} />

          <label className="label">Instagram Access Token</label>
          <input className="input" placeholder="IGAA..." value={instagramToken} onChange={(e) => setInstagramToken(e.target.value)} />

          <label className="label">OpenAI API Key</label>
          <input className="input" placeholder="sk-..." value={openaiKey} onChange={(e) => setOpenaiKey(e.target.value)} />

          <button className="btn" style={{ marginTop: 10 }} onClick={createAccount}>Guardar cuenta</button>
        </article>

        <article className="card">
          <h2>Cuentas conectadas</h2>
          <div className="account-list">
            {accounts.map((acc) => (
              <div className="account-item" key={acc.id}>
                <div>
                  <strong>{acc.platform}</strong> · {acc.account_handle}
                  <div className="meta">#{acc.id}</div>
                </div>
                <button className="btn ghost" onClick={() => { setSelectedAccountId(acc.id); loadDashboard(acc.id); }}>
                  Abrir
                </button>
              </div>
            ))}
          </div>
          <button className="btn success" style={{ marginTop: 10 }} onClick={syncAccount} disabled={!selectedAccountId}>
            Sync real Instagram
          </button>
        </article>
      </section>

      <section className="card" style={{ marginTop: 16 }}>
        <div className="kpis">
          <div className="kpi"><div className="n">{posts.length}</div><div className="t">Últimas publicaciones</div></div>
          <div className="kpi"><div className="n">{reels.length}</div><div className="t">Últimos reels</div></div>
          <div className="kpi"><div className="n">{comments.length}</div><div className="t">Últimos comentarios</div></div>
          <div className="kpi"><div className="n">{replies.length}</div><div className="t">Últimas respuestas</div></div>
        </div>

        <section className="grid">
          <article>
            <h2>Publicaciones</h2>
            <ul className="list">{posts.map((x: any) => <li key={x.id}>{x.text || '(sin caption)'}<div className="small">{x.created_at}</div></li>)}</ul>
          </article>
          <article>
            <h2>Reels</h2>
            <ul className="list">{reels.map((x: any) => <li key={x.id}>{x.text || '(sin caption)'}<div className="small">{x.created_at}</div></li>)}</ul>
          </article>
          <article>
            <h2>Comentarios</h2>
            <ul className="list">
              {comments.map((x: any) => {
                const internalCommentId = x.comment_id ?? (Number.isFinite(Number(x.id)) ? Number(x.id) : null);
                return (
                  <li key={`${x.id}-${x.comment_id ?? 'na'}`}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
                      <div style={{ flex: 1 }}>
                        <div>{x.text}</div>
                        <div className="small">{x.created_at}</div>
                      </div>
                      <button
                        className="btn ghost"
                        onClick={() => internalCommentId && generateReply(Number(internalCommentId))}
                        disabled={!internalCommentId}
                        title={internalCommentId ? 'Generar respuesta para este comentario' : 'Falta comment_id interno; haz rebuild y sync'}
                      >
                        Generar respuesta
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </article>
          <article>
            <h2>Respuestas</h2>
            <ul className="list">{replies.map((x: any) => <li key={x.id}>{x.text}<div className="small">{x.created_at}</div></li>)}</ul>
          </article>
        </section>
      </section>
    </main>
  );
}
