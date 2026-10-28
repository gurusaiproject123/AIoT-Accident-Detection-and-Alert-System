import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useNavigate } from "react-router";
import {
  loadState,
  verifyDemoStaff,
  buildIncidentCsv,
  seedIncidents,
  HOSPITAL,
  RESPONSE_WINDOW_MS,
  escalateIncident,
  expireIncident,
  isAwaitingAcknowledgment,
} from "./data";

const HospitalContext = createContext(null);

export function useHospital() {
  const context = useContext(HospitalContext);
  if (!context)
    throw new Error("Hospital components require HospitalProvider.");
  return context;
}

// Local prototype store. Replace these actions with authenticated FastAPI calls.
export function HospitalProvider({ children }) {
  const [initial] = useState(loadState);
  const [incidents, setIncidents] = useState(initial.incidents);
  const [motion, setMotion] = useState(initial.motion !== false);
  const [notice, setNotice] = useState("");
  const [pendingResponse, setPendingResponse] = useState(null);
  const [operatorName, setOperatorName] = useState("");
  const pendingResolver = useRef(null);
  useEffect(
    () => () => {
      pendingResolver.current?.(false);
    },
    [],
  );
  // Always armed. sound reports browser audio readiness, not an on/off preference.
  const [sound, setSound] = useState(false);
  const [clock, setClock] = useState(() => Date.now());
  const audio = useRef(null);
  const activeTones = useRef(new Set());
  const navigate = useNavigate();

  useEffect(() => {
    try {
      localStorage.setItem(
        "aiot-hospital-demo-v1",
        JSON.stringify({ incidents, motion }),
      );
    } catch {
      /* The UI can run without browser persistence. */
    }
  }, [incidents, motion]);
  useEffect(() => {
    const id = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    setIncidents((items) => {
      let changed = false;
      const next = items.map((incident) => {
        const updated = expireIncident(incident, clock);
        if (updated !== incident) changed = true;
        return updated;
      });
      return changed ? next : items;
    });
  }, [clock]);
  useEffect(() => {
    if (!notice) return;
    const id = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(id);
  }, [notice]);
  useEffect(
    () => () => {
      audio.current?.close();
    },
    [],
  );

  const toast = (message) => setNotice(message);
  const openIncident = (id) =>
    navigate(`/hospital/incidents/${encodeURIComponent(id)}`);
  const newCount = incidents.filter((i) => i.status === "New").length;
  const alarmActive = sound && newCount > 0;
  const active = incidents.filter(
    (i) =>
      !["Closed", "Declined", "Escalated", "Escalation pending"].includes(
        i.status,
      ),
  );
  const history = incidents
    .flatMap((i) => i.timeline.map((e) => ({ ...e, id: i.id })))
    .sort((a, b) => b.at - a.at);
  const age = (timestamp) => {
    const minutes = Math.max(0, Math.floor((clock - timestamp) / 60000));
    return minutes < 1
      ? "Just now"
      : minutes < 60
        ? `${minutes} min ago`
        : `${Math.floor(minutes / 60)}h ${minutes % 60}m ago`;
  };

  const stopTones = useCallback(() => {
    for (const oscillator of activeTones.current) {
      try {
        oscillator.stop();
      } catch {
        /* Already ended. */
      }
    }
    activeTones.current.clear();
  }, []);

  const prepareAudio = useCallback(async () => {
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) throw new Error("Audio unavailable");
    if (!audio.current || audio.current.state === "closed")
      audio.current = new Audio();
    audio.current.onstatechange = () =>
      setSound(audio.current?.state === "running");
    await audio.current.resume();
  }, []);

  // One pulse; the effect below repeats it until all New alerts are handled.
  const playTone = useCallback(() => {
    const context = audio.current;
    if (!context || context.state !== "running") return;
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.frequency.setValueAtTime(660, context.currentTime);
    oscillator.frequency.setValueAtTime(880, context.currentTime + 0.25);
    gain.gain.setValueAtTime(0.001, context.currentTime);
    gain.gain.linearRampToValueAtTime(0.055, context.currentTime + 0.03);
    gain.gain.setValueAtTime(0.055, context.currentTime + 0.45);
    gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.6);
    activeTones.current.add(oscillator);
    oscillator.onended = () => {
      activeTones.current.delete(oscillator);
      oscillator.disconnect();
      gain.disconnect();
    };
    oscillator.start();
    oscillator.stop(context.currentTime + 0.65);
  }, []);

  // One loop for the entire hospital workspace, including across page changes.
  useEffect(() => {
    if (!sound || newCount === 0) {
      stopTones();
      return;
    }
    playTone();
    const interval = setInterval(playTone, 1200);
    return () => {
      clearInterval(interval);
      stopTones();
    };
  }, [sound, newCount, playTone, stopTones]);

  // Automatically unlock audio on the first dashboard interaction. The Add
  // demo alert click also counts; no separate Enable switch is required.
  useEffect(() => {
    let disposed = false;
    const activate = async (event) => {
      if (event.type === "keydown" && event.repeat) return;
      if (audio.current?.state === "running") return;
      try {
        await prepareAudio();
        if (!disposed) setSound(audio.current?.state === "running");
      } catch {
        if (!disposed)
          setNotice(
            "Browser audio is blocked. Click Activate audio or check site sound permissions.",
          );
      }
    };
    window.addEventListener("pointerdown", activate, true);
    window.addEventListener("keydown", activate, true);
    return () => {
      disposed = true;
      window.removeEventListener("pointerdown", activate, true);
      window.removeEventListener("keydown", activate, true);
    };
  }, [prepareAudio]);

  async function enableSound() {
    try {
      await prepareAudio();
      setSound(true);
      if (newCount === 0) playTone();
      toast(
        newCount > 0
          ? "Alarm active. Acknowledge all new incidents to stop it."
          : "Test tone played. Alarm stays armed for new incidents.",
      );
    } catch {
      setSound(false);
      toast("Browser audio is blocked. Check site sound permissions.");
    }
  }

  function updateIncident(id, status, text) {
    if (pendingResolver.current) return Promise.resolve(false);
    return new Promise((resolve) => {
      pendingResolver.current = resolve;
      setPendingResponse({ id, status, text });
    });
  }

  function cancelResponse() {
    pendingResolver.current?.(false);
    pendingResolver.current = null;
    setPendingResponse(null);
  }

  async function confirmResponse(name, password) {
    if (!pendingResponse)
      return { ok: false, error: "No response is awaiting confirmation." };
    let actor;
    try {
      actor = verifyDemoStaff(name, password);
    } catch (error) {
      return { ok: false, error: error.message };
    }
    const succeeded = applyIncidentUpdate(
      pendingResponse.id,
      pendingResponse.status,
      pendingResponse.text,
      actor,
    );
    if (succeeded) setOperatorName(actor.actorName);
    pendingResolver.current?.(succeeded);
    pendingResolver.current = null;
    setPendingResponse(null);
    return { ok: true };
  }

  function applyIncidentUpdate(id, status, text, actor) {
    const allowed = {
      New: ["Acknowledged"],
      Acknowledged: ["Accepted", "Declined"],
      Accepted: ["Closed"],
    };
    const current = incidents.find((i) => i.id === id);
    if (!current || (status && !allowed[current.status]?.includes(status))) {
      toast("This response is not available for the current incident status.");
      return false;
    }
    const at = Date.now();
    if (
      isAwaitingAcknowledgment(current) &&
      Number.isFinite(current.responseDeadline) &&
      at >= current.responseDeadline
    ) {
      setIncidents((items) =>
        items.map((i) => (i.id === id ? expireIncident(i, at) : i)),
      );
      toast(
        "The response deadline has passed. This incident has entered escalation.",
      );
      return false;
    }
    setIncidents((items) =>
      items.map((i) => {
        if (i.id !== id || (status && !allowed[i.status]?.includes(status)))
          return i;
        const updated = {
          ...i,
          status: status || i.status,
          responseDeadline:
            status === "Acknowledged" ? null : i.responseDeadline,
          acknowledgedAt: status === "Acknowledged" ? at : i.acknowledgedAt,
          acknowledgedBy:
            status === "Acknowledged" ? actor.actorName : i.acknowledgedBy,
          acceptedAt: status === "Accepted" ? at : i.acceptedAt,
          acceptedBy: status === "Accepted" ? actor.actorName : i.acceptedBy,
          declinedAt: status === "Declined" ? at : i.declinedAt,
          declinedBy: status === "Declined" ? actor.actorName : i.declinedBy,
          closedAt: status === "Closed" ? at : i.closedAt,
          closedBy: status === "Closed" ? actor.actorName : i.closedBy,
          notes:
            !status && text.startsWith("Note:")
              ? [
                  ...(i.notes || []),
                  { text: text.slice(5).trim(), at, user: actor.actorName },
                ]
              : i.notes,

          timeline: [
            ...i.timeline,
            {
              text,
              at,
              user: actor.actorName,
              actorId: actor.actorId,
              hospitalId: HOSPITAL.id,
              action: status || "Note or review report",
              confirmationMethod: actor.confirmationMethod,
              identityVerified: actor.identityVerified,
            },
          ],
        };
        return status === "Declined"
          ? escalateIncident(updated, "decline", text, at)
          : updated;
      }),
    );
    toast(text);
    return true;
  }

  function addDemo() {
    const at = Date.now();
    setClock(at);
    const id = `INC-D${at.toString().slice(-7)}`;
    setIncidents((items) => [
      {
        ...seedIncidents()[0],
        id,
        created: at,
        occurredAt: at,
        occurredAtSource: "simulated",
        assignedAt: at,
        responseDeadline: at + RESPONSE_WINDOW_MS,
        acknowledgedAt: null,
        escalation: null,
        attemptedHospitalIds: [HOSPITAL.id],
        status: "New",
        notes: [],
        timeline: [
          {
            text: "Demo alert received by this hospital",
            at,
            user: "Demo generator",
          },
        ],
      },
      ...items,
    ]);
    toast("A simulated alert was added. No external notification was sent.");
  }

  function resetDemo() {
    if (window.confirm("Reset local demo incidents and history?")) {
      setIncidents(seedIncidents());
      toast("Demo records restored.");
    }
  }

  function exportCsv() {
    const csv = buildIncidentCsv(incidents);
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8;" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "hospital-demo-incidents.csv";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Demo incident report downloaded.");
  }

  return (
    <HospitalContext.Provider
      value={{
        incidents,
        pendingResponse,
        operatorName,
        confirmResponse,
        cancelResponse,
        motion,
        setMotion,
        notice,
        setNotice,
        sound,
        clock,
        newCount,
        alarmActive,
        active,
        history,
        age,
        toast,
        openIncident,
        enableSound,
        updateIncident,
        addDemo,
        resetDemo,
        exportCsv,
      }}
    >
      {children}
    </HospitalContext.Provider>
  );
}
