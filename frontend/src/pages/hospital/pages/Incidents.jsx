import { useState } from "react";
import { useHospital } from "../HospitalContext";
import { HOSPITAL } from "../data";
import { Icon, IncidentTable } from "../components/ui";

export default function Incidents() {
  const { incidents, addDemo } = useHospital();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All");
  const visible = incidents.filter(
    (i) =>
      (filter === "All" || i.status === filter) &&
      `${i.id} ${i.device} ${i.location}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <section className="hd-panel">
      <div className="hd-panel-title">
        <div>
          <h2>
            Assigned incidents{" "}
            <span className="hd-count">{incidents.length}</span>
          </h2>
          <p>Demo records scoped to {HOSPITAL.id}.</p>
        </div>
        <button className="hd-button hd-button-primary" onClick={addDemo}>
          <Icon name="bell" size={16} /> Add demo alert
        </button>
      </div>
      <div className="hd-toolbar">
        <label className="hd-search">
          <Icon name="search" size={17} />
          <input
            aria-label="Search assigned incidents"
            placeholder="Search incident, device or location…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="hd-filter-label">
          Status
          <select
            aria-label="Filter incidents by status"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            {[
              "All",
              "New",
              "Acknowledged",
              "Accepted",
              "Declined",
              "Escalated",
              "Escalation pending",
              "Closed",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <span className="hd-results">{visible.length} results</span>
      </div>
      <IncidentTable items={visible} />
    </section>
  );
}
