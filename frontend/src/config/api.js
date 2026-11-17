// The browser calls FastAPI; FastAPI owns the WAMP MySQL connection.
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.VITE_API_URL ??
  ''
).replace(/\/$/, '');
