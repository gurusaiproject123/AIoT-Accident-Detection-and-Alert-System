import { useState } from "react";
import { Link, useParams } from "react-router";
import Icon from "../components/Icon";
import { Badge, DetailList, EmptyState, Field, Modal, Panel, StatusBadge } from "../components/ui";
import { useSuperuser } from "../useSuperuser";
import {
  BASE_PATH,
  INCIDENT_STATUS,
  NOTIFICATION_STATUS,
  formatCoords,
  formatDateTime,
  formatRelative,
  formatTime,
  mapsUrl,
} from "../data";

const TIMELINE_ICONS = {
  detected: "alert",
  window: "clock",
  notified: "send",
  ack: "check",
  accept: "checkCircle",
  decline: "x",
  timeout: "clock",
  escalated: "route",
  closed: "shield",
  cancelled: "x",
  note: "note",
};

const TIMELINE_TONES = {
  detected: "red",
  window: "amber",
  notified: "red",
  ack: "blue",
  accept: "green",
  decline: "grey",
  timeout: "amber",
  escalated: "amber",
  closed: "purple",
  cancelled: "grey",
  note: "grey",
};

export default function IncidentDetail() {
  const { incidentId } = useParams();
  const { incidents, hospitals, hospitalById, deviceById, now, notifyHospital, closeIncident, addIncidentNote } =
    useSuperuser();
  const incident = incidents.find((i) => i.id === incidentId);

  const [routeTo, setRouteTo] = useState("");
  const [note, setNote] = useState("");
  const [closing, setClosing] = useState(false);
  const [closeNote, setCloseNote] = useState("");

  if (!incident) {
    return (
      <div className="su-page">
        <Panel>
          <EmptyState icon="alert" title={`Incident ${incidentId} is unavailable`}>
            It may have been removed, or the link is incorrect.
          </EmptyState>
          <div className="su-center">
            <Link to={`${BASE_PATH}/incidents`} className="su-btn su-btn-soft">
              <Icon name="chevronLeft" size={15} /> Back to incidents
            </Link>
          </div>
        </Panel>
      </div>
    );
  }

  const device = deviceById[incident.deviceId];
  const isResolved = ["closed", "cancelled"].includes(incident.status);
  const inWindow = incident.status === "cancellation_window";
  const notifiedIds = incident.notifications.map((n) => n.hospitalId);
  const routable = hospitals.filter((h) => h.active && !notifiedIds.includes(h.id));
  const url = mapsUrl(incident.location?.lat, incident.location?.lng);

  const deadline =
    new Date(incident.detectedAt).getTime() + incident.cancellation.windowSeconds * 1000;
  const remaining = Math.max(0, Math.ceil((deadline - now) / 1000));

  const cancellation = {
    pending: { label: "Window running", tone: "amber", text: `${remaining}s left for a local false-alarm cancellation.` },
    expired: { label: "Not cancelled", tone: "red", text: "The cancellation window ended without a cancellation, so hospitals were notified." },
    cancelled: { label: "Cancelled", tone: "grey", text: `Cancelled as a false alarm by ${incident.cancellation.by ?? "an authorised operator"}.` },
  }[incident.cancellation.outcome];

  const submitNote = (event) => {
    event.preventDefault();
    if (!note.trim()) return;
    addIncidentNote(incident.id, note.trim());
    setNote("");
  };

  const submitRoute = () => {
    if (!routeTo) return;
    notifyHospital(incident.id, routeTo);
    setRouteTo("");
  };

  return (
    <div className="su-page">
      <Link to={`${BASE_PATH}/incidents`} className="su-back">
        <Icon name="chevronLeft" size={15} /> All incidents
      </Link>

      <div className="su-page-heading">
        <div>
          <p className="su-eyebrow">Incident record · {incident.deviceId}</p>
          <h1 className="su-title su-title-row">
            <span className="su-mono">{incident.id}</span>
            <StatusBadge map={INCIDENT_STATUS} value={incident.status} />
          </h1>
          <p className="su-subtitle">
            Detected {formatDateTime(incident.detectedAt)} · {formatRelative(incident.detectedAt, now)}
          </p>
        </div>
        <div className="su-page-actions">
          {url && (
            <a href={url} target="_blank" rel="noreferrer" className="su-btn su-btn-outline">
              <Icon name="external" size={15} /> Open in Google Maps
            </a>
          )}
          {!isResolved && (
            <button type="button" className="su-btn su-btn-primary" onClick={() => setClosing(true)}>
              <Icon name="shield" size={15} /> Close incident
            </button>
          )}
        </div>
      </div>

      <div className="su-detail-grid">
        <div className="su-stack">
          <Panel title="Detection and location" icon="alert">
            <DetailList
              items={[
                { label: "Detected at", value: formatDateTime(incident.detectedAt) },
                { label: "Device", value: <span className="su-mono">{incident.deviceId}</span> },
                { label: "Vehicle", value: device ? `${device.vehicle} · ${device.vehicleModel}` : "Unknown device" },
                { label: "Registered owner", value: device?.owner ?? "Unavailable" },
                { label: "Detection signal", value: incident.impact },
                {
                  label: "Model score",
                  value: (
                    <span title="Random Forest output — not a calibrated crash probability">
                      {incident.modelScore.toFixed(2)}
                    </span>
                  ),
                },
                { label: "Location", value: incident.location?.label ?? "Location unavailable" },
                { label: "GPS coordinates", value: <span className="su-mono">{formatCoords(incident.location?.lat, incident.location?.lng)}</span> },
              ]}
            />
            <p className="su-panel-foot">
              The model score is not a calibrated crash probability or injury-severity estimate.
            </p>
          </Panel>

          <Panel title="Cancellation status" icon="clock">
            <div className={`su-callout su-tone-${cancellation.tone}`}>
              <Badge tone={cancellation.tone}>{cancellation.label}</Badge>
              <p>{cancellation.text}</p>
              {inWindow && (
                <div className="su-countdown">
                  <span style={{ width: `${(remaining / incident.cancellation.windowSeconds) * 100}%` }} />
                </div>
              )}
            </div>
            <DetailList
              items={[
                { label: "Window length", value: `${incident.cancellation.windowSeconds} seconds` },
                { label: "Outcome recorded", value: formatTime(incident.cancellation.at) },
                { label: "Cancelled by", value: incident.cancellation.by ?? "—" },
              ]}
            />
          </Panel>

          <Panel
            title="Hospitals notified"
            count={incident.notifications.length}
            subtitle="Acknowledgment and acceptance from each notified hospital."
          >
            {incident.notifications.length === 0 ? (
              <EmptyState icon="building" title={inWindow ? "Waiting for the cancellation window" : "No hospitals notified"}>
                {inWindow
                  ? "Hospitals are notified automatically if the alert is not cancelled."
                  : "No notification was sent for this incident."}
              </EmptyState>
            ) : (
              <ol className="su-hospital-steps">
                {incident.notifications.map((n, index) => (
                  <li key={n.hospitalId}>
                    <span className="su-step-num">{index + 1}</span>
                    <div className="su-step-body">
                      <div className="su-step-head">
                        <strong>{hospitalById[n.hospitalId]?.name ?? n.hospitalId}</strong>
                        <StatusBadge map={NOTIFICATION_STATUS} value={n.status} />
                      </div>
                      <div className="su-step-times">
                        <span>
                          <small>Notified</small>
                          {formatTime(n.notifiedAt)}
                        </span>
                        <span>
                          <small>Acknowledged</small>
                          {formatTime(n.acknowledgedAt)}
                        </span>
                        <span>
                          <small>{n.status === "declined" ? "Declined" : "Accepted"}</small>
                          {formatTime(n.respondedAt)}
                        </span>
                      </div>
                      {n.reason && <p className="su-step-reason">Reason: {n.reason}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            )}

            {!isResolved && !inWindow && (
              <div className="su-route-box">
                <label htmlFor="route-hospital">Route to another hospital</label>
                <div className="su-inline-form">
                  <select
                    id="route-hospital"
                    className="su-select"
                    value={routeTo}
                    onChange={(e) => setRouteTo(e.target.value)}
                    disabled={!routable.length}
                  >
                    <option value="">{routable.length ? "Select an active hospital" : "No other active hospitals"}</option>
                    {routable.map((h) => (
                      <option key={h.id} value={h.id}>
                        {h.name} · {h.city}
                      </option>
                    ))}
                  </select>
                  <button type="button" className="su-btn su-btn-primary" onClick={submitRoute} disabled={!routeTo}>
                    <Icon name="send" size={15} /> Notify
                  </button>
                </div>
                <small>Manual routing is recorded in the escalation history and activity log.</small>
              </div>
            )}
          </Panel>
        </div>

        <div className="su-stack">
          <Panel title="Escalation history" subtitle="Complete incident flow, oldest first." icon="route">
            <ol className="su-timeline">
              {incident.timeline.map((entry, index) => (
                <li key={`${entry.at}-${index}`}>
                  <span className={`su-timeline-icon su-tone-${TIMELINE_TONES[entry.type] ?? "grey"}`}>
                    <Icon name={TIMELINE_ICONS[entry.type] ?? "clock"} size={14} />
                  </span>
                  <div>
                    <p>{entry.text}</p>
                    <small>
                      {formatDateTime(entry.at)} · {entry.actor}
                    </small>
                  </div>
                </li>
              ))}
            </ol>
          </Panel>

          <Panel title="Superuser notes" count={incident.notes.length} icon="note">
            {incident.notes.length > 0 && (
              <ul className="su-notes">
                {incident.notes.map((n, index) => (
                  <li key={`${n.at}-${index}`}>
                    <p>{n.text}</p>
                    <small>
                      {formatDateTime(n.at)} · {n.actor}
                    </small>
                  </li>
                ))}
              </ul>
            )}
            <form className="su-note-form" onSubmit={submitNote}>
              <label htmlFor="incident-note" className="su-visually-hidden">
                Add a note
              </label>
              <textarea
                id="incident-note"
                rows={3}
                placeholder="Add an internal note for this incident…"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={500}
              />
              <button type="submit" className="su-btn su-btn-soft" disabled={!note.trim()}>
                <Icon name="plus" size={15} /> Add note
              </button>
            </form>
          </Panel>
        </div>
      </div>

      {closing && (
        <Modal
          title={`Close ${incident.id}?`}
          subtitle="Closing records the incident as resolved. No further routing will occur."
          onClose={() => setClosing(false)}
          size="sm"
          footer={
            <>
              <button type="button" className="su-btn su-btn-ghost" onClick={() => setClosing(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="su-btn su-btn-primary"
                onClick={() => {
                  closeIncident(incident.id, closeNote.trim());
                  setClosing(false);
                  setCloseNote("");
                }}
              >
                Close incident
              </button>
            </>
          }
        >
          <Field label="Closing note (optional)">
            <textarea
              rows={3}
              value={closeNote}
              onChange={(e) => setCloseNote(e.target.value)}
              placeholder="e.g. Confirmed resolved with Bindura Hospital."
            />
          </Field>
        </Modal>
      )}
    </div>
  );
}

