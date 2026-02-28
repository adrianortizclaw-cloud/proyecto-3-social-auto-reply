import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE,
});

export function setSessionHeader(sessionId: string | null) {
  if (!sessionId) {
    delete api.defaults.headers.common['X-Session-Id'];
    return;
  }
  api.defaults.headers.common['X-Session-Id'] = sessionId;
}
