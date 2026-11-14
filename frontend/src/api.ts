import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 45000,
})

api.interceptors.request.use((config) => {
  // A login attempt must not inherit an expired token saved by a previous session.
  const isLoginRequest = /\/auth\/login\/?$/.test(config.url || '')
  if (isLoginRequest) {
    config.headers.delete('Authorization')
    return config
  }

  const token = localStorage.getItem('kfd_token')
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  } else {
    config.headers.delete('Authorization')
  }

  return config
})

// Do not clear the session here. A 401 can also come from a downstream
// Keycloak request; only /auth/me can establish that the local session is invalid.
export default api
