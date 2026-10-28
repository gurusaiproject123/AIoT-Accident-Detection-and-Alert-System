/*
 * Superuser demo data, navigation and formatting helpers.
 *
 * Every record in this file is FICTIONAL. Hospital names are used as
 * sample labels only and do not imply any partnership. Phone numbers are
 * placeholders and email addresses use the reserved example.com domain.
 *
 * Replace these fixtures with authenticated FastAPI requests during
 * backend integration (see api.js).
 */

export const STORAGE_KEY = "aiot-superuser-demo-v1";
export const DEMO_ACTOR = "Demo superuser";
export const BASE_PATH = "/superuser";

/* ------------------------------------------------------------------ */
/* Navigation                                                          */
/* ------------------------------------------------------------------ */

export const NAV_ITEMS = [
  { to: "", label: "Overview", icon: "grid", end: true },
  { to: "incidents", label: "Incidents", icon: "bell" },
  { to: "devices", label: "Devices", icon: "cpu" },
  { to: "hospitals", label: "Hospitals", icon: "building" },
  { to: "users", label: "Users and roles", icon: "users" },
  { to: "activity", label: "Activity history", icon: "clock" },
];

/* ------------------------------------------------------------------ */
/* Status vocabularies                                                 */
/* ------------------------------------------------------------------ */

export const INCIDENT_STATUS = {
  cancellation_window: { label: "Cancellation window", tone: "amber" },
  cancelled: { label: "Cancelled", tone: "grey" },
  notified: { label: "Hospital notified", tone: "red" },
  acknowledged: { label: "Acknowledged", tone: "blue" },
  accepted: { label: "Accepted", tone: "green" },
  escalated: { label: "Escalated", tone: "amber" },
  closed: { label: "Closed", tone: "purple" },
};

export const NOTIFICATION_STATUS = {
  notified: { label: "Awaiting response", tone: "red" },
  acknowledged: { label: "Acknowledged", tone: "blue" },
  accepted: { label: "Accepted", tone: "green" },
  declined: { label: "Declined", tone: "grey" },
  timed_out: { label: "No response", tone: "amber" },
};

export const DEVICE_STATUS = {
  online: { label: "Online", tone: "green" },
  offline: { label: "Offline", tone: "grey" },
  fault: { label: "Sensor fault", tone: "red" },
};

export const GPS_STATUS = {
  fix: { label: "GPS fix", tone: "green" },
  stale: { label: "Location outdated", tone: "amber" },
  none: { label: "No GPS fix", tone: "red" },
};

export const ROLES = {
  superuser: { label: "Superuser", tone: "purple" },
  hospital_staff: { label: "Hospital staff", tone: "blue" },
  unassigned: { label: "No role assigned", tone: "grey" },
};

export const USER_STATUS = {
  active: { label: "Active", tone: "green" },
  suspended: { label: "Suspended", tone: "grey" },
};

export const AUDIT_CATEGORIES = {
  incident: "Incident",
  hospital: "Hospital",
  user: "User",
  device: "Device",
  system: "System",
};

/* ------------------------------------------------------------------ */
/* Seed data                                                           */
/* ------------------------------------------------------------------ */

const MIN = 60 * 1000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

/**
 * Builds a fresh set of demo records with timestamps relative to `now`,
 * so the demo always looks current right after loading or resetting.
 */
export function buildSeed(now = Date.now()) {
  const ago = (ms) => new Date(now - ms).toISOString();

  const hospitals = [
    {
      id: "HSP-001",
      name: "Bindura Hospital",
      city: "Bindura",
      address: "Chipadze Road, Bindura",
      phone: "+263 000 000 101",
      email: "emergency.bindura@example.com",
      lat: -17.3019,
      lng: 31.3306,
      active: true,
      registeredAt: ago(120 * DAY),
    },
    {
      id: "HSP-002",
      name: "Mazowe District Hospital",
      city: "Mazowe",
      address: "Main Road, Concession",
      phone: "+263 000 000 102",
      email: "casualty.mazowe@example.com",
      lat: -17.5101,
      lng: 30.9711,
      active: true,
      registeredAt: ago(96 * DAY),
    },
    {
      id: "HSP-003",
      name: "Shamva District Hospital",
      city: "Shamva",
      address: "Hospital Road, Shamva",
      phone: "+263 000 000 103",
      email: "er.shamva@example.com",
      lat: -17.3127,
      lng: 31.5703,
      active: true,
      registeredAt: ago(80 * DAY),
    },
    {
      id: "HSP-004",
      name: "Harare Central Hospital",
      city: "Harare",
      address: "Lobengula Road, Southerton",
      phone: "+263 000 000 104",
      email: "trauma.harare@example.com",
      lat: -17.8622,
      lng: 31.0217,
      active: true,
      registeredAt: ago(60 * DAY),
    },
    {
      id: "HSP-005",
      name: "Glendale Clinic",
      city: "Glendale",
      address: "Glendale Township",
      phone: "+263 000 000 105",
      email: "clinic.glendale@example.com",
      lat: -17.3539,
      lng: 31.0678,
      active: false,
      registeredAt: ago(30 * DAY),
    },
  ];

  const devices = [
    {
      id: "ESP32-A01",
      vehicle: "DEMO-AB 1234",
      vehicleModel: "Toyota Corolla · Silver",
      owner: "Demo owner one",
      status: "online",
      gps: "fix",
      lastSeen: ago(0.4 * MIN),
      firmware: "0.4.2",
      lat: -17.3205,
      lng: 31.3101,
    },
    {
      id: "ESP32-A02",
      vehicle: "DEMO-CD 5678",
      vehicleModel: "Honda Fit · Blue",
      owner: "Demo owner two",
      status: "online",
      gps: "fix",
      lastSeen: ago(1.2 * MIN),
      firmware: "0.4.2",
      lat: -17.4012,
      lng: 31.1888,
    },
    {
      id: "ESP32-A03",
      vehicle: "DEMO-EF 9012",
      vehicleModel: "Nissan NP200 · White",
      owner: "Demo owner three",
      status: "online",
      gps: "stale",
      lastSeen: ago(3 * MIN),
      firmware: "0.4.1",
      lat: -17.5502,
      lng: 31.0103,
    },
    {
      id: "ESP32-A04",
      vehicle: "DEMO-GH 3456",
      vehicleModel: "Toyota Hilux · Red",
      owner: "Demo owner four",
      status: "offline",
      gps: "none",
      lastSeen: ago(5 * HOUR),
      firmware: "0.3.9",
      lat: null,
      lng: null,
    },
    {
      id: "ESP32-A05",
      vehicle: "DEMO-JK 7890",
      vehicleModel: "Mazda Demio · Black",
      owner: "Demo owner five",
      status: "fault",
      gps: "fix",
      lastSeen: ago(12 * MIN),
      firmware: "0.4.0",
      lat: -17.3104,
      lng: 31.5402,
    },
    {
      id: "ESP32-TEST",
      vehicle: "Lab prototype car",
      vehicleModel: "RC test chassis",
      owner: "Project team",
      status: "online",
      gps: "fix",
      lastSeen: ago(0.2 * MIN),
      firmware: "0.5.0-dev",
      lat: -17.3022,
      lng: 31.3299,
    },
  ];

  const users = [
    {
      id: "USR-001",
      name: "Demo superuser",
      email: "superuser@example.com",
      role: "superuser",
      hospitalId: null,
      status: "active",
      lastSignIn: ago(2 * MIN),
    },
    {
      id: "USR-002",
      name: "Response operator",
      email: "operator.bindura@example.com",
      role: "hospital_staff",
      hospitalId: "HSP-001",
      status: "active",
      lastSignIn: ago(35 * MIN),
    },
    {
      id: "USR-003",
      name: "Casualty nurse",
      email: "nurse.mazowe@example.com",
      role: "hospital_staff",
      hospitalId: "HSP-002",
      status: "active",
      lastSignIn: ago(4 * HOUR),
    },
    {
      id: "USR-004",
      name: "Trauma desk",
      email: "desk.harare@example.com",
      role: "hospital_staff",
      hospitalId: "HSP-004",
      status: "active",
      lastSignIn: ago(1 * DAY),
    },
    {
      id: "USR-005",
      name: "Night shift lead",
      email: "night.shamva@example.com",
      role: "hospital_staff",
      hospitalId: "HSP-003",
      status: "suspended",
      lastSignIn: ago(9 * DAY),
    },
    {
      id: "USR-006",
      name: "New team member",
      email: "pending.user@example.com",
      role: "unassigned",
      hospitalId: null,
      status: "active",
      lastSignIn: null,
    },
  ];

  const incidents = [
    {
      id: "INC-1052",
      deviceId: "ESP32-A02",
      detectedAt: ago(1.5 * MIN),
      location: { label: "A11 Bindura–Harare Road, km 28", lat: -17.4012, lng: 31.1888 },
      modelScore: 0.91,
      impact: "Sudden deceleration and roll detected",
      status: "cancellation_window",
      cancellation: { windowSeconds: 30, outcome: "pending", by: null, at: null },
      notifications: [],
      timeline: [
        { at: ago(1.5 * MIN), type: "detected", text: "Suspected accident detected by device ESP32-A02.", actor: "System" },
        { at: ago(1.5 * MIN), type: "window", text: "30 second local cancellation window started.", actor: "System" },
      ],
      notes: [],
    },
    {
      id: "INC-1051",
      deviceId: "ESP32-A01",
      detectedAt: ago(14 * MIN),
      location: { label: "Chipadze Road, Bindura", lat: -17.3205, lng: 31.3101 },
      modelScore: 0.87,
      impact: "Front impact signature",
      status: "notified",
      cancellation: { windowSeconds: 30, outcome: "expired", by: null, at: ago(13.5 * MIN) },
      notifications: [
        { hospitalId: "HSP-001", status: "notified", notifiedAt: ago(13.4 * MIN), acknowledgedAt: null, respondedAt: null, reason: null },
      ],
      timeline: [
        { at: ago(14 * MIN), type: "detected", text: "Suspected accident detected by device ESP32-A01.", actor: "System" },
        { at: ago(13.5 * MIN), type: "window", text: "Cancellation window expired without cancellation.", actor: "System" },
        { at: ago(13.4 * MIN), type: "notified", text: "Bindura Hospital notified (nearest active hospital).", actor: "System" },
      ],
      notes: [],
    },
    {
      id: "INC-1050",
      deviceId: "ESP32-A03",
      detectedAt: ago(52 * MIN),
      location: { label: "Mazowe Road near Concession", lat: -17.5502, lng: 31.0103 },
      modelScore: 0.78,
      impact: "Side impact signature",
      status: "escalated",
      cancellation: { windowSeconds: 30, outcome: "expired", by: null, at: ago(51.5 * MIN) },
      notifications: [
        { hospitalId: "HSP-002", status: "timed_out", notifiedAt: ago(51.4 * MIN), acknowledgedAt: null, respondedAt: null, reason: null },
        { hospitalId: "HSP-004", status: "notified", notifiedAt: ago(46.4 * MIN), acknowledgedAt: null, respondedAt: null, reason: null },
      ],
      timeline: [
        { at: ago(52 * MIN), type: "detected", text: "Suspected accident detected by device ESP32-A03.", actor: "System" },
        { at: ago(51.5 * MIN), type: "window", text: "Cancellation window expired without cancellation.", actor: "System" },
        { at: ago(51.4 * MIN), type: "notified", text: "Mazowe District Hospital notified.", actor: "System" },
        { at: ago(46.4 * MIN), type: "timeout", text: "No acknowledgment from Mazowe District Hospital within 5 minutes.", actor: "System" },
        { at: ago(46.4 * MIN), type: "escalated", text: "Escalated to Harare Central Hospital (level 2).", actor: "System" },
      ],
      notes: [],
    },
    {
      id: "INC-1049",
      deviceId: "ESP32-A05",
      detectedAt: ago(3 * HOUR),
      location: { label: "Shamva Road, km 12", lat: -17.3104, lng: 31.5402 },
      modelScore: 0.83,
      impact: "Rear impact signature",
      status: "accepted",
      cancellation: { windowSeconds: 30, outcome: "expired", by: null, at: ago(3 * HOUR - 0.5 * MIN) },
      notifications: [
        { hospitalId: "HSP-003", status: "accepted", notifiedAt: ago(3 * HOUR - 0.6 * MIN), acknowledgedAt: ago(3 * HOUR - 2 * MIN), respondedAt: ago(3 * HOUR - 4 * MIN), reason: null },
      ],
      timeline: [
        { at: ago(3 * HOUR), type: "detected", text: "Suspected accident detected by device ESP32-A05.", actor: "System" },
        { at: ago(3 * HOUR - 0.5 * MIN), type: "window", text: "Cancellation window expired without cancellation.", actor: "System" },
        { at: ago(3 * HOUR - 0.6 * MIN), type: "notified", text: "Shamva District Hospital notified.", actor: "System" },
        { at: ago(3 * HOUR - 2 * MIN), type: "ack", text: "Shamva District Hospital acknowledged the alert.", actor: "Night shift lead" },
        { at: ago(3 * HOUR - 4 * MIN), type: "accept", text: "Shamva District Hospital accepted the response.", actor: "Night shift lead" },
      ],
      notes: [],
    },
    {
      id: "INC-1048",
      deviceId: "ESP32-A01",
      detectedAt: ago(6 * HOUR),
      location: { label: "Bindura town centre", lat: -17.3022, lng: 31.3299 },
      modelScore: 0.69,
      impact: "Hard braking with tilt",
      status: "acknowledged",
      cancellation: { windowSeconds: 30, outcome: "expired", by: null, at: ago(6 * HOUR - 0.5 * MIN) },
      notifications: [
        { hospitalId: "HSP-001", status: "acknowledged", notifiedAt: ago(6 * HOUR - 0.6 * MIN), acknowledgedAt: ago(6 * HOUR - 1.5 * MIN), respondedAt: null, reason: null },
      ],
      timeline: [
        { at: ago(6 * HOUR), type: "detected", text: "Suspected accident detected by device ESP32-A01.", actor: "System" },
        { at: ago(6 * HOUR - 0.5 * MIN), type: "window", text: "Cancellation window expired without cancellation.", actor: "System" },
        { at: ago(6 * HOUR - 0.6 * MIN), type: "notified", text: "Bindura Hospital notified.", actor: "System" },
        { at: ago(6 * HOUR - 1.5 * MIN), type: "ack", text: "Bindura Hospital acknowledged the alert.", actor: "Response operator" },
      ],
      notes: [],
    },
    {
      id: "INC-1047",
      deviceId: "ESP32-TEST",
      detectedAt: ago(1 * DAY),
      location: { label: "Campus test track", lat: -17.3019, lng: 31.3306 },
      modelScore: 0.74,
      impact: "Lab drop test",
      status: "cancelled",
      cancellation: { windowSeconds: 30, outcome: "cancelled", by: "Project team (vehicle page)", at: ago(1 * DAY - 0.2 * MIN) },
      notifications: [],
      timeline: [
        { at: ago(1 * DAY), type: "detected", text: "Suspected accident detected by device ESP32-TEST.", actor: "System" },
        { at: ago(1 * DAY - 0.2 * MIN), type: "cancelled", text: "Cancelled as a false alarm during the cancellation window.", actor: "Project team" },
      ],
      notes: [],
    },
    {
      id: "INC-1046",
      deviceId: "ESP32-A02",
      detectedAt: ago(2 * DAY),
      location: { label: "Harare Drive, Mount Pleasant", lat: -17.7701, lng: 31.0502 },
      modelScore: 0.88,
      impact: "Front impact signature",
      status: "closed",
      cancellation: { windowSeconds: 30, outcome: "expired", by: null, at: ago(2 * DAY - 0.5 * MIN) },
      notifications: [
        { hospitalId: "HSP-004", status: "declined", notifiedAt: ago(2 * DAY - 0.6 * MIN), acknowledgedAt: ago(2 * DAY - 1.4 * MIN), respondedAt: ago(2 * DAY - 2 * MIN), reason: "Trauma unit at capacity." },
        { hospitalId: "HSP-001", status: "accepted", notifiedAt: ago(2 * DAY - 2.1 * MIN), acknowledgedAt: ago(2 * DAY - 3 * MIN), respondedAt: ago(2 * DAY - 4 * MIN), reason: null },
      ],
      timeline: [
        { at: ago(2 * DAY), type: "detected", text: "Suspected accident detected by device ESP32-A02.", actor: "System" },
        { at: ago(2 * DAY - 0.5 * MIN), type: "window", text: "Cancellation window expired without cancellation.", actor: "System" },
        { at: ago(2 * DAY - 0.6 * MIN), type: "notified", text: "Harare Central Hospital notified.", actor: "System" },
        { at: ago(2 * DAY - 1.4 * MIN), type: "ack", text: "Harare Central Hospital acknowledged the alert.", actor: "Trauma desk" },
        { at: ago(2 * DAY - 2 * MIN), type: "decline", text: "Harare Central Hospital declined: Trauma unit at capacity.", actor: "Trauma desk" },
        { at: ago(2 * DAY - 2.1 * MIN), type: "escalated", text: "Escalated to Bindura Hospital (level 2).", actor: "System" },
        { at: ago(2 * DAY - 3 * MIN), type: "ack", text: "Bindura Hospital acknowledged the alert.", actor: "Response operator" },
        { at: ago(2 * DAY - 4 * MIN), type: "accept", text: "Bindura Hospital accepted the response.", actor: "Response operator" },
        { at: ago(2 * DAY - 70 * MIN), type: "closed", text: "Incident closed by hospital.", actor: "Response operator" },
      ],
      notes: [],
    },
  ];

  const audit = [
    { id: "AUD-0009", at: ago(2 * MIN), actor: "Demo superuser", role: "superuser", category: "system", action: "Signed in", target: "Superuser dashboard", detail: "Demo session started." },
    { id: "AUD-0008", at: ago(46.4 * MIN), actor: "System", role: "system", category: "incident", action: "Escalated incident", target: "INC-1050", detail: "No response from Mazowe District Hospital; routed to Harare Central Hospital." },
    { id: "AUD-0007", at: ago(3 * HOUR - 4 * MIN), actor: "Night shift lead", role: "hospital_staff", category: "incident", action: "Accepted response", target: "INC-1049", detail: "Shamva District Hospital accepted the response." },
    { id: "AUD-0006", at: ago(9 * DAY), actor: "Demo superuser", role: "superuser", category: "user", action: "Suspended user", target: "night.shamva@example.com", detail: "Account suspended pending review." },
    { id: "AUD-0005", at: ago(1 * DAY - 0.2 * MIN), actor: "Project team", role: "device", category: "incident", action: "Cancelled false alarm", target: "INC-1047", detail: "Cancelled from the vehicle page during the cancellation window." },
    { id: "AUD-0004", at: ago(2 * DAY - 70 * MIN), actor: "Response operator", role: "hospital_staff", category: "incident", action: "Closed incident", target: "INC-1046", detail: "Response completed." },
    { id: "AUD-0003", at: ago(30 * DAY), actor: "Demo superuser", role: "superuser", category: "hospital", action: "Registered hospital", target: "HSP-005 Glendale Clinic", detail: "Registered as inactive until contacts are verified." },
    { id: "AUD-0002", at: ago(32 * DAY), actor: "Demo superuser", role: "superuser", category: "device", action: "Registered device", target: "ESP32-TEST", detail: "Lab prototype linked to the project team." },
    { id: "AUD-0001", at: ago(60 * DAY), actor: "Demo superuser", role: "superuser", category: "hospital", action: "Registered hospital", target: "HSP-004 Harare Central Hospital", detail: "Added to the notification network." },
  ];

  return { hospitals, devices, users, incidents, audit, preferences: { animations: true } };
}

/* ------------------------------------------------------------------ */
/* Formatting helpers                                                  */
/* ------------------------------------------------------------------ */

export function formatDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function formatRelative(iso, now) {
  if (!iso) return "Never";
  const diff = Math.max(0, now - new Date(iso).getTime());
  if (diff < MIN) return "Just now";
  if (diff < HOUR) return `${Math.floor(diff / MIN)} min ago`;
  if (diff < DAY) return `${Math.floor(diff / HOUR)} h ago`;
  const days = Math.floor(diff / DAY);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

export function formatCoords(lat, lng) {
  if (lat == null || lng == null) return "Location unavailable";
  return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
}

export function mapsUrl(lat, lng) {
  if (lat == null || lng == null) return null;
  return `https://www.google.com/maps?q=${lat},${lng}`;
}

export function initials(name = "") {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

export function pad2(value) {
  return String(value).padStart(2, "0");
}

/** Converts an array of flat objects to a CSV string. */
export function toCsv(rows, columns) {
  const escape = (value) => {
    const text = value == null ? "" : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const header = columns.map((c) => escape(c.label)).join(",");
  const body = rows.map((row) => columns.map((c) => escape(c.value(row))).join(","));
  return [header, ...body].join("\n");
}

export function downloadFile(filename, content, type = "text/csv;charset=utf-8") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Generates the next sequential ID such as HSP-006 or USR-007. */
export function nextId(prefix, records, width = 3) {
  const max = records.reduce((highest, record) => {
    const number = Number.parseInt(String(record.id).split("-").pop(), 10);
    return Number.isNaN(number) ? highest : Math.max(highest, number);
  }, 0);
  return `${prefix}-${String(max + 1).padStart(width, "0")}`;
}

