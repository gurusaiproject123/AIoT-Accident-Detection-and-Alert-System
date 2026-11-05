import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "../auth/useAuth";
import { hospitalRequest, mapAlert } from "./hospitalApi";

const HospitalContext = createContext(null);
export const useHospital = () => useContext(HospitalContext);

export function HospitalProvider({ children }) {
  const { session, profile, signOut } = useAuth();
  const token = session?.access_token;
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [feedError, setFeedError] = useState("");
  const [lastSync, setLastSync] = useState(null);
  const [motion, setMotion] = useState(true);
  const [notice, setNotice] = useState("");
  const [sound, setSound] = useState(false);
  const [clock, setClock] = useState(Date.now);
  const audio = useRef(null);
  const activeTones = useRef(new Set());
  const currentRequest = useRef(null);
  const navigate = useNavigate();
  const toast = setNotice;
  const request = useCallback((path, options) => hospitalRequest(token, path, options), [token]);

  const refresh = useCallback(async () => {
    currentRequest.current?.abort();
    const controller = new AbortController();
    currentRequest.current = controller;
    try {
      const result = await request("/api/hospital/alerts", { signal: controller.signal });
      if (!Array.isArray(result)) throw new Error("Unexpected hospital alert list.");
      if (controller.signal.aborted) return;
      setIncidents(result.map(mapAlert).sort((a, b) => b.created - a.created));
      setLastSync(Date.now());
      setFeedError("");
    } catch (error) {
      if (!controller.signal.aborted) {
        if (error.status === 401 || error.status === 403) {
          setIncidents([]);
          setLastSync(null);
        }
        setFeedError(error.message || "Could not load hospital alerts.");
      }
    } finally {
      if (currentRequest.current === controller) {
        currentRequest.current = null;
        setLoading(false);
      }
    }
  }, [request]);

  useEffect(() => {
    refresh();
    const interval = setInterval(() => { if (!currentRequest.current) refresh(); }, 10000);
    return () => {
      clearInterval(interval);
      currentRequest.current?.abort();
      currentRequest.current = null;
    };
  }, [refresh]);
  useEffect(() => {
    const interval = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timeout = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(timeout);
  }, [notice]);
  useEffect(() => () => {
    if (audio.current && audio.current.state !== "closed") {
      audio.current.onstatechange = null;
      audio.current.close().catch(() => {});
    }
  }, []);

  const openIncident = (id) => navigate(`/hospital/incidents/${encodeURIComponent(id)}`);
  const newCount = incidents.filter((item) => item.status === "New").length;
  const alarmActive = sound && newCount > 0;
  const active = incidents.filter((item) => ["New", "Acknowledged", "Accepted"].includes(item.status));
  const hospitalName = incidents.find((item) => item.hospital?.name)?.hospital.name || "Assigned hospital";
  const hospitalCode = incidents.find((item) => item.hospital?.code)?.hospital.code;
  const history = incidents.flatMap((item) => [
    [item.created, "Alert received"],
    [item.acknowledgedAt, "Alert acknowledged"],
    [item.respondedAt, item.declineReason ? "Response declined" : "Response recorded"],
  ].filter(([at]) => Number.isFinite(at)).map(([at, text]) => ({ id: item.id, code: item.code, at, text })))
    .sort((a, b) => b.at - a.at);
  const age = (at) => Number.isFinite(at) ? `${Math.max(0, Math.floor((clock - at) / 60000))} min ago` : "Time unavailable";

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

  // Unlock browser audio on the first dashboard interaction.
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

  function exportCsv() {
    const escape = (value) => {
      const raw = String(value ?? "");
      const safe = /^[\s]*[=+@-]|^[\t\r\n]/.test(raw) && typeof value !== "number" ? "'" + raw : raw;
      return '"' + safe.replaceAll('"', '""') + '"';
    };
    const rows = [["Incident", "Alert status", "Received UTC", "Device", "Latitude", "Longitude"],
      ...incidents.map((item) => [item.code, item.status,
        Number.isFinite(item.created) ? new Date(item.created).toISOString() : "",
        item.device, item.lat, item.lng])];
    const url = URL.createObjectURL(new Blob([rows.map((row) => row.map(escape).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "hospital-incidents.csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <HospitalContext.Provider value={{ incidents, loading, feedError, lastSync, refresh, request,
    hospitalName, hospitalCode, profile, signOut, motion, setMotion, notice, setNotice, sound, clock,
    newCount, alarmActive, active, history, age, toast, openIncident, enableSound, exportCsv }}>
    {children}
  </HospitalContext.Provider>;
}
