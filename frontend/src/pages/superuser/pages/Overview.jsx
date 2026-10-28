import { Link } from "react-router";
import Icon from "../components/Icon";
import { Badge, IncidentTable, PageHeading, Panel, PulseRing, StatCard } from "../components/ui";
import { useSuperuser } from "../useSuperuser";
import { BASE_PATH, INCIDENT_STATUS, formatRelative } from "../data";

const FLOW = [
  { key: "cancellation_window", label: "Cancellation window" },
  { key: "notified", label: "Notified" },
  { key: "escalated", label: "Escalated" },
  { key: "acknowledged", label: "Acknowledged" },
  { key: "accepted", label: "Accepted" },
  { key: "closed", label: "Closed" },
  { key: "cancelled", label: "Cancelled" },
];

export default function Overview() {
  const { incidents, devices, hospitals, audit, stats, now, preferences } = useSuperuser();

  const recent = [...incidents]
    .sort((a, b) => new Date(b.detectedAt) - new Date(a.detectedAt))
    .slice(0, 5);

  const countByStatus = incidents.reduce((acc, incident) => {
    acc[incident.status] = (acc[incident.status] ?? 0) + 1;
    return acc;
  }, {});

  const attention = incidents.filter(
    (i) =>
      i.status === "escalated" ||
      i.status === "cancellation_window" ||
      (i.status === "notified" &&
        i.notifications.some(
          (n) => n.status === "notified" && now - new Date(n.notifiedAt).getTime() > 5 * 60 * 1000,
        )),
  );

  const deviceCounts = {
    online: devices.filter((d) => d.status === "online").length,
    offline: devices.filter((d) => d.status === "offline").length,
    fault: devices.filter((d) => d.status === "fault").length,
    gpsIssues: devices.filter((d) => d.gps !== "fix").length,
  };

  const openByHospital = incidents
    .filter((i) => !["closed", "cancelled"].includes(i.status))
    .flatMap((i) => i.notifications.filter((n) => ["notified", "acknowledged", "accepted"].includes(n.status)))
    .reduce((acc, n) => ({ ...acc, [n.hospitalId]: (acc[n.hospitalId] ?? 0) + 1 }), {});

  const isAlerting = stats.pendingAlerts > 0 || countByStatus.cancellation_window > 0;
  const dateLabel = new Date(now).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

  return (
    <div className="su-page">
      <PageHeading
        eyebrow="AIoT Response / System administration"
        title="Superuser dashboard"
        subtitle="Every incident, device, hospital and user — overseen from one place."
        actions={
          <span className="su-date">
            <Icon name="clock" size={15} /> {dateLabel}
          </span>
        }
      />

      <section className="su-hero">
        <div className="su-hero-copy">
          <p className="su-hero-eyebrow">
            <span className={`su-live-dot ${isAlerting ? "is-red" : ""}`} />
            {isAlerting ? "Incidents need attention" : "All systems monitored"}
          </p>
          <h2>
            System oversight.
            <span>Faster coordination.</span>
          </h2>
          <p className="su-hero-text">
            Follow each suspected accident from detection to hospital response, keep devices
            healthy and manage who can act on every alert.
          </p>
          <div className="su-hero-actions">
            <Link to={`${BASE_PATH}/incidents`} className="su-btn su-btn-mint">
              Review incidents <Icon name="chevronRight" size={16} />
            </Link>
            <Link to={`${BASE_PATH}/hospitals`} className="su-btn su-btn-glass">
              Manage hospitals
            </Link>
          </div>
          <small className="su-hero-note">Academic prototype · all incidents are simulated</small>
        </div>
        <div className="su-hero-visual">
          <PulseRing alert={isAlerting} animated={preferences?.animations !== false} />
          <span className="su-float-chip su-chip-a">
            <Icon name="mapPin" size={14} /> Location received
          </span>
          <span className="su-float-chip su-chip-b">
            <span className="su-live-dot" /> {stats.activeHospitals} hospitals connected
          </span>
          <span className="su-float-chip su-chip-c">
            <Icon name="cpu" size={14} /> {stats.onlineDevices} devices online
          </span>
        </div>
      </section>

      <div className="su-section-head">
        <h2>At a glance</h2>
        <span>Across the whole system</span>
      </div>
      <div className="su-stats">
        <StatCard
          label="Total incidents"
          value={stats.totalIncidents}
          hint="Recorded suspected accidents"
          icon="alert"
          tone="red"
          to={`${BASE_PATH}/incidents`}
        />
        <StatCard
          label="Pending alerts"
          value={stats.pendingAlerts}
          hint="Hospital notifications awaiting a response"
          icon="bell"
          tone="amber"
          to={`${BASE_PATH}/incidents`}
        />
        <StatCard
          label="Online devices"
          value={stats.onlineDevices}
          hint={`Communicating now · ${stats.totalDevices} registered`}
          icon="wifi"
          tone="green"
          to={`${BASE_PATH}/devices`}
        />
        <StatCard
          label="Active hospitals"
          value={stats.activeHospitals}
          hint={`Available for notification · ${stats.totalHospitals} registered`}
          icon="building"
          tone="purple"
          to={`${BASE_PATH}/hospitals`}
        />
      </div>

      <div className="su-grid-2">
        <Panel
          title="Recent incidents"
          count={incidents.length}
          subtitle="Latest suspected accidents across all devices."
          action={
            <Link to={`${BASE_PATH}/incidents`} className="su-link">
              View all <Icon name="chevronRight" size={14} />
            </Link>
          }
        >
          <IncidentTable incidents={recent} statusMap={INCIDENT_STATUS} compact />
        </Panel>

        <Panel title="Incident flow" subtitle="Where every incident currently sits." icon="route">
          <ul className="su-flow">
            {FLOW.map((step) => {
              const count = countByStatus[step.key] ?? 0;
              const tone = INCIDENT_STATUS[step.key].tone;
              const pct = incidents.length ? (count / incidents.length) * 100 : 0;
              return (
                <li key={step.key}>
                  <span className={`su-flow-dot su-tone-${tone}`} />
                  <span className="su-flow-label">{step.label}</span>
                  <span className="su-flow-bar">
                    <span className={`su-tone-${tone}`} style={{ width: `${pct}%` }} />
                  </span>
                  <strong>{count}</strong>
                </li>
              );
            })}
          </ul>

          <div className="su-attention">
            <h3>Needs attention</h3>
            {attention.length === 0 ? (
              <p className="su-muted">Nothing waiting on a superuser right now.</p>
            ) : (
              attention.map((incident) => (
                <Link key={incident.id} to={`${BASE_PATH}/incidents/${incident.id}`} className="su-attention-item">
                  <span className="su-mono su-strong">{incident.id}</span>
                  <Badge tone={INCIDENT_STATUS[incident.status].tone}>
                    {INCIDENT_STATUS[incident.status].label}
                  </Badge>
                  <Icon name="chevronRight" size={14} />
                </Link>
              ))
            )}
          </div>
        </Panel>
      </div>

      <div className="su-grid-3">
        <Panel
          title="Device connectivity"
          subtitle="ESP32 units reporting to the system."
          action={
            <Link to={`${BASE_PATH}/devices`} className="su-link">
              Devices <Icon name="chevronRight" size={14} />
            </Link>
          }
        >
          <div className="su-mini-stats">
            <div>
              <Badge tone="green">Online</Badge>
              <strong>{deviceCounts.online}</strong>
            </div>
            <div>
              <Badge tone="grey">Offline</Badge>
              <strong>{deviceCounts.offline}</strong>
            </div>
            <div>
              <Badge tone="red">Sensor fault</Badge>
              <strong>{deviceCounts.fault}</strong>
            </div>
            <div>
              <Badge tone="amber">GPS issues</Badge>
              <strong>{deviceCounts.gpsIssues}</strong>
            </div>
          </div>
          <p className="su-panel-foot">Live heartbeat data will replace these demo values.</p>
        </Panel>

        <Panel
          title="Hospital network"
          subtitle="Open assignments per hospital."
          action={
            <Link to={`${BASE_PATH}/hospitals`} className="su-link">
              Hospitals <Icon name="chevronRight" size={14} />
            </Link>
          }
        >
          <ul className="su-list">
            {hospitals.map((hospital) => (
              <li key={hospital.id}>
                <span className={`su-status-dot ${hospital.active ? "is-on" : ""}`} />
                <span className="su-list-main">
                  <strong>{hospital.name}</strong>
                  <small>
                    {hospital.id} · {hospital.city}
                  </small>
                </span>
                <span className="su-list-meta">
                  {hospital.active ? `${openByHospital[hospital.id] ?? 0} open` : "Inactive"}
                </span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel
          title="Recent activity"
          subtitle="Who did what, and when."
          action={
            <Link to={`${BASE_PATH}/activity`} className="su-link">
              History <Icon name="chevronRight" size={14} />
            </Link>
          }
        >
          <ul className="su-feed">
            {audit.slice(0, 5).map((entry) => (
              <li key={entry.id}>
                <span className="su-feed-dot" />
                <div>
                  <strong>{entry.action}</strong>
                  <span>
                    {entry.target} · {entry.actor}
                  </span>
                  <small>{formatRelative(entry.at, now)}</small>
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
