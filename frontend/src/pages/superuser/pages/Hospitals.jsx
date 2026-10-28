import { useState } from "react";
import Icon from "../components/Icon";
import HospitalForm from "../components/HospitalForm";
import { Badge, ConfirmDialog, EmptyState, FilterTabs, PageHeading, SearchInput } from "../components/ui";
import { useSuperuser } from "../useSuperuser";
import { formatCoords, formatDateTime } from "../data";

export default function Hospitals() {
  const { hospitals, users, incidents, saveHospital, toggleHospital } = useSuperuser();
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(null); // null | "new" | hospital
  const [confirming, setConfirming] = useState(null);

  const text = query.trim().toLowerCase();
  const filtered = hospitals
    .filter((h) => filter === "all" || (filter === "active" ? h.active : !h.active))
    .filter((h) => !text || [h.id, h.name, h.city, h.email].join(" ").toLowerCase().includes(text));

  const staffCount = (id) => users.filter((u) => u.hospitalId === id && u.status === "active").length;
  const openCount = (id) =>
    incidents.filter(
      (i) =>
        !["closed", "cancelled"].includes(i.status) &&
        i.notifications.some((n) => n.hospitalId === id && ["notified", "acknowledged", "accepted"].includes(n.status)),
    ).length;

  const activeCount = hospitals.filter((h) => h.active).length;

  return (
    <div className="su-page">
      <PageHeading
        eyebrow="Superuser / Hospital network"
        title="Hospitals"
        subtitle="Register, edit and activate the hospitals that receive incident notifications."
        actions={
          <button type="button" className="su-btn su-btn-primary" onClick={() => setEditing("new")}>
            <Icon name="plus" size={15} /> Register hospital
          </button>
        }
      />

      <div className="su-toolbar su-toolbar-bare">
        <FilterTabs
          label="Hospital status"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: "All", count: hospitals.length },
            { value: "active", label: "Active", count: activeCount },
            { value: "inactive", label: "Inactive", count: hospitals.length - activeCount },
          ]}
        />
        <SearchInput value={query} onChange={setQuery} placeholder="Search hospitals…" />
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon="building" title="No hospitals match these filters" />
      ) : (
        <div className="su-card-grid">
          {filtered.map((hospital) => (
            <article key={hospital.id} className={`su-hospital-card ${hospital.active ? "" : "is-inactive"}`}>
              <header>
                <span className="su-hospital-icon">
                  <Icon name="building" size={20} />
                </span>
                <div>
                  <h3>{hospital.name}</h3>
                  <small>
                    {hospital.id} · {hospital.city}
                  </small>
                </div>
                <Badge tone={hospital.active ? "green" : "grey"}>{hospital.active ? "Active" : "Inactive"}</Badge>
              </header>

              <ul className="su-hospital-meta">
                <li>
                  <Icon name="mapPin" size={14} />
                  <span>{hospital.address || "No address recorded"}</span>
                </li>
                <li>
                  <Icon name="bell" size={14} />
                  <span>{hospital.phone}</span>
                </li>
                <li>
                  <Icon name="send" size={14} />
                  <span>{hospital.email}</span>
                </li>
                <li>
                  <Icon name="map" size={14} />
                  <span className="su-mono">{formatCoords(hospital.lat, hospital.lng)}</span>
                </li>
              </ul>

              <div className="su-hospital-numbers">
                <div>
                  <strong>{staffCount(hospital.id)}</strong>
                  <small>Active staff</small>
                </div>
                <div>
                  <strong>{openCount(hospital.id)}</strong>
                  <small>Open incidents</small>
                </div>
                <div>
                  <strong>{formatDateTime(hospital.registeredAt).split(",")[0]}</strong>
                  <small>Registered</small>
                </div>
              </div>

              <footer>
                <button type="button" className="su-btn su-btn-soft su-btn-sm" onClick={() => setEditing(hospital)}>
                  <Icon name="edit" size={14} /> Edit
                </button>
                <button
                  type="button"
                  className={`su-btn su-btn-sm ${hospital.active ? "su-btn-ghost-danger" : "su-btn-outline"}`}
                  onClick={() => setConfirming(hospital)}
                >
                  <Icon name="power" size={14} /> {hospital.active ? "Deactivate" : "Activate"}
                </button>
              </footer>
            </article>
          ))}
        </div>
      )}

      {editing && (
        <HospitalForm
          hospital={editing === "new" ? null : editing}
          hospitals={hospitals}
          onSave={saveHospital}
          onClose={() => setEditing(null)}
        />
      )}

      {confirming && (
        <ConfirmDialog
          title={`${confirming.active ? "Deactivate" : "Activate"} ${confirming.name}?`}
          message={
            confirming.active
              ? "This hospital will stop receiving new incident notifications. Existing incident records are kept."
              : "This hospital will be included in automatic routing for new incidents."
          }
          confirmLabel={confirming.active ? "Deactivate" : "Activate"}
          tone={confirming.active ? "danger" : "primary"}
          onConfirm={() => toggleHospital(confirming.id)}
          onClose={() => setConfirming(null)}
        />
      )}
    </div>
  );
}

