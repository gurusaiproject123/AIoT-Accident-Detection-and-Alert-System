import { useEffect, useRef, useState } from "react";
import "./Login.css";

const PREVIEW_SESSION_KEY = "aiot.preview.signedIn";
const PREVIEW_DELAY_MILLISECONDS = 800;

function restorePreviewState() {
  try {
    return localStorage.getItem(PREVIEW_SESSION_KEY) === "true"
      ? { status: "success", message: "Demo sign-in restored. No real account is authenticated." }
      : { status: "idle", message: "" };
  } catch {
    return { status: "error", message: "Browser storage is unavailable. Enable local storage to use the demo." };
  }
}

export default function Login() {
  const [showPassword, setShowPassword] = useState(false);
  const [feedback, setFeedback] = useState(restorePreviewState);
  const pendingSignIn = useRef(null);
  const isSigningIn = feedback.status === "loading";

  useEffect(() => () => clearTimeout(pendingSignIn.current), []);

  function handleSubmit(event) {
    event.preventDefault();
    if (pendingSignIn.current !== null) return;

    const form = event.currentTarget;
    const credentials = new FormData(form);
    const matchesDemoAccount = credentials.get("email").trim().toLowerCase() === "demo@example.org"
      && credentials.get("password") === "DemoPreview123!";

    setFeedback({ status: "loading", message: "Checking demo credentials…" });
    // Simulate latency for the UI only. This does not authenticate a real user.
    pendingSignIn.current = setTimeout(() => {
      pendingSignIn.current = null;
      if (!matchesDemoAccount) {
        setFeedback({ status: "error", message: "Incorrect demo email or password. Use the demo credentials shown below." });
        return;
      }
      try {
        localStorage.setItem(PREVIEW_SESSION_KEY, "true");
        form.reset();
        setShowPassword(false);
        setFeedback({ status: "success", message: "Demo sign-in successful. No real account is authenticated." });
      } catch {
        setFeedback({ status: "error", message: "Could not save the demo session. Browser storage may be blocked or full. Enable storage and try again." });
      }
    }, PREVIEW_DELAY_MILLISECONDS);
  }

  function clearPreviewSession() {
    try {
      localStorage.removeItem(PREVIEW_SESSION_KEY);
      setFeedback({ status: "idle", message: "Demo session cleared." });
    } catch {
      setFeedback({ status: "error", message: "Could not clear the demo session. Check your browser storage settings." });
    }
  }

  return (
    <div className="login-layout">
      <section className="login-introduction" aria-labelledby="system-name">
        <span className="login-brand">AIoT</span>
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
          <form onSubmit={handleSubmit} aria-busy={isSigningIn}>
            <label htmlFor="email">Email address</label>
            <input id="email" name="email" type="email" autoComplete="username" placeholder="you@hospital.org" disabled={isSigningIn} required />
            <label htmlFor="password">Password</label>
            <div className="login-password">
              <input id="password" name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" placeholder="Enter your password" disabled={isSigningIn} required />
              <button type="button" className="login-password-toggle" aria-controls="password" aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            <div className={`login-message login-message--${feedback.status}`} role="status" aria-live="polite">{feedback.message}</div>
            <button className="login-submit" type="submit" disabled={isSigningIn}>{isSigningIn ? "Signing in…" : "Sign in"} <span aria-hidden="true">→</span></button>
          </form>
          <div className="login-demo">
            <p>Demo only — use <strong>demo@example.org</strong> with password <strong>DemoPreview123!</strong>. Any other credentials show an error.</p>
            <button type="button" onClick={clearPreviewSession} disabled={isSigningIn}>Clear demo session</button>
          </div>
          <p className="login-support">Need an account or help signing in?<br />Contact your system administrator.</p>
          <p className="login-preview"><span aria-hidden="true">◌</span> UI preview · Authentication is not connected</p>
        </div>
        <p className="login-form-footer">Accident Detection & Alert System</p>
      </section>
    </div>
  );
}
