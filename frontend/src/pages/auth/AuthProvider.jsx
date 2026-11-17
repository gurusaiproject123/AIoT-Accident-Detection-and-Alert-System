import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AuthContext } from './useAuth';
import { API_BASE_URL, getAuthClient } from './authClient';
import { fetchVerifiedProfile, signInError } from './authService';

export default function AuthProvider({ children, client: sharedClient, apiBaseUrl = API_BASE_URL }) {
  const config = useMemo(() => {
    try { return { client:sharedClient ?? getAuthClient(apiBaseUrl), error:null }; }
    catch { return { client:null, error:'Authentication is not configured. Check the FastAPI connection.' }; }
  }, [sharedClient, apiBaseUrl]);
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
    if (session.password_change_required) {
      setState({session,profile:null,loading:false,error:null});
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    // Rechecking the same account must not unmount the active dashboard.
    // Initial access and account changes still wait for backend verification.
    setState(previous => {
      const keepProfile = previous.profile && !previous.error &&
        previous.session?.user?.id === session.user?.id;
      return {
        session,
        profile: keepProfile ? previous.profile : null,
        loading: !keepProfile,
        error: null,
      };
    });
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
  useEffect(() => {
    if (!config.client) return;
    const endPageSession = () => {
      // Clear UI access immediately; unload-time network requests are best effort.
      void applySession(null);
      void config.client.auth.stopAutoRefresh();
      void config.client.auth.signOut({scope:'local'}).catch(() => {});
    };
    const restorePage = event => {
      // Browser Back may restore a whole page from memory instead of loading it.
      if (event.persisted) window.location.reload();
    };
    window.addEventListener('pagehide', endPageSession);
    window.addEventListener('pageshow', restorePage);
    return () => {
      window.removeEventListener('pagehide', endPageSession);
      window.removeEventListener('pageshow', restorePage);
    };
  }, [config.client, applySession]);
  const retryAccess=useCallback(()=>applySession(currentSession.current),[applySession]);
  const changePassword=useCallback(async(oldPassword,newPassword)=>{
    const session=await config.client.auth.changePassword(oldPassword,newPassword);
    await applySession(session);
  },[config.client,applySession]);
  const value=useMemo(()=>({...state,configured:Boolean(config.client),signIn,signOut,retryAccess,changePassword}),[state,config.client,signIn,signOut,retryAccess,changePassword]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
