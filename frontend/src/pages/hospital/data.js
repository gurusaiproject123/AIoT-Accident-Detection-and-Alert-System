// Demonstration fixtures only. Replace with authorised backend responses.
export const HOSPITAL = {
  id: "HSP-001",
  name: "Bindura Hospital",
  unit: "Emergency response desk",
};
export const NAV = [
  ["overview", "Overview", "grid"],
  ["incidents", "Assigned incidents", "bell"],
  ["operations", "Operations", "clock"],
  ["health", "Locations and health", "pulse"],
  ["reports", "Reports", "chart"],
];
// Fictional records used only by this prototype. Real records come from the
// authorised incident API, linked through device -> vehicle -> registered owner.
export const DEMO_VEHICLES = Object.fromEntries(
  [
    ["DEV-008", "DEMO-008", "Toyota", "Corolla", "Silver"],
    ["DEV-003", "DEMO-003", "Honda", "Fit", "Blue"],
    ["DEV-012", "DEMO-012", "Nissan", "Note", "White"],
    ["DEV-006", "DEMO-006", "Mazda", "Demio", "Red"],
    ["DEV-010", "DEMO-010", "Toyota", "Vitz", "Grey"],
    ["DEV-004", "DEMO-004", "Suzuki", "Swift", "Black"],
  ].map(([device, registration, make, model, colour]) => {
    const suffix = device.slice(-3);
    return [
      device,
      {
        vehicle: { registration, make, model, colour },
        owner: {
          name: `Sample owner ${suffix}`,
          phone: "+263 7XX XXX XXX",
          email: `owner${suffix}@example.com`,
          relationship: "Registered owner",
        },
      },
    ];
  }),
);

// Migrate older demo records without deleting their response history. Explicit
// null values stay unavailable; unknown devices are never assigned invented data.
export function withDemoVehicle(incident) {
  const fixture = DEMO_VEHICLES[incident.device];
  const assignedAt = incident.assignedAt ?? Date.now();
  const pending = incident.status === "New";
  return {
    ...incident,
    assignedAt,
    occurredAt:
      incident.occurredAt === undefined
        ? (incident.created ?? null)
        : incident.occurredAt,
    occurredAtSource:
      incident.occurredAtSource ||
      (incident.occurredAt === undefined
        ? "reported_time_estimate"
        : "provided"),
    acknowledgedAt: incident.acknowledgedAt ?? null,
    responseDeadline:
      incident.status === "Acknowledged"
        ? null
        : incident.responseDeadline === undefined
          ? pending
            ? assignedAt + RESPONSE_WINDOW_MS
            : null
          : incident.responseDeadline,
    attemptedHospitalIds: incident.attemptedHospitalIds || [HOSPITAL.id],
    escalation: incident.escalation || null,
    vehicle:
      incident.vehicle === undefined
        ? (fixture?.vehicle ?? null)
        : incident.vehicle,
    owner:
      incident.owner === undefined ? (fixture?.owner ?? null) : incident.owner,
  };
}

export function seedIncidents() {
  const now = Date.now();
  return [
    [
      "INC-1048",
      "DEV-008",
      "Bindura–Harare Road",
      "New",
      3,
      0.89,
      -17.337,
      31.318,
      4.2,
    ],
    [
      "INC-1047",
      "DEV-003",
      "Mazowe Road junction",
      "New",
      8,
      0.76,
      -17.305,
      31.297,
      3.6,
    ],
    [
      "INC-1046",
      "DEV-012",
      "Chipadze Road",
      "Acknowledged",
      17,
      0.82,
      -17.319,
      31.345,
      5.1,
    ],
    [
      "INC-1045",
      "DEV-006",
      "Shamva Road",
      "Accepted",
      31,
      0.91,
      -17.286,
      31.354,
      4.8,
    ],
    [
      "INC-1044",
      "DEV-010",
      "Hospital Road",
      "Closed",
      65,
      0.71,
      -17.298,
      31.327,
      3.1,
    ],
    ["INC-1043", "DEV-004", "Mazowe Road", "Closed", 94, 0.67, null, null, 2.9],
  ].map(([id, device, location, status, minutes, score, lat, lng, peak]) =>
    withDemoVehicle({
      id,
      device,
      location,
      status,
      score,
      lat,
      lng,
      peak,
      hospitalId: HOSPITAL.id,
      created: now - minutes * 60000,
      occurredAt: now - minutes * 60000,
      occurredAtSource: "simulated",
      gpsAge: lat === null ? null : 12,
      notes: [],
      timeline: [
        {
          text: "Suspected incident assigned to this hospital",
          at: now - minutes * 60000,
          user: "Demo routing service",
        },
      ],
    }),
  );
}
export function loadState() {
  try {
    const s = JSON.parse(localStorage.getItem("aiot-hospital-demo-v1"));
    if (
      s?.incidents?.every((i) => i.hospitalId === HOSPITAL.id) &&
      Array.isArray(s.incidents) &&
      s.incidents.length
    )
      return { ...s, incidents: s.incidents.map(withDemoVehicle) };
  } catch {
    /* Use demo defaults if storage is unavailable. */
  }
  return { incidents: seedIncidents(), motion: true };
}
export const time = (t) =>
  new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
export const date = (t) =>
  new Date(t).toLocaleDateString([], { day: "numeric", month: "short" });

export const RESPONSE_WINDOW_MS = 3 * 60 * 1000;
// Fictional participating hospitals and coordinates for routing demonstrations.
export const DEMO_HOSPITALS = [
  {
    id: "HSP-001",
    name: "Bindura Hospital",
    lat: -17.3,
    lng: 31.33,
    active: true,
  },
  {
    id: "HSP-002",
    name: "Mazowe Demo Hospital",
    lat: -17.52,
    lng: 30.98,
    active: true,
  },
  {
    id: "HSP-003",
    name: "Shamva Demo Hospital",
    lat: -17.31,
    lng: 31.57,
    active: true,
  },
  {
    id: "HSP-004",
    name: "Harare Demo Hospital",
    lat: -17.78,
    lng: 31.04,
    active: true,
  },
];
export const isAwaitingAcknowledgment = (incident) => incident.status === "New";
export function distanceKm(aLat, aLng, bLat, bLng) {
  const radians = (value) => (value * Math.PI) / 180;
  const dLat = radians(bLat - aLat),
    dLng = radians(bLng - aLng);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(radians(aLat)) * Math.cos(radians(bLat)) * Math.sin(dLng / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
}
export function nextHospital(incident, hospitals = DEMO_HOSPITALS) {
  if (
    !Number.isFinite(incident.lat) ||
    !Number.isFinite(incident.lng) ||
    Math.abs(incident.lat) > 90 ||
    Math.abs(incident.lng) > 180
  )
    return null;
  const tried = new Set([
    incident.hospitalId,
    ...(incident.attemptedHospitalIds || []),
  ]);
  return (
    hospitals
      .filter(
        (h) =>
          h.active &&
          !tried.has(h.id) &&
          Number.isFinite(h.lat) &&
          Number.isFinite(h.lng),
      )
      .map((h) => ({
        ...h,
        distanceKm: distanceKm(incident.lat, incident.lng, h.lat, h.lng),
      }))
      .sort(
        (a, b) => a.distanceKm - b.distanceKm || a.id.localeCompare(b.id),
      )[0] || null
  );
}
export function escalateIncident(
  incident,
  trigger,
  reason,
  now = Date.now(),
  hospitals = DEMO_HOSPITALS,
) {
  if (
    incident.escalation ||
    ["Accepted", "Closed", "Escalated", "Escalation pending"].includes(
      incident.status,
    )
  )
    return incident;
  const next = nextHospital(incident, hospitals);
  const escalation = {
    trigger,
    reason,
    at: now,
    toHospitalId: next?.id || null,
    toHospitalName: next?.name || null,
    distanceKm: next?.distanceKm ?? null,
    delivery: "Simulated",
  };
  const text = next
    ? `Demo escalation to ${next.name} (${next.distanceKm.toFixed(1)} km straight-line). Reason: ${reason}. No live notification sent.`
    : `Escalation pending: ${!Number.isFinite(incident.lat) || !Number.isFinite(incident.lng) ? "valid GPS unavailable" : "no eligible alternative hospital"}. Reason: ${reason}. Manual routing review required.`;
  return {
    ...incident,
    status: next ? "Escalated" : "Escalation pending",
    escalation,
    attemptedHospitalIds: [
      ...new Set([
        ...(incident.attemptedHospitalIds || []),
        incident.hospitalId,
        ...(next ? [next.id] : []),
      ]),
    ],
    timeline: [
      ...incident.timeline,
      { text, at: now, user: "Demo escalation service" },
    ],
  };
}
export function expireIncident(incident, now = Date.now()) {
  return isAwaitingAcknowledgment(incident) &&
    Number.isFinite(incident.responseDeadline) &&
    now >= incident.responseDeadline
    ? escalateIncident(
        incident,
        "timeout",
        "No acknowledgment within the three-minute deadline",
        now,
      )
    : incident;
}

// Public fixture credential for UI demonstrations ONLY. This is not an account
// password and provides no production identity verification.
export const DEMO_CONFIRMATION_PASSWORD = "DemoConfirm!2026";
export const DEMO_STAFF = [
  {
    id: "STAFF-001",
    name: "Demo Nurse Alpha",
    role: "Nurse",
    hospitalId: HOSPITAL.id,
    active: true,
  },
  {
    id: "STAFF-002",
    name: "Demo Doctor Beta",
    role: "Doctor",
    hospitalId: HOSPITAL.id,
    active: true,
  },
  {
    id: "STAFF-003",
    name: "Demo Response Officer Gamma",
    role: "Response officer",
    hospitalId: HOSPITAL.id,
    active: true,
  },
];
export function verifyDemoStaff(staffId, password) {
  const staff = DEMO_STAFF.find(
    (person) =>
      person.id === staffId &&
      person.hospitalId === HOSPITAL.id &&
      person.active,
  );
  if (!staff)
    throw new Error("Select an active staff member from this hospital.");
  if (password !== DEMO_CONFIRMATION_PASSWORD)
    throw new Error("Incorrect demo confirmation password.");
  return {
    actorName: staff.name,
    actorId: staff.id,
    confirmationMethod: "demo_password",
    identityVerified: false,
  };
}
export const formatDateTime = (value) =>
  Number.isFinite(value)
    ? new Date(value).toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        timeZoneName: "short",
      })
    : "Not recorded";
const isoTime = (value) =>
  Number.isFinite(value) ? new Date(value).toISOString() : "";
function safeExport(value) {
  if (Array.isArray(value)) return value.map(safeExport);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .filter(
          ([key]) => !/password|secret|access.?token|refresh.?token/i.test(key),
        )
        .map(([key, item]) => [key, safeExport(item)]),
    );
  return value;
}
export function incidentExportRows(incidents) {
  return incidents.map((i) => ({
    "Incident ID": i.id,
    "Hospital ID": i.hospitalId,
    "Hospital name": i.hospitalId === HOSPITAL.id ? HOSPITAL.name : "",
    "Device ID": i.device,
    Status: i.status,
    Location: i.location,
    "Incident time UTC": isoTime(i.occurredAt),
    "Incident time source": i.occurredAtSource || "Not recorded",
    "Reported time UTC": isoTime(i.created),
    "Assigned time UTC": isoTime(i.assignedAt),
    "GPS latitude": i.lat ?? "",
    "GPS longitude": i.lng ?? "",
    "GPS age at detection seconds": i.gpsAge ?? "",
    "GPS accuracy metres": i.gpsAccuracy ?? "",
    "Model score": i.score ?? "",
    "Peak acceleration g": i.peak ?? "",
    "Vehicle registration": i.vehicle?.registration || "",
    "Vehicle make": i.vehicle?.make || "",
    "Vehicle model": i.vehicle?.model || "",
    "Vehicle colour": i.vehicle?.colour || "",
    "Owner name": i.owner?.name || "",
    "Owner relationship": i.owner?.relationship || "",
    "Owner phone": i.owner?.phone || "",
    "Owner email": i.owner?.email || "",
    "Acknowledged by": i.acknowledgedBy || "",
    "Acknowledged time UTC": isoTime(i.acknowledgedAt),
    "Accepted by": i.acceptedBy || "",
    "Accepted time UTC": isoTime(i.acceptedAt),
    "Declined by": i.declinedBy || "",
    "Declined time UTC": isoTime(i.declinedAt),
    "Closed by": i.closedBy || "",
    "Closed time UTC": isoTime(i.closedAt),
    "Acknowledgment deadline UTC": isoTime(i.responseDeadline),
    "Escalation destination ID": i.escalation?.toHospitalId || "",
    "Escalation destination": i.escalation?.toHospitalName || "",
    "Escalation trigger": i.escalation?.trigger || "",
    "Escalation reason": i.escalation?.reason || "",
    "Escalation time UTC": isoTime(i.escalation?.at),
    "Escalation distance km": i.escalation?.distanceKm ?? "",
    "Escalation delivery": i.escalation?.delivery || "",
    "Attempted hospitals JSON": JSON.stringify(i.attemptedHospitalIds || []),
    "Response notes JSON": JSON.stringify(safeExport(i.notes || [])),
    "Audit history JSON": JSON.stringify(safeExport(i.timeline || [])),
    "Incident details JSON": JSON.stringify(safeExport(i)),
  }));
}
export function buildIncidentCsv(incidents) {
  const records = incidentExportRows(incidents);
  if (!records.length) return "\uFEFFIncident ID\r\n";
  const fields = Object.keys(records[0]);
  const cell = (value) => {
    let text = String(value ?? "");
    // Prevent names/notes/phone fields from becoming spreadsheet formulas.
    if (
      typeof value !== "number" &&
      (/^\s*[=+@-]/.test(text) || /^[\t\r\n]/.test(text))
    )
      text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  };
  return (
    "\uFEFF" +
    [
      fields.map(cell).join(","),
      ...records.map((row) => fields.map((key) => cell(row[key])).join(",")),
    ].join("\r\n")
  );
}
