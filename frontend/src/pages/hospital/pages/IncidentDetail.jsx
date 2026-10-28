import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useHospital } from "../HospitalContext";
import { HOSPITAL, time, date, formatDateTime } from "../data";
import { Icon, Badge, ResponseCountdown } from "../components/ui";

export default function IncidentDetail() {
  const { incidentId } = useParams();
  const navigate = useNavigate();
  const { incidents, updateIncident, toast } = useHospital();
  const incident = incidents.find((i) => i.id === incidentId);
  const [action, setAction] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  async function saveAction() {
    if (!reason.trim()) {
      toast("Enter a reason before continuing.");
      return;
    }
    const succeeded =
      action === "decline"
        ? await updateIncident(
            incidentId,
            "Declined",
            `Hospital declined response: ${reason.trim()}`,
          )
        : await updateIncident(
            incidentId,
            null,
            `Possible false alarm reported: ${reason.trim()}. Awaiting authorised review.`,
          );
    if (!succeeded) return;
    setAction("");
    setReason("");
  }
  if (!incident)
    return (
      <section className="hd-panel hd-empty">
        <h2>Incident unavailable</h2>
        <p>This ID is not in this hospital’s demo records.</p>
        <Link to="/hospital/incidents" className="hd-button hd-button-primary">
          Back to incidents
        </Link>
      </section>
    );
  return (
    <div className="hd-incident-page">
      <section
        className="hd-detail-drawer"
        aria-labelledby="hd-detail-title"
        tabIndex="-1"
      >
        <div className="hd-detail-header">
          <div>
            <span className="hd-eyebrow">ASSIGNED INCIDENT</span>
            <h2 id="hd-detail-title">{incident.id}</h2>
          </div>
          <button
            className="hd-icon-button"
            onClick={() => navigate("/hospital/incidents")}
            aria-label="Back to assigned incidents"
          >
            <Icon name="close" />
          </button>
        </div>
        <div className="hd-detail-body">
          <div className="hd-detail-status">
            <Badge status={incident.status} />
            <span>
              {date(incident.created)} · {time(incident.created)}
            </span>
          </div>
          <h3>{incident.location}</h3>
          <p className="hd-incident-time">
            <Icon name="clock" size={17} />
            <span>
              <strong>Incident time</strong>{" "}
              {formatDateTime(incident.occurredAt)}
            </span>
          </p>
          {incident.occurredAtSource === "reported_time_estimate" && (
            <p className="hd-footnote">
              Exact incident time was not supplied for this older record. The
              reported time is shown as an estimate.
            </p>
          )}
          <p className="hd-footnote">
            Reported to the system: {formatDateTime(incident.created)}
            {incident.occurredAtSource === "simulated"
              ? " · Simulated incident time"
              : ""}
          </p>
          <p className="hd-subtitle">
            Suspected accident · {incident.device} · Sample recording
          </p>
          <div className="hd-detail-location">
            <Icon name="pin" />
            <div>
              <strong>
                {incident.lat !== null
                  ? `${incident.lat}, ${incident.lng}`
                  : "Location unavailable"}
              </strong>
              <p>
                {incident.lat !== null
                  ? `GPS age at detection: ${incident.gpsAge}s · Accuracy not reported`
                  : "No valid GPS fix supplied. Location must be verified."}
              </p>
            </div>
            {incident.lat !== null && (
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${incident.lat},${incident.lng}`}
                target="_blank"
                rel="noreferrer"
                aria-label="Open sample coordinates in Google Maps"
              >
                <Icon name="external" size={18} />
              </a>
            )}
          </div>
          <div className="hd-detail-metrics">
            <div>
              <span>Model score</span>
              <strong>{incident.score.toFixed(2)}</strong>
            </div>
            <div>
              <span>Peak acceleration</span>
              <strong>
                {incident.peak} <small>g</small>
              </strong>
            </div>
          </div>
          <p className="hd-footnote">
            Demo model values. A score is not a calibrated crash probability or
            injury severity estimate.
          </p>
          <div className="hd-identity-grid">
            <section
              className="hd-identity-card"
              aria-labelledby="hd-vehicle-heading"
            >
              <div className="hd-identity-heading">
                <span className="hd-stat-icon hd-teal">
                  <Icon name="car" size={20} />
                </span>
                <div>
                  <h4 id="hd-vehicle-heading">Vehicle details</h4>
                  <p>Vehicle linked to this incident</p>
                </div>
              </div>
              <span
                className="hd-registration"
                aria-label="Vehicle registration number"
              >
                {incident.vehicle?.registration || "Not available"}
              </span>
              <dl className="hd-contact-fields">
                <div>
                  <dt>Registration number</dt>
                  <dd>{incident.vehicle?.registration || "Not provided"}</dd>
                </div>
                <div>
                  <dt>Make and model</dt>
                  <dd>
                    {[incident.vehicle?.make, incident.vehicle?.model]
                      .filter(Boolean)
                      .join(" ") || "Not provided"}
                  </dd>
                </div>
                <div>
                  <dt>Colour</dt>
                  <dd>{incident.vehicle?.colour || "Not provided"}</dd>
                </div>
                <div>
                  <dt>Linked device</dt>
                  <dd>{incident.device || "Not provided"}</dd>
                </div>
              </dl>
            </section>
            <section
              className="hd-identity-card"
              aria-labelledby="hd-owner-heading"
            >
              <div className="hd-identity-heading">
                <span className="hd-stat-icon hd-blue">
                  <Icon name="shield" size={20} />
                </span>
                <div>
                  <h4 id="hd-owner-heading">Owner and contact details</h4>
                  <p>Registered contact for this vehicle</p>
                </div>
              </div>
              <dl className="hd-contact-fields">
                <div>
                  <dt>Full name</dt>
                  <dd>{incident.owner?.name || "Not provided"}</dd>
                </div>
                <div>
                  <dt>Relationship to vehicle</dt>
                  <dd>{incident.owner?.relationship || "Not provided"}</dd>
                </div>
                <div>
                  <dt>Phone number</dt>
                  <dd>{incident.owner?.phone || "Not provided"}</dd>
                </div>
                <div>
                  <dt>Email address</dt>
                  <dd>{incident.owner?.email || "Not provided"}</dd>
                </div>
              </dl>
              <p className="hd-footnote">
                Sample contact details. The registered owner may differ from the
                driver or occupants. Confirm identity before contacting anyone.
              </p>
            </section>
          </div>
          <p className="hd-footnote">
            Demo registration numbers and contacts are fictional. Replace them
            with authorised vehicle registration records during backend
            integration.
          </p>
          <section
            className="hd-detail-response-clock"
            aria-label="Incident acknowledgment deadline"
          >
            <div>
              <h4>Acknowledgment deadline</h4>
              <p>
                Assigned at {time(incident.assignedAt)}. Acknowledge within
                three minutes of assignment.
              </p>
              <p>
                The countdown applies only to New alerts. Acknowledgment stops
                both the alarm and timer. A later decline still escalates
                immediately.
              </p>
            </div>
            <ResponseCountdown incident={incident} />
          </section>
          {incident.escalation && (
            <section
              className="hd-escalation-card"
              aria-labelledby="hd-escalation-heading"
            >
              <h4 id="hd-escalation-heading">
                {incident.status === "Escalated"
                  ? "Escalation recorded"
                  : "Escalation requires review"}
              </h4>
              <dl className="hd-contact-fields">
                <div>
                  <dt>Trigger</dt>
                  <dd>
                    {incident.escalation.trigger === "decline"
                      ? "Hospital declined after acknowledgment"
                      : "Three-minute acknowledgment timeout"}
                  </dd>
                </div>
                <div>
                  <dt>Next hospital</dt>
                  <dd>
                    {incident.escalation.toHospitalName ||
                      "No eligible destination selected"}
                  </dd>
                </div>
                <div>
                  <dt>Distance</dt>
                  <dd>
                    {incident.escalation.distanceKm == null
                      ? "Unavailable"
                      : `${incident.escalation.distanceKm.toFixed(1)} km straight-line`}
                  </dd>
                </div>
                <div>
                  <dt>Escalated at</dt>
                  <dd>
                    {date(incident.escalation.at)} ·{" "}
                    {time(incident.escalation.at)}
                  </dd>
                </div>
                <div>
                  <dt>Reason</dt>
                  <dd>{incident.escalation.reason}</dd>
                </div>
              </dl>
              <p className="hd-footnote">
                Simulated routing only. No other hospital has been contacted.
                Real delivery and durable deadlines must be handled by FastAPI.
              </p>
            </section>
          )}
          <section
            className="hd-response-audit"
            aria-labelledby="hd-response-audit-title"
          >
            <h4 id="hd-response-audit-title">Response audit</h4>
            <dl className="hd-contact-fields">
              <div>
                <dt>Acknowledged by</dt>
                <dd>
                  {incident.acknowledgedBy ||
                    (incident.acknowledgedAt
                      ? "Not recorded in this older record"
                      : "Not acknowledged")}
                </dd>
              </div>
              <div>
                <dt>Acknowledged at</dt>
                <dd>{formatDateTime(incident.acknowledgedAt)}</dd>
              </div>
              <div>
                <dt>Response accepted by</dt>
                <dd>{incident.acceptedBy || "Not recorded"}</dd>
              </div>
              <div>
                <dt>Response accepted at</dt>
                <dd>{formatDateTime(incident.acceptedAt)}</dd>
              </div>
            </dl>
            <p className="hd-footnote">
              Demo names are selected from the hospital staff list. Production
              identity must be verified by the server.
            </p>
          </section>
          <h4>Hospital response</h4>
          <p className="hd-footnote">
            Acknowledge receipt first, then accept or decline the response.
          </p>
          <div className="hd-response-actions">
            <button
              className="hd-button hd-button-secondary"
              disabled={incident.status !== "New"}
              onClick={() =>
                updateIncident(
                  incident.id,
                  "Acknowledged",
                  "Alert receipt acknowledged",
                )
              }
            >
              <Icon name="check" size={16} /> Acknowledge
            </button>
            <button
              className="hd-button hd-button-primary"
              disabled={incident.status !== "Acknowledged"}
              onClick={() =>
                updateIncident(
                  incident.id,
                  "Accepted",
                  "Hospital response accepted",
                )
              }
            >
              <Icon name="shield" size={16} /> Accept response
            </button>
            <button
              className="hd-button hd-button-danger-outline"
              disabled={incident.status !== "Acknowledged"}
              onClick={() => {
                setAction("decline");
                setReason("");
              }}
            >
              Decline
            </button>
            {incident.status === "Accepted" && (
              <button
                className="hd-button hd-button-secondary"
                onClick={() =>
                  updateIncident(
                    incident.id,
                    "Closed",
                    "Incident closed by demo operator",
                  )
                }
              >
                Close incident
              </button>
            )}
          </div>
          <button
            className="hd-text-link hd-report-false"
            disabled={[
              "Closed",
              "Declined",
              "Escalated",
              "Escalation pending",
            ].includes(incident.status)}
            onClick={() => {
              setAction("false-alarm");
              setReason("");
            }}
          >
            Report a possible false alarm
          </button>
          {action && (
            <div className="hd-action-form">
              <label htmlFor="hd-reason">
                {action === "decline"
                  ? "Reason for declining"
                  : "Reason for review"}{" "}
                <span>(required)</span>
              </label>
              <textarea
                id="hd-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Explain the reason…"
                maxLength={1000}
              />
              <p className="hd-footnote">
                Demo only. Declining immediately records simulated routing to
                the next nearby hospital with this reason. No live notification
                or global cancellation is performed.
              </p>
              <div>
                <button
                  className="hd-button hd-button-primary"
                  onClick={saveAction}
                  disabled={!reason.trim()}
                >
                  Save {action === "decline" ? "decline" : "report"}
                </button>
                <button
                  className="hd-button hd-button-secondary"
                  onClick={() => setAction("")}
                >
                  Back
                </button>
              </div>
            </div>
          )}
          <h4>Response notes</h4>
          <label className="hd-sr" htmlFor="hd-note">
            Add a response note
          </label>
          <textarea
            id="hd-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add information for your response team…"
            maxLength={1000}
          />
          <button
            className="hd-button hd-button-secondary hd-save-note"
            disabled={!note.trim()}
            onClick={async () => {
              const saved = await updateIncident(
                incident.id,
                null,
                `Note: ${note.trim()}`,
              );
              if (saved) setNote("");
            }}
          >
            Save note
          </button>
          <h4>Incident timeline</h4>
          <div className="hd-detail-timeline">
            {[...incident.timeline].reverse().map((e, i) => (
              <div key={i}>
                <span />
                <strong>{e.text}</strong>
                <small>
                  {e.user} · {time(e.at)}
                </small>
              </div>
            ))}
          </div>
        </div>
        <div className="hd-detail-footer">
          <Icon name="shield" size={15} />
          Visible in {HOSPITAL.name}’s demo workspace only
        </div>
      </section>
    </div>
  );
}
