import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useHospital } from "../HospitalContext";
import { mapAlert } from "../hospitalApi";
import { formatDateTime } from "../data";
import { Badge, ResponseCountdown } from "../components/ui";

export default function IncidentDetail() {
  const { incidentId: alertId } = useParams();
  const { request, refresh, incidents } = useHospital();
  const fromFeed = incidents.find((item) => item.id === alertId);
  const [result, setResult] = useState(null);
  const [revision, setRevision] = useState(0);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [action, setAction] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const options = { signal: controller.signal };
    async function load() {
      try {
        const alert = mapAlert(await request(`/api/alerts/${encodeURIComponent(alertId)}`, options));
        if (controller.signal.aborted) return;
        setResult({ alert });
        setLoadError("");
        const path = `/api/incidents/${encodeURIComponent(alert.incidentId)}`;
        const [detail, timeline] = await Promise.allSettled([
          request(path, options), request(path + "/timeline", options),
        ]);
        if (controller.signal.aborted) return;
        setResult({
          alert,
          detail: detail.status === "fulfilled" ? detail.value : null,
          timeline: timeline.status === "fulfilled" ? timeline.value.items ?? [] : null,
        });
        if (detail.status === "rejected" || timeline.status === "rejected") {
          setLoadError("Some incident details or timeline entries could not be loaded.");
        }
      } catch (error) {
        if (!controller.signal.aborted) setLoadError(error.message);
      }
    }
    load();
    return () => controller.abort();
  }, [request, alertId, revision]);

  const alert = result?.alert?.id === alertId ? result.alert : fromFeed;
  const current = fromFeed ?? alert;
  const detail = result?.detail;
  const timeline = result?.timeline;
  const retry = () => setRevision((value) => value + 1);

  async function send(endpoint, body, success) {
    if (lock.current || !alert) return false;
    lock.current = true;
    setBusy(true);
    setActionError("");
    setMessage("");
    try {
      await request(endpoint, { method: "POST", body });
      setMessage(success);
      return true;
    } catch (error) {
      setActionError(error.message);
      return false;
    } finally {
      await refresh();
      retry();
      setBusy(false);
      lock.current = false;
    }
  }

  if (!alert) return <section className="hd-panel hd-empty">
    <p role={loadError ? "alert" : "status"}>{loadError || "Loading incident…"}</p>
    {loadError && <button className="hd-text-link" onClick={retry}>Retry</button>}
    <Link to="/hospital/incidents">Back to alerts</Link>
  </section>;

  const alertPath = `/api/alerts/${encodeURIComponent(alert.id)}`;
  const incidentPath = `/api/incidents/${encodeURIComponent(alert.incidentId)}`;
  const pending = current.status === "New";
  const acknowledged = current.status === "Acknowledged";
  const canWrite = pending || acknowledged || current.status === "Accepted";

  async function saveReason(event) {
    event.preventDefault();
    const value = reason.trim();
    const decline = action === "decline";
    if (value.length < (decline ? 1 : 3)) return;
    if (await send(decline ? alertPath + "/decline" : incidentPath + "/false-alarm-reports",
      { reason: value }, decline ? "Response declined." : "False alarm report submitted for review.")) {
      setAction("");
      setReason("");
    }
  }

  return <div className="hd-incident-page">
    <section className="hd-detail-drawer" aria-labelledby="hd-detail-title">
      <div className="hd-detail-header">
        <div><p className="hd-eyebrow">ASSIGNED ALERT</p><h2 id="hd-detail-title">{alert.code}</h2></div>
        <Link className="hd-button hd-button-secondary" to="/hospital/incidents">Back to alerts</Link>
      </div>
      <div className="hd-detail-body">
        {loadError && <p role="alert">{loadError} <button className="hd-text-link" onClick={retry}>Retry</button></p>}
        <Badge status={current.status} />
        <h3>{alert.location}</h3>
        <p>{alert.device} · Received {formatDateTime(alert.created)}</p>
        <p>Detected {formatDateTime(alert.detected)}</p>
        {detail?.occurred_at && <p>Occurred {formatDateTime(Date.parse(detail.occurred_at))}{detail.occurred_at_estimated ? " (estimated)" : ""}</p>}
        {alert.lat !== null && <a className="hd-text-link" target="_blank" rel="noreferrer"
          href={`https://www.google.com/maps/search/?api=1&query=${alert.lat},${alert.lng}`}>Open GPS location</a>}
        {alert.score !== null && <p>Model score: {alert.score.toFixed(2)}</p>}
        {alert.impactSummary && <p>{alert.impactSummary}</p>}
        <div className="hd-identity-grid">
          <section className="hd-identity-card">
            <h4>Registered vehicle</h4>
            <p>{alert.vehicle?.registration || "Unavailable"}</p>
            <p>{[alert.vehicle?.make, alert.vehicle?.model, alert.vehicle?.colour].filter(Boolean).join(" · ")}</p>
          </section>
          <section className="hd-identity-card">
            <h4>Registered owner</h4>
            <p>{alert.owner?.full_name || "Unavailable"}</p>
            {alert.owner?.phone && <p>{alert.owner.phone}</p>}
            {alert.owner?.email && <p>{alert.owner.email}</p>}
          </section>
        </div>
        <section className="hd-detail-response-clock">
          <h4>Acknowledgment deadline</h4><ResponseCountdown incident={current} />
        </section>
        <h4>Hospital response</h4>
        {message && <p role="status">{message}</p>}
        {actionError && <p role="alert">{actionError}</p>}
        <div className="hd-response-actions">
          <button className="hd-button hd-button-secondary" disabled={busy || !pending}
            onClick={() => send(alertPath + "/acknowledge", undefined, "Alert acknowledged.")}>Acknowledge</button>
          <button className="hd-button hd-button-primary" disabled={busy || !acknowledged}
            onClick={() => send(alertPath + "/accept", undefined, "Response accepted.")}>Accept response</button>
          <button className="hd-button hd-button-danger-outline" disabled={busy || !acknowledged}
            onClick={() => { setAction("decline"); setReason(""); }}>Decline</button>
          {current.status === "Accepted" && <button className="hd-button hd-button-secondary" disabled={busy}
            onClick={() => { if (window.confirm("Close this incident?")) send(incidentPath + "/close", {}, "Incident closed."); }}>Close incident</button>}
          {canWrite && <button className="hd-text-link" disabled={busy}
            onClick={() => { setAction("report"); setReason(""); }}>Report possible false alarm</button>}
        </div>
        {action && <form className="hd-action-form" onSubmit={saveReason}>
          <label htmlFor="hd-reason">{action === "decline" ? "Reason for declining" : "Reason for review"}</label>
          <textarea id="hd-reason" required value={reason} maxLength={action === "decline" ? 500 : 1000}
            onChange={(event) => setReason(event.target.value)} />
          <div>
            <button type="submit" className="hd-button hd-button-primary"
              disabled={busy || (action === "decline" ? !acknowledged || !reason.trim() : !canWrite || reason.trim().length < 3)}>Submit</button>
            <button type="button" className="hd-button hd-button-secondary" disabled={busy}
              onClick={() => setAction("")}>Back</button>
          </div>
        </form>}
        <h4>Response notes</h4>
        {detail?.notes?.map((item, index) => <p key={item.id ?? index}>{item.body}</p>)}
        {canWrite && <form className="hd-action-form" onSubmit={async (event) => {
          event.preventDefault();
          if (note.trim() && await send(incidentPath + "/notes", { body: note.trim() }, "Note saved.")) setNote("");
        }}>
          <label htmlFor="hd-note">Add a response note</label>
          <textarea id="hd-note" maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} />
          <button type="submit" className="hd-button hd-button-secondary" disabled={busy || !note.trim()}>Save note</button>
        </form>}
        <h4>Incident timeline</h4>
        <div className="hd-detail-timeline">
          {timeline?.length ? [...timeline].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)).map((event, index) =>
            <div key={event.id ?? index}><span /><strong>{event.message || event.event_type}</strong>
              <small>{event.actor_label || "System"} · {formatDateTime(Date.parse(event.created_at))}</small></div>
          ) : <p>{timeline ? "No timeline entries." : "Timeline unavailable."}</p>}
        </div>
      </div>
    </section>
  </div>;
}
