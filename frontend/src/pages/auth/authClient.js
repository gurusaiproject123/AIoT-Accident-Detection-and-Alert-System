import { API_BASE_URL } from '../../config/api';
import { createLocalClient } from './localClient';

export { API_BASE_URL };

const clients = new Map();
export function getAuthClient(baseUrl = API_BASE_URL) {
  const base = baseUrl.replace(/\/$/, '');
  if (!clients.has(base)) clients.set(base, createLocalClient(base));
  return clients.get(base);
}
