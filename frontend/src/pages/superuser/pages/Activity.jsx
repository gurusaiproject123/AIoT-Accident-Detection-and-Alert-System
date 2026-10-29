import { useState } from "react";
import Icon from "../components/Icon";
import { Badge, ConfirmDialog, EmptyState, FilterTabs, PageHeading, Panel, SearchInput } from "../components/ui";
import { useSuperuser } from "../useSuperuser";
import { AUDIT_CATEGORIES, downloadFile, formatDateTime, formatRelative, toCsv } from "../data";

const CATEGORY_TONES = {
  incident: "red",
  hospital: "purple",
  user: "blue",
  device: "green",
  system: "grey",
};

export default function Activity() {
  const { audit, now, preferences, setPreference, resetDemo } = useSuperuser();
  const [category, setCategory] = useState("all");
  const [query, setQuery] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);

  const text = query.trim().toLowerCase();
  const filtered = audit
    .filter((entry) => category === "all" || entry.category === category)
    .filter(
      (entry) =>
        !text || [entry.actor, entry.action, entry.target, entry.detail].join(" ").toLowerCase().includes(text),
    );

  const exportCsv = () => {
    const csv = toCsv(filtered, [
      { label: "ID", value: (e) => e.id },
      { label: "Time", value: (e) => e.at },
      { label: "Actor", value: (e) => e.actor },
      { label: "Role", value: (e) => e.role },
      { label: "Category", value: (e) => AUDIT_CATEGORIES[e.category] ?? e.category },
      { label: "Action", value: (e) => e.action },
      { label: "Target", value: (e) => e.target },
      { label: "Detail", value: (e) => e.detail },
    ]);
    downloadFile(`superuser-activity-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  };

  const tabs = [
    { value: "all", label: "All", count: audit.length },
    ...Object.entries(AUDIT_CATEGORIES).map(([value, label]) => ({
      value,
      label,
      count: audit.filter((e) => e.category === value).length,
    })),
  ];

  return (
    <div className="su-page">
      <PageHeading
        eyebrow="Superuser / Audit trail"
        title="Activity history"
        subtitle="Who performed each action, and when."
        actions={
          <button type="button" className="su-btn su-btn-outline" onClick={exportCsv} disabled={!filtered.length}>
            <Icon name="download" size={15} /> Export CSV
          </button>
        }
      />

      <Panel className="su-panel-flush">
        <div className="su-toolbar">
          <FilterTabs label="Activity category" options={tabs} value={category} onChange={setCategory} />
          <SearchInput value={query} onChange={setQuery} placeholder="Search actor, action, target…" />
        </div>

        {filtered.length === 0 ? (
          <EmptyState icon="clock" title="No activity matches these filters" />
        ) : (
          <div className="su-table-wrap">
            <table className="su-table">
              <thead>
                <tr>
                  <th scope="col">Time</th>
                  <th scope="col">Actor</th>
                  <th scope="col">Category</th>
                  <th scope="col">Action</th>
                  <th scope="col">Target</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((entry) => (
                  <tr key={entry.id}>
                    <td>
                      <span className="su-two-line">
                        <strong>{formatDateTime(entry.at)}</strong>
                        <small>{formatRelative(entry.at, now)}</small>
                      </span>
                    </td>
                    <td>
                      <span className="su-two-line">
                        <strong>{entry.actor}</strong>
                        <small>{entry.role.replace("_", " ")}</small>
                      </span>
                    </td>
                    <td>
                      <Badge tone={CATEGORY_TONES[entry.category] ?? "grey"}>
                        {AUDIT_CATEGORIES[entry.category] ?? entry.category}
                      </Badge>
                    </td>
                    <td className="su-strong">{entry.action}</td>
                    <td className="su-mono">{entry.target}</td>
                    <td className="su-cell-detail">{entry.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="su-table-foot">
          The backend will own the authoritative audit trail. This list is stored in this browser only.
        </p>
      </Panel>

      <Panel title="Workspace preferences" subtitle="Saved in this browser for the demo." icon="settings">
        <div className="su-pref-row">
          <label className="su-switch">
            <input
              type="checkbox"
              checked={preferences?.animations !== false}
              onChange={(e) => setPreference("animations", e.target.checked)}
            />
            <span className="su-switch-track" aria-hidden="true" />
            <span>
              <strong>Background and ring animations</strong>
              <small>Operating-system reduced-motion settings are always respected.</small>
            </span>
          </label>
          <button type="button" className="su-btn su-btn-ghost-danger" onClick={() => setConfirmReset(true)}>
            <Icon name="refresh" size={15} /> Reset demo
          </button>
        </div>
      </Panel>

      {confirmReset && (
        <ConfirmDialog
          title="Reset demo data?"
          message="This restores the initial incidents, devices, hospitals, users and activity history in this browser."
          confirmLabel="Reset demo"
          tone="danger"
          onConfirm={resetDemo}
          onClose={() => setConfirmReset(false)}
        />
      )}
    </div>
  );
}

