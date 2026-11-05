export const NAV = [
  ["overview", "Overview", "grid"],
  ["incidents", "Assigned incidents", "bell"],
  ["operations", "Operations", "clock"],
  ["health", "Locations and health", "pulse"],
  ["reports", "Reports", "chart"],
];
export const time = (t) => Number.isFinite(t) ? new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Not recorded";
export const date = (t) => Number.isFinite(t) ? new Date(t).toLocaleDateString([], { day: "numeric", month: "short" }) : "Not recorded";
export const isAwaitingAcknowledgment = (incident) => incident.status === "New";
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
