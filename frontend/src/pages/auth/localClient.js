/** Memory-only local sessions: refresh/close requires a new login. */
export function createLocalClient(baseUrl) {
  let session = null;
  const listeners = new Set();
  const emit = event => listeners.forEach(callback => callback(event, session));
  async function request(path, body, token = session?.access_token, keepalive = false) {
    const response = await fetch(baseUrl + path, {
      method: 'POST', cache: 'no-store', keepalive,
      signal: AbortSignal.timeout(15000),
      headers: {'Content-Type':'application/json', ...(token ? {Authorization:`Bearer ${token}`} : {})},
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) throw Object.assign(new Error(result.detail || 'Local authentication failed.'), {status: response.status});
    return result;
  }
  return {auth: {
    onAuthStateChange(callback) { listeners.add(callback); return {data:{subscription:{unsubscribe:()=>listeners.delete(callback)}}}; },
    async getSession() {return {data:{session},error:null};},
    async signInWithPassword(credentials) {
      try { const result = await request('/api/auth/login', credentials); session = result.session; emit('SIGNED_IN'); return {data:{session},error:null}; }
      catch (error) {return {data:{session:null},error};}
    },
    async signOut() {
      const token = session?.access_token;
      session = null; emit('SIGNED_OUT');
      try {if (token) await request('/api/auth/logout', {}, token, true); return {error:null};}
      catch(error) {return {error};}
    },
    async changePassword(current_password, new_password) {
      await request('/api/auth/password', {current_password,new_password});
      session = {...session,password_change_required:false}; emit('USER_UPDATED');
      return session;
    },
    stopAutoRefresh() {},
  }};
}
