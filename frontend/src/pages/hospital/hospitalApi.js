const base = (import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export async function hospitalRequest(token, path, { signal, method = "GET", body } = {}) {
  if (!token) throw new Error("Sign in again to access hospital alerts.");
  const timeout = AbortSignal.timeout(12000);
  const response = await fetch(base + path, {
    method, cache: "no-store", signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    headers: { Authorization: `Bearer ${token}`, ...(body !== undefined && { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(typeof result?.detail === "string" ? result.detail :
      `Hospital API request failed (HTTP ${response.status}).`);
    error.status = response.status;
    throw error;
  }
  if (result === null) throw new Error("The hospital API returned no JSON data.");
  return result;
}

const timestamp = (value) => value ? Date.parse(value) : null;
const statuses = { notified: "New", acknowledged: "Acknowledged", accepted: "Accepted",
  declined: "Declined", timed_out: "Timed out", withdrawn: "Withdrawn" };

export function mapAlert(alert) {
  const incident = alert.incident ?? {};
  const hasLocation = incident.location_available !== false &&
    Number.isFinite(incident.latitude) && Number.isFinite(incident.longitude);
  const status = incident.status === "closed" ? "Closed" :
    statuses[alert.status] ?? alert.status ?? "Unknown";
  const score = incident.model_score;
  return {
    id: alert.id, incidentId: alert.incident_id, code: incident.code ?? alert.incident_id,
    hospital: alert.hospital, status,
    device: incident.device_code ?? "Device unavailable",
    location: incident.location_label || (hasLocation ? "GPS coordinates available" : "Location unavailable"),
    lat: hasLocation ? incident.latitude : null, lng: hasLocation ? incident.longitude : null,
    score: score != null && Number.isFinite(Number(score)) ? Number(score) : null,
    impactSummary: incident.impact_summary,
    created: timestamp(alert.notified_at),
    detected: timestamp(incident.detected_at),
    assignedAt: timestamp(alert.notified_at),
    responseDeadline: timestamp(alert.response_deadline),
    acknowledgedAt: timestamp(alert.acknowledged_at),
    respondedAt: timestamp(alert.responded_at),
    declineReason: alert.decline_reason,
    vehicle: incident.vehicle, owner: incident.owner,
  };
}
