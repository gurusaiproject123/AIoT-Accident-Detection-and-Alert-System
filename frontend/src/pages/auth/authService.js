import { normalizeVerifiedProfile } from './accountRules.js';

export async function fetchVerifiedProfile(session, { baseUrl, signal, fetcher = fetch }) {
  if (!session?.access_token || !session.user?.id) throw new Error('Sign in again to verify your session.');
  const response = await fetcher(`${baseUrl.replace(/\/$/, '')}/api/auth/me`, {
    method:'GET', headers:{ Authorization:`Bearer ${session.access_token}` }, signal, cache:'no-store',
  });
  if (response.status === 401) throw new Error('Your session could not be verified. Sign out and sign in again.');
  if (response.status === 403) throw new Error('This account does not have active system access. Contact the administrator.');
  if (!response.ok) throw new Error('The account verification service is unavailable. Please retry.');
  let raw;
  try { raw=await response.json(); } catch { throw new Error('The server returned invalid account information.'); }
  return normalizeVerifiedProfile(raw, session.user.id);
}

export function signInError(error) {
  if (error?.code === 'email_not_confirmed') return 'Confirm your email before signing in, or contact your administrator.';
  if (error?.status === 429 || error?.code === 'over_request_rate_limit') return 'Too many attempts. Wait a moment before trying again.';
  if (error?.code === 'invalid_credentials' || error?.status === 400) return 'The email or password is incorrect.';
  return 'Could not sign in. Check your connection and try again.';
}
