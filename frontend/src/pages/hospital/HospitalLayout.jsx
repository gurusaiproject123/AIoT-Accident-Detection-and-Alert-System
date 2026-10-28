import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation } from "react-router";
import { useHospital } from "./HospitalContext";
import { HOSPITAL, NAV, date, isAwaitingAcknowledgment } from "./data";
import { Icon, ResponseCountdown, ResponseConfirmation } from "./components/ui";
import Background from "./components/Background";

export default function HospitalLayout({ embedded = false }) {
  const {
    motion,
    sound,
    enableSound,
    newCount,
    clock,
    notice,
    setNotice,
    incidents,
  } = useHospital();
  const [menu, setMenu] = useState(false);
  const heading = useRef(null);
  const { pathname } = useLocation();
  const segment = pathname.replace(/\/$/, "").split("/")[2] || "overview";
  const page = NAV.some((n) => n[0] === segment) ? segment : "not-found";
  const isDetail =
    page === "incidents" && pathname.split("/").filter(Boolean).length > 2;
  const title = isDetail
    ? "Incident details"
    : {
        overview: "Hospital overview",
        incidents: "Assigned incidents",
        operations: "Hospital operations",
        health: "Locations and health",
        reports: "Hospital reports",
        "not-found": "Page not found",
      }[page];
  const subtitle =
    {
      overview: "Every alert matters. Stay informed, respond with confidence.",
      incidents: "Review and respond to incidents assigned to your hospital.",
      operations: "Review hospital actions and manage workspace preferences.",
      health:
        "Check location availability and hospital-relevant connection status.",
      reports:
        "Understand your hospital’s activity and export incident records.",
    }[page] || "";
  useEffect(() => {
    heading.current?.focus();
  }, [pathname]);
  return (
    <div
      className={`hd-app ${!motion ? "hd-motion-off" : ""} ${embedded ? "hd-embedded" : ""}`}
    >
      <Background />
      <a className="hd-skip" href="#hd-content">
        Skip to content
      </a>
      {menu && (
        <button
          className="hd-mobile-scrim"
          onClick={() => setMenu(false)}
          aria-label="Close navigation"
        />
      )}
      <aside className={`hd-sidebar ${menu ? "hd-sidebar-open" : ""}`}>
        <Link to="/hospital" className="hd-brand">
          <span className="hd-brand-mark">
            <Icon name="pulse" size={27} />
          </span>
          <span>
            AIoT<span className="hd-brand-light"> RESPONSE</span>
            <small>HOSPITAL WORKSPACE</small>
          </span>
        </Link>
        <div className="hd-hospital-switch">
          <span className="hd-hospital-icon">
            <Icon name="hospital" />
          </span>
          <div>
            <strong>{HOSPITAL.name}</strong>
            <small>{HOSPITAL.id} · Hospital staff</small>
          </div>
          <Icon name="shield" size={15} />
        </div>
        <span className="hd-nav-label">WORKSPACE</span>
        <nav aria-label="Hospital navigation" onClick={() => setMenu(false)}>
          {NAV.map(([key, label, icon]) => (
            <Link
              key={key}
              to={key === "overview" ? "/hospital" : `/hospital/${key}`}
              className={`hd-nav-item ${page === key ? "is-active" : ""}`}
              aria-current={page === key ? "page" : undefined}
            >
              <Icon name={icon} />
              <span>{label}</span>
              {key === "incidents" && newCount > 0 && <b>{newCount}</b>}
            </Link>
          ))}
        </nav>
        <div className="hd-sidebar-bottom">
          <div className="hd-sidebar-note">
            <Icon name="shield" />
            <strong>Your hospital. Your incidents.</strong>
            <p>This workspace shows incidents assigned to {HOSPITAL.name}.</p>
          </div>
          <div className="hd-user">
            <span className="hd-avatar">BH</span>
            <div>
              <strong>Response operator</strong>
              <small>Demo hospital account</small>
            </div>
            <span className="hd-user-dot" />
          </div>
        </div>
      </aside>
      <div className="hd-workspace">
        <header className="hd-topbar">
          <div className="hd-topbar-left">
            <button
              className="hd-icon-button hd-menu-button"
              onClick={() => setMenu(!menu)}
              aria-label="Toggle navigation"
              aria-expanded={menu}
            >
              <Icon name="menu" />
            </button>
            <span className="hd-breadcrumb">
              Workspace <Icon name="arrow" size={12} />{" "}
              <strong>
                {NAV.find((n) => n[0] === page)?.[1] || "Not found"}
              </strong>
            </span>
          </div>
          <div className="hd-topbar-right">
            <span className="hd-demo-label">
              <span /> DEMO WORKSPACE
            </span>
            <button
              className={`hd-sound-button ${sound ? "is-enabled" : ""}`}
              onClick={enableSound}
              aria-label={sound ? "Test alarm" : "Activate audio"}
            >
              <Icon name="sound" size={16} />
              <span>{sound ? "Test alarm" : "Activate audio"}</span>
            </button>
            <Link
              to="/hospital/incidents"
              className="hd-notification"
              aria-label={`${newCount} new alerts`}
            >
              <Icon name="bell" />
              {newCount > 0 && <span />}
            </Link>
            <span className="hd-avatar hd-avatar-small">BH</span>
          </div>
        </header>
        <main id="hd-content" className="hd-main">
          <div className="hd-page-heading">
            <div>
              <p className="hd-eyebrow">
                {HOSPITAL.name.toUpperCase()} / EMERGENCY RESPONSE
              </p>
              <h1 ref={heading} tabIndex="-1">
                {title}
                <span>.</span>
              </h1>
              <p className="hd-subtitle">{subtitle}</p>
            </div>
            <div className="hd-heading-date">
              <Icon name="clock" size={15} />
              {date(clock)} ·{" "}
              {new Date(clock).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </div>
          </div>
          {newCount > 0 && (
            <section
              className={`hd-alarm-banner ${sound ? "hd-alarm-active" : ""}`}
              aria-label="Alarm status"
            >
              <Icon name="bell" size={20} />
              <div>
                <strong>
                  {newCount} unacknowledged{" "}
                  {newCount === 1 ? "alert" : "alerts"}
                </strong>
                <p>
                  {sound
                    ? "Alarm ringing. Acknowledge all new incidents to stop it."
                    : "Alarm armed. Click anywhere once to activate browser audio."}
                </p>
              </div>
              <button
                className="hd-button hd-button-danger-outline"
                onClick={enableSound}
              >
                {sound ? "Test alarm" : "Activate audio"}
              </button>
            </section>
          )}
          {incidents.some(isAwaitingAcknowledgment) && (
            <section
              className="hd-deadline-panel"
              aria-label="Hospital response countdowns"
            >
              <div>
                <strong>Acknowledgment countdown</strong>
                <p>
                  Acknowledge within 3 minutes. Acknowledgment stops both the
                  alarm and countdown.
                </p>
              </div>
              <div className="hd-deadline-items">
                {incidents.filter(isAwaitingAcknowledgment).map((i) => (
                  <Link key={i.id} to={`/hospital/incidents/${i.id}`}>
                    <span>{i.id}</span>
                    <ResponseCountdown incident={i} />
                  </Link>
                ))}
              </div>
            </section>
          )}
          <div key={pathname}>
            <Outlet />
          </div>{" "}
          <footer className="hd-footer">
            <span>
              <Icon name="shield" size={13} /> AIoT Accident Detection & Alert
              System
            </span>
            <span>Demo data · No live emergency service connection</span>
          </footer>
        </main>
      </div>
      <ResponseConfirmation />
      {notice && (
        <div className="hd-toast" role="status">
          <Icon name="check" size={18} />
          {notice}
          <button onClick={() => setNotice("")} aria-label="Dismiss message">
            <Icon name="close" size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
