const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export const ADMIN_ENDPOINTS = {
  overview: "/api/admin/overview",
  incidents: "/api/admin/incidents",
  incident: (id) => `/api/admin/incidents/${encodeURIComponent(id)}`,
  routeIncident: (id) => `/api/admin/incidents/${encodeURIComponent(id)}/notify`,
  closeIncident: (id) => `/api/admin/incidents/${encodeURIComponent(id)}/close`,
  devices: "/api/admin/devices",
  hospitals: "/api/admin/hospitals",
  hospital: (id) => `/api/admin/hospitals/${encodeURIComponent(id)}`,
  users: "/api/admin/users",
  user: (id) => `/api/admin/users/${encodeURIComponent(id)}`,
  audit: "/api/admin/audit",
};

/**
 * Minimal authenticated fetch wrapper.
 * @param {string} path      Endpoint path from ADMIN_ENDPOINTS.
 * @param {string} token     Supabase session access token.
 * @param {RequestInit} init Optional fetch options.
 */
export async function adminRequest(path, token, init = {}) {
  const response = await fetch(`${API_BASE.replace(/\/$/, "")}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail)
      ? detail.map(({loc, msg}) => `${loc?.at(-1) ?? "Field"}: ${msg}`).join("; ")
      : `Request failed (HTTP ${response.status}).`);
  }
  return response.status === 204 ? null : response.json();
}

export const getOverview = (token) => adminRequest(ADMIN_ENDPOINTS.overview, token);
export const getIncidents = (token) => adminRequest(ADMIN_ENDPOINTS.incidents, token);
export const getIncident = (token, id) => adminRequest(ADMIN_ENDPOINTS.incident(id), token);
export const getDevices = (token) => adminRequest(ADMIN_ENDPOINTS.devices, token);
export const getHospitals = (token) => adminRequest(ADMIN_ENDPOINTS.hospitals, token);
export const getUsers = (token) => adminRequest(ADMIN_ENDPOINTS.users, token);
export const getAudit = (token) => adminRequest(ADMIN_ENDPOINTS.audit, token);

export const createHospital = (token, body) =>
  adminRequest(ADMIN_ENDPOINTS.hospitals, token, { method: "POST", body: JSON.stringify(body) });
export const updateHospital = (token, id, body) =>
  adminRequest(ADMIN_ENDPOINTS.hospital(id), token, { method: "PATCH", body: JSON.stringify(body) });
export const updateUser = (token, id, body) =>
  adminRequest(ADMIN_ENDPOINTS.user(id), token, { method: "PATCH", body: JSON.stringify(body) });
export const routeIncident = (token, id, hospitalId) =>
  adminRequest(ADMIN_ENDPOINTS.routeIncident(id), token, {
    method: "POST",
    body: JSON.stringify({ hospital_id: hospitalId }),
  });
export const closeIncident = (token, id, note) =>
  adminRequest(ADMIN_ENDPOINTS.closeIncident(id), token, {
    method: "POST",
    body: JSON.stringify({ note }),
  });


/** Provision a Supabase account through FastAPI. Never persist passwords. */
export function createUser(token, { name, email, role, hospitalId, ownerId, password }) {
  if (!token) throw new Error("A verified administrator session is required.");
  if (!["hospital_staff","car_owner"].includes(role)) throw new Error("Unsupported user role.");
  if (role === "hospital_staff" && !hospitalId) throw new Error("Select one hospital.");
  if (role !== "hospital_staff" && hospitalId) throw new Error("This account type has no hospital assignment.");
  if (role === "car_owner" && !ownerId) throw new Error("Select the registered owner.");
  if (!password) throw new Error("An email/password account requires a password.");
  return adminRequest(ADMIN_ENDPOINTS.users, token, {
    method:"POST", body:JSON.stringify({full_name:name,email,role,hospital_id:hospitalId ?? null,owner_id:role === "car_owner" ? ownerId : null,password}),
  });
}

export async function getAll(path, token, signal) {
  const items = [];
  for (let offset = 0; ; ) {
    const page = await adminRequest(`${path}?limit=100&offset=${offset}`, token, {signal});
    if (!Array.isArray(page?.items)) throw new Error("The server returned an invalid list.");
    items.push(...page.items);
    offset += page.items.length;
    if (!page.items.length || offset >= page.total) return items;
  }
}
