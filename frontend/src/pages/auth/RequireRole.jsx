import { useState } from 'react';
import { Navigate } from 'react-router';
import { useAuth } from './useAuth';
import { homeForProfile } from './accountRules';

/** UI guard only. FastAPI and RLS must authorize each request separately. */
export default function RequireRole({ roles, children }) {
  const {session,profile,loading,error,retryAccess,signOut}=useAuth();
  const [actionError,setActionError]=useState('');
  if (loading) return <p role="status">Verifying account access…</p>;
  if (!session) return <Navigate to="/login" replace />;
  if (error || !profile) return <section role="alert"><h1>Access could not be verified</h1><p>{actionError || error || 'Please retry account verification.'}</p>
    <button type="button" onClick={()=>void retryAccess()}>Retry</button>{' '}
    <button type="button" onClick={()=>signOut().catch(e=>setActionError(e.message))}>Sign out</button></section>;
  if (!roles.includes(profile.role)) return <Navigate to={homeForProfile(profile)} replace />;
  return children;
}
