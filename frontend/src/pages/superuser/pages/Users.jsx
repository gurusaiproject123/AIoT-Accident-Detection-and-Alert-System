import { useState } from "react";
import { useSearchParams } from "react-router";
import { needsAssignmentCorrection } from "../userRules";
import Icon from "../components/Icon";
import UserForm from "../components/UserForm";
import { ConfirmDialog, EmptyState, FilterTabs, PageHeading, Panel, SearchInput, StatusBadge } from "../components/ui";
import { useSuperuser } from "../useSuperuser";
import { ROLES, USER_STATUS, formatRelative, initials } from "../data";

export default function Users() {
  const { users, hospitals, owners = [], hospitalById, now, saveUser, toggleUser } = useSuperuser();
  const [role, setRole] = useState("all");
  const [searchParams, setSearchParams] = useSearchParams();
  const hospitalFilter = searchParams.get("hospital") ?? "all";
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(null); // null | "new" | user
  const [confirming, setConfirming] = useState(null);

  const text = query.trim().toLowerCase();
  const filtered = users
    .filter((u) => role === "all" || u.role === role)
    .filter((u) => hospitalFilter === "all" || u.hospitalId === hospitalFilter)
    .filter(
      (u) =>
        !text ||
        [u.name, u.email, hospitalById[u.hospitalId]?.name, ROLES[u.role]?.label].join(" ").toLowerCase().includes(text),
    );

  const corrections = users.filter((u) => needsAssignmentCorrection(u, hospitals, owners));
  const count = (key) => users.filter((u) => u.role === key).length;

  return (
    <div className="su-page">
      <PageHeading
        eyebrow="Superuser / Access management"
        title="Users and roles"
        subtitle="Staff belong to one hospital. Car owners log in to their separate vehicle interface. Superusers oversee the platform without a hospital assignment."
        actions={
          <button type="button" className="su-btn su-btn-primary" onClick={() => setEditing("new")}>
            <Icon name="plus" size={15} /> Add demo user
          </button>
        }
      />

      {corrections.length > 0 && (
        <Panel title="Existing records need correction" subtitle="No hospital has been assigned automatically.">
          <p className="su-table-foot">{corrections.length} legacy record(s) have an unsupported role or invalid hospital assignment. Edit each record to select the confirmed role and hospital.</p>
        </Panel>
      )}
      <Panel className="su-panel-flush">
        <div className="su-toolbar">
          <FilterTabs
            label="Role"
            value={role}
            onChange={setRole}
            options={[
              { value: "all", label: "All", count: users.length },
              { value: "superuser", label: "Superusers", count: count("superuser") },
              { value: "hospital_staff", label: "Hospital staff", count: count("hospital_staff") },
              { value: "car_owner", label: "Car owners", count: count("car_owner") },
            ]}
          />
          <div className="su-toolbar-right">
            <select className="su-select" aria-label="Filter users by hospital" value={hospitalFilter}
              onChange={(e) => setSearchParams(e.target.value === "all" ? {} : { hospital: e.target.value })}>
              <option value="all">All users / hospitals</option>
              {hospitals.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
            <SearchInput value={query} onChange={setQuery} placeholder="Search name, email, hospital…" />
          </div>
        </div>

        {filtered.length === 0 ? (
          <EmptyState icon="users" title="No users match these filters" />
        ) : (
          <div className="su-table-wrap">
            <table className="su-table">
              <thead>
                <tr>
                  <th scope="col">User</th>
                  <th scope="col">Role</th>
                  <th scope="col">Hospital assignment</th>
                  <th scope="col">Owner / cars</th>
                  <th scope="col">Status</th>
                  <th scope="col">Last sign-in</th>
                  <th scope="col" className="su-align-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((user) => (
                  <tr key={user.id} className={user.status === "suspended" ? "is-muted" : ""}>
                    <td>
                      <span className="su-user-cell">
                        <span className="su-avatar su-avatar-sm">{initials(user.name)}</span>
                        <span className="su-two-line">
                          <strong>{user.name}</strong>
                          <small>{user.email}</small>
                        </span>
                      </span>
                    </td>
                    <td>
                      <StatusBadge map={ROLES} value={user.role} />
                      {needsAssignmentCorrection(user, hospitals, owners) && <small className="su-muted">Needs correction</small>}
                    </td>
                    <td>
                      {user.hospitalId ? (
                        hospitalById[user.hospitalId]?.name ?? user.hospitalId
                      ) : (
                        <span className="su-muted">{user.role === "hospital_staff" ? "Needs assignment" : "No hospital assignment"}</span>
                      )}
                    </td>
                    <td>
                      {user.role === "car_owner" ? (()=>{
                        const owner=owners.find(o=>o.id===user.ownerId);
                        return <span className="su-two-line"><strong>{owner?.name ?? "Needs owner link"}</strong><small>{owner?.registrations?.join(", ")}</small></span>;
                      })() : <span className="su-muted">—</span>}
                    </td>
                    <td>
                      <StatusBadge map={USER_STATUS} value={user.status} />
                    </td>
                    <td>{formatRelative(user.lastSignIn, now)}</td>
                    <td className="su-align-right">
                      <span className="su-row-actions">
                        <button
                          type="button"
                          className="su-btn su-btn-soft su-btn-sm"
                          onClick={() => setEditing(user)}
                        >
                          <Icon name="edit" size={14} /> Edit
                        </button>
                        <button
                          type="button"
                          className={`su-btn su-btn-sm ${user.status === "active" ? "su-btn-ghost-danger" : "su-btn-outline"}`}
                          onClick={() => setConfirming(user)}
                        >
                          <Icon name="power" size={14} /> {user.status === "active" ? "Suspend" : "Reactivate"}
                        </button>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="su-table-foot">
          Email/password sign-in is managed by Supabase Auth. These are local demo profiles, not live login accounts. FastAPI must enforce permissions.
        </p>
      </Panel>

      {editing && (
        <UserForm
          user={editing === "new" ? null : editing}
          hospitals={hospitals}
          owners={owners}
          initialHospitalId={hospitalFilter === "all" ? "" : hospitalFilter}
          onSave={saveUser}
          onClose={() => setEditing(null)}
        />
      )}

      {confirming && (
        <ConfirmDialog
          title={`${confirming.status === "active" ? "Suspend" : "Reactivate"} ${confirming.name}?`}
          message={
            confirming.status === "active"
              ? "The user will no longer be able to open any dashboard. Their history is kept."
              : "The user will regain access according to their assigned role."
          }
          confirmLabel={confirming.status === "active" ? "Suspend" : "Reactivate"}
          tone={confirming.status === "active" ? "danger" : "primary"}
          onConfirm={() => toggleUser(confirming.id)}
          onClose={() => setConfirming(null)}
        />
      )}
    </div>
  );
}

