import { useEffect, useMemo, useState } from 'react';
import { api, setToken } from '../services/api';

export function App() {
  const [token, setAuthToken] = useState<string | null>(localStorage.getItem('token'));
  const [accountId, setAccountId] = useState<number | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [syncPayload, setSyncPayload] = useState<any>(null);

  const pushLog = (step: string, data: any) => {
    setLogs((prev) => [...prev, { ts: new Date().toISOString(), step, data }]);
  };

  useEffect(() => {
    setToken(token);
    if (token) {
      localStorage.setItem('token', token);
      api
        .get('/api/accounts')
        .then(({ data }) => {
          pushLog('accounts', data);
          if (data?.length) setAccountId(data[0].id);
        })
        .catch((err) => pushLog('accounts_error', err?.response?.data || err?.message));
    } else {
      localStorage.removeItem('token');
      setAccountId(null);
    }
  }, [token]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const data = event.data || {};
      if (typeof data.token !== 'string') return;
      setAuthToken(data.token);
      if (data.social_account_id) setAccountId(Number(data.social_account_id));
      if (data.oauth_debug) pushLog('oauth_callback', data.oauth_debug);
      pushLog('session_token', data.token);
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  const login = async () => {
    try {
      const { data } = await api.post('/api/auth/instagram/start', { handle: 'instagram' });
      pushLog('oauth_start_url', data);
      window.open(data.url, 'ig-login', 'width=650,height=800');
    } catch (err: any) {
      pushLog('oauth_start_error', err?.response?.data || err?.message);
    }
  };

  const sync = async () => {
    if (!accountId) return;
    try {
      const { data } = await api.post(`/api/dashboard/${accountId}/sync`);
      setSyncPayload(data);
      pushLog('sync', data);
      const dashboard = await api.get(`/api/dashboard/${accountId}`);
      pushLog('dashboard', dashboard.data);
    } catch (err: any) {
      pushLog('sync_error', err?.response?.data || err?.message);
    }
  };

  const prettyLogs = useMemo(() => JSON.stringify(logs, null, 2), [logs]);
  const prettySync = useMemo(() => JSON.stringify(syncPayload, null, 2), [syncPayload]);

  if (!token) {
    return (
      <div style={{ padding: 20, fontFamily: 'monospace' }}>
        <h2>Login</h2>
        <button onClick={login}>
          Logearse con Facebook
        </button>
        <h3>Log JSON</h3>
        <pre style={{ whiteSpace: 'pre-wrap' }}>{prettyLogs}</pre>
      </div>
    );
  }

  return (
    <div style={{ padding: 20, fontFamily: 'monospace' }}>
      <h2>Workflow directo</h2>
      <div style={{ marginBottom: 12 }}>
        <button onClick={sync} disabled={!accountId}>
          Sync
        </button>{' '}
        <button onClick={() => setAuthToken(null)}>Cerrar sesión</button>
      </div>

      <h3>Salida sync (JSON)</h3>
      <pre style={{ whiteSpace: 'pre-wrap' }}>{prettySync || '{}'}</pre>

      <h3>Eventos (JSON)</h3>
      <pre style={{ whiteSpace: 'pre-wrap' }}>{prettyLogs}</pre>
    </div>
  );
}
