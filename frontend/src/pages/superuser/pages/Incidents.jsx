import { useState } from "react";
import Icon from "../components/Icon";
import { EmptyState, FilterTabs, IncidentTable, PageHeading, Panel, SearchInput } from "../components/ui";
import { useSuperuser } from "../useSuperuser";
import { INCIDENT_STATUS } from "../data";

const GROUPS = {
  all: () => true,
  open: (i) => ["cancellation_window", "notified", "escalated", "acknowledged", "accepted"].includes(i.status),
  pending: (i) => ["cancellation_window", "notified", "escalated"].includes(i.status),
  resolved: (i) => ["closed", "cancelled"].includes(i.status),
};

export default function Incidents() {
  const { incidents, hospitals, hospitalById, deviceById, simulateIncident } = useSuperuser();
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("all");
  const [hospitalId, setHospitalId] = useState("all");

  const text = query.trim().toLowerCase();
  const filtered = incidents
    .filter(GROUPS[group])
    .filter((i) => hospitalId === "all" || i.notifications.some((n) => n.hospitalId === hospitalId))
    .filter((i) => {
      if (!text) return true;
      const haystack = [
        i.id,
        i.deviceId,
        deviceById[i.deviceId]?.vehicle,
        i.location?.label,
        INCIDENT_STATUS[i.status]?.label,
        ...i.notifications.map((n) => hospitalById[n.hospitalId]?.name),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(text);
    })
    .sort((a, b) => new Date(b.detectedAt) - new Date(a.detectedAt));

  const tabs = Object.keys(GROUPS).map((key) => ({
    value: key,
    label: { all: "All", open: "Open", pending: "Awaiting response", resolved: "Resolved" }[key],
    count: incidents.filter(GROUPS[key]).length,
  }));

  return (
    <div className="su-page">
      <PageHeading
        eyebrow="Superuser / Incident monitoring"
        title="Incidents"
        subtitle="Every suspected accident recorded by the system, from detection to outcome."
        actions={
          <button type="button" className="su-btn su-btn-primary" onClick={simulateIncident}>
            <Icon name="play" size={15} /> Simulate detection
          </button>
        }
      />

      <Panel className="su-panel-flush">
        <div className="su-toolbar">
          <FilterTabs options={tabs} value={group} onChange={setGroup} label="Incident status" />
          <div className="su-toolbar-right">
            <select
              className="su-select"
              value={hospitalId}
              onChange={(e) => setHospitalId(e.target.value)}
              aria-label="Filter by notified hospital"
            >
              <option value="all">All hospitals</option>
              {hospitals.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
            </select>
            <SearchInput value={query} onChange={setQuery} placeholder="Search ID, device, location…" />
          </div>
        </div>

        {filtered.length ? (
          <IncidentTable incidents={filtered} statusMap={INCIDENT_STATUS} />
        ) : (
          <EmptyState title="No incidents match these filters">
            Try a different search term or status filter.
          </EmptyState>
        )}
        <p className="su-table-foot">
          Showing {filtered.length} of {incidents.length} incidents
        </p>
      </Panel>
    </div>
  );
}

