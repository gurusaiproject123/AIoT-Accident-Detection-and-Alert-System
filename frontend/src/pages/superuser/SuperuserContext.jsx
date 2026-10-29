import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SuperuserContext } from "./useSuperuser";
import { DEMO_ACTOR, STORAGE_KEY, buildSeed, nextId } from "./data";
import { validateUserAssignment, publicUserRecord } from "./userRules";

/*
 * SuperuserProvider
 * -----------------
 * Owns all demo state for the superuser module: incidents, devices,
 * hospitals, users, the audit trail and workspace preferences.
 *
 * Everything is stored in browser localStorage for the demonstration.
 * During backend integration each action below should become a FastAPI
 * request, and the UI should only show a completed action after the
 * server confirms it. FastAPI must verify superuser access itself —
 * hiding controls in React is not access control.
 */

function loadInitialState() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && Array.isArray(parsed.incidents) && Array.isArray(parsed.hospitals)) {
        const state = { ...buildSeed(), ...parsed };
        return { ...state, users: (Array.isArray(state.users) ? state.users : buildSeed().users).map(publicUserRecord) };
      }
    }
  } catch {
    // Corrupt or unavailable storage: fall back to fresh demo data.
  }
  return buildSeed();
}

/** Rough straight-line distance used to pick the "nearest" demo hospital. */
function distanceKm(a, b) {
  const toRad = (deg) => (deg * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}

function nearestActiveHospital(hospitals, location, excludeIds = []) {
  const candidates = hospitals.filter((h) => h.active && !excludeIds.includes(h.id));
  if (!candidates.length) return null;
  if (location?.lat == null) return candidates[0];
  return [...candidates].sort(
    (a, b) => distanceKm(location, a) - distanceKm(location, b),
  )[0];
}

function makeAudit(audit, at, entry) {
  return [{ id: nextId("AUD", audit, 4), at, ...entry }, ...audit];
}

/** Moves incidents whose local cancellation window has passed into the hospital flow. */
function expireCancellationWindows(state, now) {
  let changed = false;
  let audit = state.audit;

  const incidents = state.incidents.map((incident) => {
    if (incident.status !== "cancellation_window") return incident;
    const deadline =
      new Date(incident.detectedAt).getTime() + incident.cancellation.windowSeconds * 1000;
    if (now < deadline) return incident;

    changed = true;
    const at = new Date(deadline).toISOString();
    const hospital = nearestActiveHospital(state.hospitals, incident.location);
    const timeline = [
      ...incident.timeline,
      { at, type: "window", text: "Cancellation window expired without cancellation.", actor: "System" },
    ];

    if (!hospital) {
      timeline.push({
        at,
        type: "timeout",
        text: "No active hospital available for notification. Superuser action required.",
        actor: "System",
      });
      audit = makeAudit(audit, at, {
        actor: "System",
        role: "system",
        category: "incident",
        action: "Routing failed",
        target: incident.id,
        detail: "No active hospital available.",
      });
      return {
        ...incident,
        status: "escalated",
        cancellation: { ...incident.cancellation, outcome: "expired", at },
        timeline,
      };
    }

    timeline.push({
      at,
      type: "notified",
      text: `${hospital.name} notified (nearest active hospital).`,
      actor: "System",
    });
    audit = makeAudit(audit, at, {
      actor: "System",
      role: "system",
      category: "incident",
      action: "Notified hospital",
      target: incident.id,
      detail: `${hospital.name} notified automatically.`,
    });

    return {
      ...incident,
      status: "notified",
      cancellation: { ...incident.cancellation, outcome: "expired", at },
      notifications: [
        {
          hospitalId: hospital.id,
          status: "notified",
          notifiedAt: at,
          acknowledgedAt: null,
          respondedAt: null,
          reason: null,
        },
      ],
      timeline,
    };
  });

  return changed ? { ...state, incidents, audit } : state;
}

export default function SuperuserProvider({ children }) {
  const [data, setData] = useState(loadInitialState);
  const [now, setNow] = useState(() => Date.now());
  const [toasts, setToasts] = useState([]);
  const toastTimers = useRef(new Map());

  const hasOpenWindow = data.incidents.some((i) => i.status === "cancellation_window");

  // Clock: tick every second while a cancellation countdown is visible,
  // otherwise every 30 seconds for "last seen" style labels.
  useEffect(() => {
    const id = window.setInterval(() => {
      const current = Date.now();
      setNow(current);
      setData((state) => expireCancellationWindows(state, current));
    }, hasOpenWindow ? 1000 : 30000);
    return () => window.clearInterval(id);
  }, [hasOpenWindow]);

  // Persist demo records.
  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch {
      // Storage full or blocked; the demo keeps working in memory.
    }
  }, [data]);

  // Clear any pending toast timers on unmount.
  useEffect(() => {
    const timers = toastTimers.current;
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, []);

  /* ---------------------------- Toasts ---------------------------- */

  const dismissToast = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id));
    const timer = toastTimers.current.get(id);
    if (timer) {
      window.clearTimeout(timer);
      toastTimers.current.delete(id);
    }
  }, []);

  const notify = useCallback(
    (message, tone = "green") => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((list) => [...list.slice(-3), { id, message, tone }]);
      toastTimers.current.set(
        id,
        window.setTimeout(() => dismissToast(id), 4200),
      );
    },
    [dismissToast],
  );

  /* --------------------------- Helpers ---------------------------- */

  /** Applies a change and records who performed it and when. */
  const commit = useCallback((updater, auditEntry) => {
    const at = new Date().toISOString();
    setData((state) => {
      const next = updater(state, at);
      if (!auditEntry) return next;
      const entry =
        typeof auditEntry === "function" ? auditEntry(state, next) : auditEntry;
      return {
        ...next,
        audit: makeAudit(next.audit, at, {
          actor: DEMO_ACTOR,
          role: "superuser",
          ...entry,
        }),
      };
    });
    setNow(Date.now());
  }, []);

  const updateIncident = (state, id, change) => ({
    ...state,
    incidents: state.incidents.map((incident) =>
      incident.id === id ? change(incident) : incident,
    ),
  });

  /* --------------------------- Incidents -------------------------- */

  const notifyHospital = useCallback(
    (incidentId, hospitalId) => {
      const hospital = data.hospitals.find((h) => h.id === hospitalId);
      if (!hospital) return;
      commit(
        (state, at) =>
          updateIncident(state, incidentId, (incident) => {
            const level = incident.notifications.length + 1;
            return {
              ...incident,
              status: incident.notifications.length ? "escalated" : "notified",
              notifications: [
                ...incident.notifications,
                {
                  hospitalId,
                  status: "notified",
                  notifiedAt: at,
                  acknowledgedAt: null,
                  respondedAt: null,
                  reason: null,
                },
              ],
              timeline: [
                ...incident.timeline,
                {
                  at,
                  type: level > 1 ? "escalated" : "notified",
                  text:
                    level > 1
                      ? `Manually escalated to ${hospital.name} (level ${level}).`
                      : `${hospital.name} notified manually.`,
                  actor: DEMO_ACTOR,
                },
              ],
            };
          }),
        {
          category: "incident",
          action: "Routed incident",
          target: incidentId,
          detail: `Notification sent to ${hospital.name}.`,
        },
      );
      notify(`${hospital.name} notified for ${incidentId}.`);
    },
    [commit, data.hospitals, notify],
  );

  const closeIncident = useCallback(
    (incidentId, note) => {
      commit(
        (state, at) =>
          updateIncident(state, incidentId, (incident) => ({
            ...incident,
            status: "closed",
            timeline: [
              ...incident.timeline,
              {
                at,
                type: "closed",
                text: note ? `Closed by superuser: ${note}` : "Closed by superuser.",
                actor: DEMO_ACTOR,
              },
            ],
          })),
        {
          category: "incident",
          action: "Closed incident",
          target: incidentId,
          detail: note || "Closed from the superuser dashboard.",
        },
      );
      notify(`${incidentId} closed.`, "purple");
    },
    [commit, notify],
  );

  const addIncidentNote = useCallback(
    (incidentId, text) => {
      commit(
        (state, at) =>
          updateIncident(state, incidentId, (incident) => ({
            ...incident,
            notes: [...incident.notes, { at, text, actor: DEMO_ACTOR }],
            timeline: [
              ...incident.timeline,
              { at, type: "note", text: `Note added: ${text}`, actor: DEMO_ACTOR },
            ],
          })),
        {
          category: "incident",
          action: "Added note",
          target: incidentId,
          detail: text,
        },
      );
      notify("Note added to the incident record.");
    },
    [commit, notify],
  );

  /** Creates a simulated detection so the full incident flow can be demonstrated. */
  const simulateIncident = useCallback(() => {
    const candidates = data.devices.filter((d) => d.status === "online" && d.lat != null);
    const device = candidates[Math.floor(Math.random() * candidates.length)] ?? data.devices[0];
    const id = nextId("INC", data.incidents, 4);
    commit(
      (state, at) => ({
        ...state,
        incidents: [
          {
            id,
            deviceId: device.id,
            detectedAt: at,
            location: {
              label: `Near ${device.vehicle} last known position`,
              lat: device.lat,
              lng: device.lng,
            },
            modelScore: Math.round((0.7 + Math.random() * 0.25) * 100) / 100,
            impact: "Simulated impact signature",
            status: "cancellation_window",
            cancellation: { windowSeconds: 30, outcome: "pending", by: null, at: null },
            notifications: [],
            timeline: [
              { at, type: "detected", text: `Simulated detection from ${device.id}.`, actor: "System" },
              { at, type: "window", text: "30 second local cancellation window started.", actor: "System" },
            ],
            notes: [],
          },
          ...state.incidents,
        ],
      }),
      {
        category: "incident",
        action: "Simulated detection",
        target: id,
        detail: `Demo incident created for ${device.id}.`,
      },
    );
    notify(`Simulated incident ${id} created. Cancellation window running.`, "amber");
    return id;
  }, [commit, data.devices, data.incidents, notify]);

  /* --------------------------- Hospitals -------------------------- */

  const saveHospital = useCallback(
    (hospital) => {
      const isNew = !hospital.id;
      const id = isNew ? nextId("HSP", data.hospitals) : hospital.id;
      commit(
        (state, at) => ({
          ...state,
          hospitals: isNew
            ? [...state.hospitals, { ...hospital, id, registeredAt: at }]
            : state.hospitals.map((h) => (h.id === id ? { ...h, ...hospital } : h)),
        }),
        {
          category: "hospital",
          action: isNew ? "Registered hospital" : "Updated hospital",
          target: `${id} ${hospital.name}`,
          detail: isNew
            ? `Registered as ${hospital.active ? "active" : "inactive"}.`
            : "Hospital details edited.",
        },
      );
      notify(isNew ? `${hospital.name} registered.` : `${hospital.name} updated.`);
      return id;
    },
    [commit, data.hospitals, notify],
  );

  const toggleHospital = useCallback(
    (id) => {
      const hospital = data.hospitals.find((h) => h.id === id);
      if (!hospital) return;
      const active = !hospital.active;
      commit(
        (state) => ({
          ...state,
          hospitals: state.hospitals.map((h) => (h.id === id ? { ...h, active } : h)),
        }),
        {
          category: "hospital",
          action: active ? "Activated hospital" : "Deactivated hospital",
          target: `${id} ${hospital.name}`,
          detail: active
            ? "Hospital can now receive incident notifications."
            : "Hospital will no longer receive new incident notifications.",
        },
      );
      notify(`${hospital.name} ${active ? "activated" : "deactivated"}.`, active ? "green" : "grey");
    },
    [commit, data.hospitals, notify],
  );

  /* ----------------------------- Users ---------------------------- */

  const activeSuperusers = data.users.filter(
    (u) => u.role === "superuser" && u.status === "active",
  );

  const saveUser = useCallback(
    (user) => {
      const errors = validateUserAssignment(user, data.hospitals, data.owners ?? []);
      if (Object.keys(errors).length) return { ok: false, error: Object.values(errors)[0] };
      if (user.role === "car_owner" && data.users.some(u => u.role === "car_owner" && u.ownerId === user.ownerId && u.id !== user.id)) {
        return { ok: false, error: "This registered owner already has a login account." };
      }
      const isNew = !user.id;
      const existing = data.users.find((u) => u.id === user.id);
      if (!isNew && !existing) return { ok: false, error: "User not found." };
      const losesSuperuser =
        existing?.role === "superuser" &&
        existing.status === "active" &&
        user.role !== "superuser";
      if (losesSuperuser && activeSuperusers.length <= 1) {
        return { ok: false, error: "At least one active superuser must remain." };
      }
      const emailTaken = data.users.some(
        (u) => u.email.toLowerCase() === user.email.toLowerCase() && u.id !== user.id,
      );
      if (emailTaken) {
        return { ok: false, error: "Another user already uses this email address." };
      }

      const id = isNew ? nextId("USR", data.users) : user.id;
      const record = publicUserRecord({
        ...existing, id, name: user.name.trim(), email: user.email.trim().toLowerCase(),
        role: user.role, hospitalId: user.role === "hospital_staff" ? user.hospitalId : null,
        ownerId: user.role === "car_owner" ? user.ownerId : null,
      });
      commit(
        (state) => ({
          ...state,
          users: isNew
            ? [...state.users, { ...record, status: "active", lastSignIn: null }]
            : state.users.map((u) => (u.id === id ? { ...u, ...record } : u)),
        }),
        {
          category: "user",
          action: isNew ? "Added demo user" : "Updated role assignment",
          target: record.email,
          detail: `Role: ${record.role}${record.hospitalId ? ` · Hospital: ${record.hospitalId}` : record.ownerId ? ` · Owner: ${record.ownerId}` : ""}.`,
        },
      );
      notify(isNew ? `${record.name} added to demo only — no login created.` : `${record.name} updated.`);
      return { ok: true };
    },
    [activeSuperusers.length, commit, data.users, data.hospitals, data.owners, notify],
  );

  const toggleUser = useCallback(
    (id) => {
      const user = data.users.find((u) => u.id === id);
      if (!user) return { ok: false };
      const suspend = user.status === "active";
      if (!suspend && Object.keys(validateUserAssignment(user, data.hospitals, data.owners ?? [])).length) {
        notify("Correct the user's role and hospital assignment before reactivating.", "red");
        return { ok: false };
      }
      if (suspend && user.role === "superuser" && activeSuperusers.length <= 1) {
        notify("At least one active superuser must remain.", "red");
        return { ok: false };
      }
      commit(
        (state) => ({
          ...state,
          users: state.users.map((u) =>
            u.id === id ? { ...u, status: suspend ? "suspended" : "active" } : u,
          ),
        }),
        {
          category: "user",
          action: suspend ? "Suspended user" : "Reactivated user",
          target: user.email,
          detail: suspend ? "Dashboard access suspended." : "Dashboard access restored.",
        },
      );
      notify(`${user.name} ${suspend ? "suspended" : "reactivated"}.`, suspend ? "grey" : "green");
      return { ok: true };
    },
    [activeSuperusers.length, commit, data.users, data.hospitals, data.owners, notify],
  );

  /* -------------------------- Preferences ------------------------- */

  const setPreference = useCallback((key, value) => {
    setData((state) => ({
      ...state,
      preferences: { ...state.preferences, [key]: value },
    }));
  }, []);

  const resetDemo = useCallback(() => {
    const fresh = buildSeed(Date.now());
    setData(fresh);
    setNow(Date.now());
    notify("Demo data restored to the initial records.", "blue");
  }, [notify]);

  /* ---------------------------- Derived --------------------------- */

  const value = useMemo(() => {
    const hospitalById = Object.fromEntries(data.hospitals.map((h) => [h.id, h]));
    const deviceById = Object.fromEntries(data.devices.map((d) => [d.id, d]));
    const openIncidents = data.incidents.filter(
      (i) => !["closed", "cancelled"].includes(i.status),
    );
    const pendingAlerts = openIncidents.reduce(
      (count, incident) =>
        count + incident.notifications.filter((n) => n.status === "notified").length,
      0,
    );

    return {
      ...data,
      now,
      hospitalById,
      deviceById,
      stats: {
        totalIncidents: data.incidents.length,
        openIncidents: openIncidents.length,
        pendingAlerts,
        onlineDevices: data.devices.filter((d) => d.status === "online").length,
        totalDevices: data.devices.length,
        activeHospitals: data.hospitals.filter((h) => h.active).length,
        totalHospitals: data.hospitals.length,
      },
      toasts,
      notify,
      dismissToast,
      notifyHospital,
      closeIncident,
      addIncidentNote,
      simulateIncident,
      saveHospital,
      toggleHospital,
      saveUser,
      toggleUser,
      setPreference,
      resetDemo,
    };
  }, [
    data,
    now,
    toasts,
    notify,
    dismissToast,
    notifyHospital,
    closeIncident,
    addIncidentNote,
    simulateIncident,
    saveHospital,
    toggleHospital,
    saveUser,
    toggleUser,
    setPreference,
    resetDemo,
  ]);

  return <SuperuserContext.Provider value={value}>{children}</SuperuserContext.Provider>;
}

