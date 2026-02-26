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
    });
    setMessage('Cuenta creada ✅');
    setHandle('');
    setInstagramToken('');
    setOpenaiKey('');
    await loadAccounts();
  }

  async function syncAccount() {
    if (!selectedAccountId) return;
    await api.post(`/api/dashboard/${selectedAccountId}/sync`);
    setMessage('Sincronización mock completada ✅');
    await loadDashboard(selectedAccountId);
  }

  async function loadDashboard(accountId: number) {
    const { data } = await api.get(`/api/dashboard/${accountId}`);
    setDashboard(data);
  }

  if (!token) {
    return (
      <main style={{ maxWidth: 500, margin: '40px auto', fontFamily: 'sans-serif' }}>
        <h1>Social Auto Reply</h1>
        <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} style={{ display: 'block', width: '100%', marginBottom: 8 }} />
        <input placeholder="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} style={{ display: 'block', width: '100%', marginBottom: 8 }} />
        <button onClick={register}>Register</button>{' '}
        <button onClick={login}>Login</button>
      </main>
    );
  }

  return (
    <main style={{ padding: 24, fontFamily: 'sans-serif' }}>
      <h1>Dashboard</h1>
      <button onClick={() => setAuthToken(null)}>Logout</button>
      <p>{message}</p>

      <section style={{ border: '1px solid #ddd', padding: 12, marginTop: 12 }}>
        <h2>Nueva cuenta social</h2>
        <select value={platform} onChange={(e) => setPlatform(e.target.value)}>
          <option value="instagram">Instagram</option>
          <option value="facebook">Facebook</option>
          <option value="x">X</option>
        </select>
        <input placeholder="@handle" value={handle} onChange={(e) => setHandle(e.target.value)} style={{ marginLeft: 8 }} />
        <br /><br />
        <textarea value={persona} onChange={(e) => setPersona(e.target.value)} rows={3} style={{ width: '100%' }} />
        <input placeholder="Instagram token" value={instagramToken} onChange={(e) => setInstagramToken(e.target.value)} style={{ display: 'block', width: '100%', marginTop: 8 }} />
        <input placeholder="OpenAI API key" value={openaiKey} onChange={(e) => setOpenaiKey(e.target.value)} style={{ display: 'block', width: '100%', marginTop: 8 }} />
        <button onClick={createAccount} style={{ marginTop: 8 }}>Guardar cuenta</button>
      </section>

      <section style={{ border: '1px solid #ddd', padding: 12, marginTop: 12 }}>
        <h2>Cuentas</h2>
        <ul>
          {accounts.map((acc) => (
            <li key={acc.id}>
              <button onClick={() => { setSelectedAccountId(acc.id); loadDashboard(acc.id); }}>
                {acc.platform} - {acc.account_handle}
              </button>
            </li>
          ))}
        </ul>
        <button onClick={syncAccount} disabled={!selectedAccountId}>Sync mock</button>
      </section>

      {dashboard && (
        <section style={{ marginTop: 16 }}>
          <h2>Últimas publicaciones</h2>
          <pre>{JSON.stringify(dashboard.latest_posts, null, 2)}</pre>
          <h2>Últimos reels</h2>
          <pre>{JSON.stringify(dashboard.latest_reels, null, 2)}</pre>
          <h2>Últimos comentarios</h2>
          <pre>{JSON.stringify(dashboard.latest_comments, null, 2)}</pre>
          <h2>Últimas respuestas</h2>
          <pre>{JSON.stringify(dashboard.latest_replies, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}
