import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AuthContext } from './useAuth';
import { API_BASE_URL, getSupabaseClient } from './supabaseClient';
import { fetchVerifiedProfile, signInError } from './authService';

export default function AuthProvider({ children, client: sharedClient, apiBaseUrl = API_BASE_URL }) {
  const config = useMemo(() => {
    try { return { client:sharedClient ?? getSupabaseClient(), error:null }; }
    catch { return { client:null, error:'Authentication is not configured. Set the Supabase URL/publishable key and restart Vite.' }; }
  }, [sharedClient]);
  const [state, setState] = useState({ session:null, profile:null, loading:Boolean(config.client), error:config.error });
  const mounted = useRef(false);
  const sequence = useRef(0);
  const request = useRef(null);
  const currentSession = useRef(null);

  const applySession = useCallback(async (session) => {
    if (!mounted.current) return;
    const version = ++sequence.current;
    request.current?.abort();
    currentSession.current = session;
    if (!session) { setState({ session:null, profile:null, loading:false, error:config.error }); return; }
    const controller = new AbortController();
    request.current = controller;
    setState({ session, profile:null, loading:true, error:null });
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    try {
      const profile = await fetchVerifiedProfile(session, {baseUrl:apiBaseUrl,signal:controller.signal});
      if (mounted.current && sequence.current===version) setState({session,profile,loading:false,error:null});
    } catch (error) {
      if (mounted.current && sequence.current===version) {
        const message = error?.name==='AbortError' ? 'Account verification timed out. Please retry.' :
          error instanceof TypeError ? 'Cannot reach the account verification server. Check FastAPI and your connection.' :
          error?.message ?? 'Could not verify account access. Please retry.';
        setState({session,profile:null,loading:false,error:message});
      }
    } finally { window.clearTimeout(timeout); }
  }, [apiBaseUrl, config.error]);

  useEffect(() => {
    mounted.current=true;
    let active=true;
    if (!config.client) { setState({session:null,profile:null,loading:false,error:config.error}); return () => {mounted.current=false;}; }
    const initialVersion=sequence.current;
    const { data:{subscription} } = config.client.auth.onAuthStateChange((_event,session) => {
      // Keep SDK callback synchronous; profile fetch is queued outside it.
      queueMicrotask(() => { if (active && mounted.current) void applySession(session); });
    });
    config.client.auth.getSession().then(({data,error}) => {
      if (!active || !mounted.current || sequence.current!==initialVersion) return;
      if (error) setState({session:null,profile:null,loading:false,error:'Could not restore your session. Sign in again.'});
      else void applySession(data.session);
    }).catch(() => {
      if (active && mounted.current && sequence.current===initialVersion) setState({session:null,profile:null,loading:false,error:'Could not restore your session. Sign in again.'});
    });
    return () => {active=false; mounted.current=false; ++sequence.current; request.current?.abort(); subscription.unsubscribe();};
  }, [config, applySession]);

  const signIn = useCallback(async (email,password) => {
    if (!config.client) throw new Error(config.error);
    const {data,error}=await config.client.auth.signInWithPassword({email:email.trim(),password});
    if (error) throw new Error(signInError(error));
    // Also verify explicitly in case an integration suppresses auth events.
    await applySession(data.session);
  }, [config,applySession]);
  const signOut = useCallback(async () => {
    if (!config.client) return;
    const {error}=await config.client.auth.signOut({scope:'local'});
    if (error) throw new Error('Sign-out could not be fully confirmed. Please retry.');
    await applySession(null);
  }, [config,applySession]);
  const retryAccess=useCallback(()=>applySession(currentSession.current),[applySession]);
  const value=useMemo(()=>({...state,configured:Boolean(config.client),signIn,signOut,retryAccess}),[state,config.client,signIn,signOut,retryAccess]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
