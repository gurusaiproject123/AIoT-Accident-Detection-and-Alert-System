import { useState } from "react";
import "./Login.css";

export default function Login() {
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    // UI placeholder: no credentials are sent, stored, or used to grant access.
    setMessage("This is a design preview. Sign-in is not connected yet. See auth.md for setup steps.");
  }

  return (
    <div className="login-layout">
      <section className="login-introduction" aria-labelledby="system-name">
        <span className="login-brand">AI GURUS <span> / AIoT</span></span>
        <div className="login-story">
          <span className="login-eyebrow">CONNECTED VEHICLES. COORDINATED CARE.</span>
          <h1 id="system-name">AIoT Accident Detection and Alert System</h1>
          <p>A shared workspace for hospital teams and system administrators to coordinate incident response.</p>
          <div className="login-capabilities">
            <span>01 <strong>Incident awareness</strong></span>
            <span>02 <strong>Hospital coordination</strong></span>
            <span>03 <strong>System oversight</strong></span>
          </div>
        </div>
        <p className="login-intro-footer">Built for the moments that matter.</p>
      </section>

      <section className="login-form-section" aria-labelledby="login-heading">
        <div className="login-card">
          <p className="login-eyebrow">TEAM ACCESS</p>
          <h2 id="login-heading">Welcome back</h2>
          <p className="login-description">Sign in with your assigned work account.</p>
          <form onSubmit={handleSubmit} onChange={() => setMessage("")}>
            <label htmlFor="email">Email address</label>
            <input id="email" name="email" type="email" autoComplete="username" placeholder="you@hospital.org" required />
            <label htmlFor="password">Password</label>
            <div className="login-password">
              <input id="password" name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" placeholder="Enter your password" required />
              <button type="button" className="login-password-toggle" aria-controls="password" aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            <div className="login-message" role="status" aria-live="polite">{message}</div>
            <button className="login-submit" type="submit">Sign in <span aria-hidden="true">→</span></button>
          </form>
          <p className="login-support">Need an account or help signing in?<br />Contact your system administrator.</p>
          <p className="login-preview"><span aria-hidden="true">◌</span> UI preview · Authentication is not connected</p>
        </div>
        <p className="login-form-footer">AI GURUS · Accident Detection & Alert System</p>
      </section>
    </div>
  );
}
