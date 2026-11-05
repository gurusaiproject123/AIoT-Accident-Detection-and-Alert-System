import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from './useAuth';
import { homeForProfile } from './accountRules';
import './Login.css';

export default function Login() {
  const auth=useAuth();
  const navigate=useNavigate();
  const [showPassword,setShowPassword]=useState(false);
  const [submitting,setSubmitting]=useState(false);
  const [feedback,setFeedback]=useState('');
  const pending=useRef(false);
  const busy=submitting || auth.loading;
  const disabled=busy || !auth.configured || Boolean(auth.session);
  const message=feedback || auth.error || (auth.loading ? 'Verifying account access…' : '');

  useEffect(()=>{
    if (auth.profile && !auth.loading && !auth.error) navigate(homeForProfile(auth.profile),{replace:true});
  },[auth.profile,auth.loading,auth.error,navigate]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (pending.current || disabled) return;
    const form=event.currentTarget;
    const values=new FormData(form);
    pending.current=true;setSubmitting(true);setFeedback('');
    try {
      await auth.signIn(String(values.get('email')??''),String(values.get('password')??''));
      form.reset();setShowPassword(false);
    } catch (error) {setFeedback(error.message ?? 'Could not sign in. Please try again.');}
    finally {pending.current=false;setSubmitting(false);}
  }

  return (
    <div className="login-layout">
      <section className="login-introduction" aria-labelledby="system-name">
        <span className="login-brand">AIoT</span>
        <div className="login-story">
          <span className="login-eyebrow">CONNECTED VEHICLES. COORDINATED CARE.</span>
          <h1 id="system-name">AIoT Accident Detection and Alert System</h1>
          <p>A shared system for hospital teams, vehicle owners and administrators to coordinate incident response.</p>
          <div className="login-capabilities">
            <span>01 <strong>Incident awareness</strong></span>
            <span>02 <strong>Hospital coordination</strong></span>
            <span>03 <strong>Owner access and system oversight</strong></span>
          </div>
        </div>
        <p className="login-intro-footer">Built for the moments that matter.</p>
      </section>
      <section className="login-form-section" aria-labelledby="login-heading">
        <div className="login-card">
          <p className="login-eyebrow">ACCOUNT ACCESS</p>
          <h2 id="login-heading">Welcome back</h2>
          <p className="login-description">Sign in with the email and password assigned to your account.</p>
          <form onSubmit={handleSubmit} aria-busy={busy}>
            <label htmlFor="email">Email address</label>
            <input id="email" name="email" type="email" autoComplete="username" placeholder="you@example.com" disabled={disabled} required />
            <label htmlFor="password">Password</label>
            <div className="login-password">
              <input id="password" name="password" type={showPassword?'text':'password'} autoComplete="current-password" placeholder="Enter your password" disabled={disabled} required />
              <button type="button" className="login-password-toggle" aria-controls="password" aria-pressed={showPassword} disabled={disabled} onClick={()=>setShowPassword(value=>!value)}>{showPassword?'Hide':'Show'}</button>
            </div>
            <div className={`login-message login-message--${message && !busy ? 'error':'idle'}`} role="status" aria-live="polite">{message}</div>
            <button className="login-submit" type="submit" disabled={disabled}>{busy?'Signing in…':'Sign in'} <span aria-hidden="true">→</span></button>
          </form>
          <div className="login-demo">
            {auth.session ? <>
              <p>Your identity is signed in. Dashboard access must also be verified.</p>
              <button type="button" disabled={busy} onClick={()=>{setFeedback('');void auth.retryAccess();}}>Retry account access</button>{' '}
              <button type="button" disabled={busy} onClick={()=>auth.signOut().catch(error=>setFeedback(error.message))}>Sign out / use another account</button>
            </> : <p>Accounts are created by the system administrator. Your verified role determines whether you open the hospital, superuser or separate vehicle interface.</p>}
          </div>
          <p className="login-support">Need an account or help signing in?<br />Contact your system administrator.</p>
          <p className="login-preview"><span aria-hidden="true">◌</span> {auth.configured?'Supabase configured · Access verified through FastAPI':'Setup required · Configure Supabase and the FastAPI connection'}</p>
        </div>
        <p className="login-form-footer">Accident Detection &amp; Alert System</p>
      </section>
    </div>
  );
}
