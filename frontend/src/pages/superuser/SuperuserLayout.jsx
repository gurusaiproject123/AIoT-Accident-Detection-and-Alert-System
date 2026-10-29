import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import Icon from "./components/Icon";
import Background from "./components/Background";
import { Toasts } from "./components/ui";
import { useSuperuser } from "./useSuperuser";
import { BASE_PATH, NAV_ITEMS, formatRelative } from "./data";

const SECTION_LABELS = {
  "": "Overview",
  incidents: "Incidents",
  devices: "Devices",
  hospitals: "Hospitals",
  users: "Users and roles",
  activity: "Activity history",
};

function useBreadcrumb() {
  const { pathname } = useLocation();
  const parts = pathname.replace(BASE_PATH, "").split("/").filter(Boolean);
  const section = parts[0] ?? "";
  const crumbs = [{ label: SECTION_LABELS[section] ?? "Not found", to: `${BASE_PATH}/${section}` }];
  if (parts[1]) crumbs.push({ label: parts[1], to: null });
  return crumbs;
}

export default function SuperuserLayout({ embedded = false }) {
  const {
    incidents,
    hospitalById,
    stats,
    now,
    toasts,
    dismissToast,
    simulateIncident,
    preferences,
  } = useSuperuser();
  const [menuOpen, setMenuOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const bellRef = useRef(null);
  const crumbs = useBreadcrumb();
  const { pathname } = useLocation();
  const [routeKey, setRouteKey] = useState(pathname);

  // Close the mobile menu and bell after navigation (state adjusted during render).
  if (routeKey !== pathname) {
    setRouteKey(pathname);
    setMenuOpen(false);
    setBellOpen(false);
  }

  // Close the notification dropdown on outside click.
  useEffect(() => {
    if (!bellOpen) return undefined;
    const onClick = (event) => {
      if (bellRef.current && !bellRef.current.contains(event.target)) setBellOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [bellOpen]);

  const pending = incidents
    .filter((i) => !["closed", "cancelled"].includes(i.status))
    .flatMap((incident) =>
      incident.notifications
        .filter((n) => n.status === "notified")
        .map((n) => ({ incident, notification: n })),
    );

  const countdowns = incidents
    .filter((i) => i.status === "cancellation_window")
    .map((incident) => {
      const deadline =
        new Date(incident.detectedAt).getTime() + incident.cancellation.windowSeconds * 1000;
      return { incident, remaining: Math.max(0, Math.ceil((deadline - now) / 1000)) };
    });

  const animations = preferences?.animations !== false;

  return (
    <div
      className={`su-root ${embedded ? "is-embedded" : ""} ${animations ? "" : "no-motion"} ${
        menuOpen ? "menu-open" : ""
      }`}
    >
      {!embedded && (
        <aside className="su-sidebar" aria-label="Superuser navigation">
          <div className="su-brand">
            <span className="su-brand-mark">
              <Icon name="pulse" size={22} strokeWidth={2} />
            </span>
            <div>
              <strong>
                AIoT <span>RESPONSE</span>
              </strong>
              <small>System administration</small>
            </div>
            <button
              type="button"
              className="su-icon-btn su-sidebar-close"
              onClick={() => setMenuOpen(false)}
              aria-label="Close navigation"
            >
              <Icon name="x" />
            </button>
          </div>

          <div className="su-org-card">
            <span className="su-org-icon">
              <Icon name="shield" size={18} />
            </span>
            <div>
              <strong>System control</strong>
              <small>Superuser · No hospital assignment</small>
            </div>
            <Icon name="checkCircle" size={16} className="su-org-check" />
          </div>

          <p className="su-nav-label">Administration</p>
          <nav className="su-nav">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.label}
                to={item.to ? `${BASE_PATH}/${item.to}` : BASE_PATH}
                end={item.end}
                className={({ isActive }) => `su-nav-link ${isActive ? "is-active" : ""}`}
              >
                <Icon name={item.icon} size={18} />
                <span>{item.label}</span>
                {item.to === "incidents" && stats.pendingAlerts > 0 && (
                  <span className="su-nav-pill">{stats.pendingAlerts}</span>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="su-sidebar-note">
            <Icon name="shield" size={20} />
            <strong>Every hospital. Every alert.</strong>
            <p>
              This workspace oversees incidents, devices, hospitals and user roles across the
              whole system.
            </p>
          </div>

          <div className="su-user-card">
            <span className="su-avatar">SU</span>
            <div>
              <strong>System administrator</strong>
              <small>Demo superuser account</small>
            </div>
            <Link to="/login" className="su-icon-btn su-logout" aria-label="Open login (demo)" title="Open login; the demo has no authenticated session">
              <Icon name="logout" size={16} />
            </Link>
          </div>
        </aside>
      )}

      {menuOpen && <button type="button" className="su-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}

      <div className="su-main">
        <Background animated={animations} />

        <header className="su-topbar">
          <div className="su-topbar-left">
            {!embedded && (
              <button
                type="button"
                className="su-icon-btn su-menu-btn"
                onClick={() => setMenuOpen(true)}
                aria-label="Open navigation"
              >
                <Icon name="menu" />
              </button>
            )}
            <nav className="su-crumbs" aria-label="Breadcrumb">
              <Link to={BASE_PATH}>Administration</Link>
              {crumbs.map((crumb) => (
                <span key={crumb.label} className="su-crumb">
                  <Icon name="chevronRight" size={14} />
                  {crumb.to ? <Link to={crumb.to}>{crumb.label}</Link> : <span aria-current="page">{crumb.label}</span>}
                </span>
              ))}
            </nav>
          </div>

          <div className="su-topbar-right">
            <span className="su-demo-pill">
              <span className="su-live-dot" /> Demo workspace
            </span>
            <button type="button" className="su-btn su-btn-outline" onClick={simulateIncident}>
              <Icon name="play" size={15} />
              <span className="su-hide-sm">Simulate detection</span>
            </button>

            <div className="su-bell" ref={bellRef}>
              <button
                type="button"
                className="su-icon-btn"
                aria-label={`Pending hospital alerts: ${pending.length}`}
                aria-expanded={bellOpen}
                onClick={() => setBellOpen((open) => !open)}
              >
                <Icon name="bell" />
                {pending.length > 0 && <span className="su-bell-count">{pending.length}</span>}
              </button>
              {bellOpen && (
                <div className="su-dropdown">
                  <p className="su-dropdown-title">Awaiting hospital response</p>
                  {pending.length === 0 && <p className="su-dropdown-empty">No pending alerts.</p>}
                  {pending.map(({ incident, notification }) => (
                    <Link
                      key={`${incident.id}-${notification.hospitalId}`}
                      to={`${BASE_PATH}/incidents/${incident.id}`}
                      className="su-dropdown-item"
                    >
                      <span className="su-dropdown-icon">
                        <Icon name="bell" size={15} />
                      </span>
                      <span>
                        <strong>{incident.id}</strong>
                        <small>
                          {hospitalById[notification.hospitalId]?.name ?? notification.hospitalId} ·{" "}
                          {formatRelative(notification.notifiedAt, now)}
                        </small>
                      </span>
                    </Link>
                  ))}
                </div>
              )}
            </div>
            <span className="su-avatar su-avatar-light">SU</span>
          </div>
        </header>

        {countdowns.length > 0 && (
          <div className="su-alert-banner" role="alert">
            <Icon name="alert" size={18} />
            <div>
              {countdowns.map(({ incident, remaining }) => (
                <p key={incident.id}>
                  <strong>{incident.id}</strong> suspected accident from{" "}
                  <span className="su-mono">{incident.deviceId}</span> — 30-second false-alarm window:{" "}
                  <strong>{remaining}s</strong> remaining before hospitals are notified.
                </p>
              ))}
            </div>
            <Link to={`${BASE_PATH}/incidents/${countdowns[0].incident.id}`} className="su-btn su-btn-sm su-btn-light">
              Follow incident
            </Link>
          </div>
        )}

        <main className="su-content" id="superuser-content">
          <Outlet />
        </main>

        <footer className="su-footer">
          Academic prototype · all incidents, hospitals, devices and contacts are simulated.
        </footer>
      </div>

      <Toasts toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

