import { createClient } from '@supabase/supabase-js';

let singleton;
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '');

/** Lazy creation lets an app pass its existing shared client to AuthProvider. */
export function getSupabaseClient() {
  if (singleton) return singleton;
  const url = import.meta.env.VITE_SUPABASE_URL;
  const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ?? import.meta.env.VITE_SUPABASE_ANON_KEY;
  if (!url || !key) throw new Error('Configure the Supabase URL and publishable key in frontend/.env.local, then restart Vite.');
  if (key.startsWith('sb_secret_')) throw new Error('Use a Supabase publishable key in the frontend, never a secret key.');
  singleton = createClient(url, key, { auth:{ persistSession:true, autoRefreshToken:true, detectSessionInUrl:false } });
  return singleton;
}
