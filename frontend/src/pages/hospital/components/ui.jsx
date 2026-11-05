import { useHospital } from "../HospitalContext";
import { time, isAwaitingAcknowledgment } from "../data";
const ICONS = {
  grid: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="2" />
      <rect x="14" y="3" width="7" height="7" rx="2" />
      <rect x="3" y="14" width="7" height="7" rx="2" />
      <rect x="14" y="14" width="7" height="7" rx="2" />
    </>
  ),
  bell: (
    <>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
      <path d="M10 21h4" />
    </>
  ),
  map: (
    <>
      <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Z" />
      <path d="M9 3v15M15 6v15" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  chart: (
    <>
      <path d="M4 3v17h17M8 15v-4m5 4V7m5 8V4" />
    </>
  ),
  settings: (
    <>
      <path d="m9 3-1 3-3 1 1 3-2 2 2 2-1 3 3 1 1 3h6l1-3 3-1-1-3 2-2-2-2 1-3-3-1-1-3Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  arrow: <path d="m9 5 7 7-7 7" />,
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 5 5" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  pin: (
    <>
      <path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </>
  ),
  pulse: <path d="M2 12h5l3-8 4 16 3-8h5" />,
  download: (
    <>
      <path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4" />
    </>
  ),
  shield: (
    <>
      <path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6Z" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  sound: (
    <>
      <path d="m3 9 5 0 5-5v16l-5-5H3Z" />
      <path d="M17 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14" />
    </>
  ),
  car: (
    <>
      <path d="m5 7 2-4h10l2 4 2 3v8H3v-8Z M3 10h18M6 18v3m12-3v3" />
      <circle cx="7" cy="14" r="1" />
      <circle cx="17" cy="14" r="1" />
    </>
  ),
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  external: (
    <>
      <path d="M14 3h7v7m0-7L10 14M10 4H4v16h16v-6" />
    </>
  ),
  hospital: (
    <>
      <path d="M5 21V3h14v18M2 21h20M9 7h6m-3-3v6M9 21v-6h6v6" />
    </>
  ),
  moon: <path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z" />,
};
export function Icon({ name, size = 20, ...props }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {ICONS[name] || ICONS.pulse}
    </svg>
  );
}
export function Badge({ status }) {
  return (
    <span
      className={`hd-badge hd-status-${status.toLowerCase().replaceAll(" ", "-")}`}
    >
      <span />
      {status}
    </span>
  );
}
export function Orb({ small = false }) {
  const { alarmActive } = useHospital();
  return (
    <div
      className={`hd-orbit ${small ? "hd-orbit-small" : ""} ${alarmActive ? "hd-orbit-alarming" : ""}`}
      aria-hidden="true"
    >
      {Array.from({ length: 7 }, (_, i) => (
        <i key={i} style={{ "--i": i }} />
      ))}
      <div className="hd-orbit-core">
        <Icon name="pulse" size={small ? 24 : 40} />
      </div>
    </div>
  );
}
export function MapView({ incidents }) {
  const located = incidents.filter((item) => item.lat !== null);
  return <div className="hd-activity-list">
    {!located.length && <p>No reported GPS coordinates.</p>}
    {located.map((item) => <div key={item.id} className="hd-activity-row">
      <Icon name="pin" size={16} />
      <div><strong>{item.code}</strong><p>{item.lat}, {item.lng}</p></div>
      <a className="hd-text-link" target="_blank" rel="noreferrer"
        href={`https://www.google.com/maps/search/?api=1&query=${item.lat},${item.lng}`}>Open map</a>
    </div>)}
  </div>;
}

export function IncidentTable({ items }) {
  const { age, openIncident } = useHospital();
  return (
    <div className="hd-table-scroll">
      <table className="hd-table">
        <thead>
          <tr>
            <th>Incident</th>
            <th>Location</th>
            <th>Received</th>
            <th>Status</th>
            <th>New alert timer</th>
            <th>
              <span className="hd-sr">Details</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.length ? (
            items.map((i) => (
              <tr key={i.id}>
                <td>
                  <strong>{i.code}</strong>
                  <small>{i.device}</small>
                </td>
                <td>
                  <span className="hd-inline">
                    <Icon name="pin" size={14} />
                    {i.location}
                  </span>
                  <small>
                    {i.lat !== null
                      ? "GPS location available"
                      : "GPS unavailable"}
                  </small>
                </td>
                <td>
                  {time(i.created)}
                  <small>{age(i.created)}</small>
                </td>
                <td>
                  <Badge status={i.status} />
                </td>
                <td>
                  <ResponseCountdown incident={i} compact />
                </td>
                <td>
                  <button
                    className="hd-row-link"
                    onClick={() => openIncident(i.id)}
                    aria-label={`View details for ${i.code}`}
                  >
                    View details <Icon name="arrow" size={14} />
                  </button>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="6">
                <div className="hd-empty">
                  <Icon name="search" size={30} />
                  <h3>No incidents found</h3>
                  <p>Try another search or status filter.</p>
                </div>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function ResponseCountdown({ incident, compact = false }) {
  const { clock } = useHospital();
  if (incident.escalation)
    return (
      <span className="hd-countdown-ended">
        {incident.status === "Escalated"
          ? "Escalated"
          : "Routing review required"}
      </span>
    );
  if (!isAwaitingAcknowledgment(incident))
    return (
      <span className="hd-countdown-ended">
        {incident.status === "Acknowledged"
          ? "Acknowledged — timer stopped"
          : incident.status === "Accepted" || incident.status === "Closed"
            ? "Response recorded"
            : "Not pending"}
      </span>
    );
  if (!Number.isFinite(incident.responseDeadline))
    return <span className="hd-countdown-ended">Deadline unavailable</span>;
  const seconds = Math.max(
    0,
    Math.ceil(
      (incident.responseDeadline -
        Math.max(clock, incident.assignedAt ?? clock)) /
        1000,
    ),
  );
  const display = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  return (
    <span
      className={`hd-countdown ${seconds <= 30 ? "hd-countdown-urgent" : ""} ${compact ? "hd-countdown-compact" : ""}`}
      role="timer"
      aria-label={`${display} remaining to acknowledge`}
    >
      <Icon name="clock" size={compact ? 13 : 17} />
      <strong>{display}</strong>
      {!compact && <small>to acknowledge</small>}
    </span>
  );
}

