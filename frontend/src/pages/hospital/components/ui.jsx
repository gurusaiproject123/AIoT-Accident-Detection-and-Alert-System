import { useEffect, useRef, useState } from "react";
import { useHospital } from "../HospitalContext";
import { time, isAwaitingAcknowledgment, DEMO_STAFF, HOSPITAL } from "../data";
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
export function MapView({ incidents, onSelect, large = false }) {
  const points = [
    [220, 130],
    [410, 95],
    [340, 220],
    [510, 175],
    [155, 255],
    [450, 265],
  ];
  return (
    <div className={`hd-map ${large ? "hd-map-large" : ""}`}>
      <svg
        viewBox="0 0 640 340"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <defs>
          <pattern
            id="hd-map-grid"
            width="40"
            height="40"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M40 0H0v40"
              fill="none"
              stroke="#dce8e7"
              strokeWidth=".5"
            />
          </pattern>
        </defs>
        <rect width="640" height="340" fill="#eef4f1" />
        <rect width="640" height="340" fill="url(#hd-map-grid)" />
        <path
          d="M0 280Q100 160 200 230T440 230T680 110"
          fill="none"
          stroke="#cfdee9"
          strokeWidth="23"
        />
        <path
          d="M-30 90 640 280M140 -30 440 370M-20 220 680 65M20 0 240 340M440 -30 270 370M560 -20 600 360"
          fill="none"
          stroke="#fff"
          strokeWidth="11"
        />
        <path
          d="M-30 90 640 280M140 -30 440 370M-20 220 680 65"
          fill="none"
          stroke="#e3c896"
          strokeWidth="3"
        />
        <rect x="460" y="36" width="76" height="40" rx="12" fill="#d6e6d3" />
        <rect x="68" y="130" width="77" height="48" rx="15" fill="#d6e6d3" />
        <text x="285" y="52" fill="#778b8a" fontSize="15" fontWeight="600">
          BINDURA
        </text>
        <text x="45" y="318" fill="#8b9b97" fontSize="11">
          Illustrative layout · not geographic positioning
        </text>
        <g transform="translate(305 158)">
          <rect x="-14" y="-14" width="28" height="28" rx="8" fill="#107e72" />
          <path d="M-6 0H6M0-6V6" stroke="white" strokeWidth="3" />
        </g>
      </svg>
      {incidents
        .filter((i) => i.lat !== null)
        .slice(0, 6)
        .map((item, i) => (
          <button
            key={item.id}
            className={`hd-map-pin ${item.status === "New" ? "hd-map-pin-new" : ""}`}
            style={{
              left: `${(points[i][0] / 640) * 100}%`,
              top: `${(points[i][1] / 340) * 100}%`,
            }}
            onClick={() => onSelect(item.id)}
            aria-label={`Open ${item.id} at ${item.location}`}
          >
            <Icon name="car" size={15} />
          </button>
        ))}
      <span className="hd-map-label">
        <span className="hd-dot" /> Hospital area · schematic
      </span>
    </div>
  );
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
                  <strong>{i.id}</strong>
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
                    aria-label={`View details for ${i.id}`}
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

// Mount the form only while an action is pending, so entered credentials are
// discarded on cancel/success. They are never added to the incident or audit log.
export function ResponseConfirmation() {
  const { pendingResponse } = useHospital();
  return pendingResponse ? (
    <StaffConfirmationForm pending={pendingResponse} />
  ) : null;
}
function StaffConfirmationForm({ pending }) {
  const { confirmResponse, cancelResponse, operatorName } = useHospital();
  const [staffId, setStaffId] = useState(
    () =>
      DEMO_STAFF.find(
        (person) =>
          person.name === operatorName &&
          person.hospitalId === HOSPITAL.id &&
          person.active,
      )?.id || "",
  );
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const dialog = useRef(null);
  const first = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    first.current?.focus();
    const keyboard = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        cancelResponse();
      }
      if (event.key === "Tab") {
        const nodes = dialog.current?.querySelectorAll(
          "button:not(:disabled),input:not(:disabled),select:not(:disabled)",
        );
        if (!nodes?.length) return;
        const head = nodes[0],
          tail = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === head) {
          event.preventDefault();
          tail.focus();
        } else if (!event.shiftKey && document.activeElement === tail) {
          event.preventDefault();
          head.focus();
        }
      }
    };
    document.addEventListener("keydown", keyboard);
    return () => {
      document.removeEventListener("keydown", keyboard);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
    // Only the mounted form owns its focus/keyboard lifecycle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await confirmResponse(staffId, password);
      if (!result.ok) setError(result.error);
    } catch {
      setError("Confirmation failed. Please try again.");
    } finally {
      setPassword("");
      setBusy(false);
    }
  }
  const action =
    {
      Acknowledged: "acknowledgment",
      Accepted: "response acceptance",
      Declined: "decline",
      Closed: "closure",
    }[pending.status] || "recorded action";
  return (
    <div className="hd-confirm-backdrop">
      <section
        ref={dialog}
        className="hd-confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="hd-confirm-title"
        aria-describedby="hd-confirm-description"
      >
        <div className="hd-confirm-heading">
          <span className="hd-stat-icon hd-teal">
            <Icon name="shield" />
          </span>
          <button
            className="hd-icon-button"
            onClick={cancelResponse}
            aria-label="Cancel response confirmation"
            disabled={busy}
          >
            <Icon name="close" />
          </button>
        </div>
        <h2 id="hd-confirm-title">Confirm {action}</h2>
        <p id="hd-confirm-description">
          Select who is performing this action for <strong>{pending.id}</strong>
          . No response is recorded until confirmation succeeds.
        </p>
        <p className="hd-confirm-demo">
          Demo only — use <code>DemoConfirm!2026</code>. Do not enter a real
          account password. This fixture does not verify a real staff identity.
        </p>
        <form onSubmit={submit}>
          <label htmlFor="hd-confirm-name">Staff member</label>
          <select
            ref={first}
            id="hd-confirm-name"
            value={staffId}
            onChange={(event) => setStaffId(event.target.value)}
            required
            disabled={busy}
          >
            <option value="" disabled>
              Select the person performing this action
            </option>
            {DEMO_STAFF.filter(
              (person) => person.hospitalId === HOSPITAL.id && person.active,
            ).map((person) => (
              <option key={person.id} value={person.id}>
                {person.name} — {person.role}
              </option>
            ))}
          </select>
          <label htmlFor="hd-confirm-password">Confirmation password</label>
          <input
            id="hd-confirm-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            autoComplete="off"
            placeholder="Enter the demo confirmation password"
            disabled={busy}
            aria-describedby={error ? "hd-confirm-error" : undefined}
          />
          {error && (
            <p className="hd-confirm-error" id="hd-confirm-error" role="alert">
              {error}
            </p>
          )}
          <p className="hd-footnote">
            The acknowledgment countdown continues while this popup is open.
            Passwords are never stored in the audit history or CSV.
          </p>
          <div className="hd-confirm-actions">
            <button
              type="button"
              className="hd-button hd-button-secondary"
              onClick={cancelResponse}
              disabled={busy}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="hd-button hd-button-primary"
              disabled={busy || !staffId || !password}
            >
              {busy ? "Confirming…" : "Confirm action"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
