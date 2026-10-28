import { useState } from "react";
import Icon from "../components/Icon";
import UserForm from "../components/UserForm";
import { ConfirmDialog, EmptyState, FilterTabs, PageHeading, Panel, SearchInput, StatusBadge } from "../components/ui";
import { useSuperuser } from "../useSuperuser";
import { ROLES, USER_STATUS, formatRelative, initials } from "../data";

export default function Users() {
  const { users, hospitals, hospitalById, now, saveUser, toggleUser } = useSuperuser();
  const [role, setRole] = useState("all");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(null); // null | "new" | user
  const [confirming, setConfirming] = useState(null);

  const text = query.trim().toLowerCase();
  const filtered = users
    .filter((u) => role === "all" || u.role === role)
    .filter(
      (u) =>
        !text ||
        [u.name, u.email, hospitalById[u.hospitalId]?.name, ROLES[u.role]?.label].join(" ").toLowerCase().includes(text),
    );

  const count = (key) => users.filter((u) => u.role === key).length;

  return (
    <div className="su-page">
      <PageHeading
        eyebrow="Superuser / Access management"
        title="Users and roles"
        subtitle="Authorised roles and hospital assignments for everyone who can sign in."
        actions={
          <button type="button" className="su-btn su-btn-primary" onClick={() => setEditing("new")}>
            <Icon name="plus" size={15} /> Add user
          </button>
        }
      />

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
              { value: "unassigned", label: "No role", count: count("unassigned") },
            ]}
          />
          <SearchInput value={query} onChange={setQuery} placeholder="Search name, email, hospital…" />
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
                    </td>
                    <td>
                      {user.hospitalId ? (
                        hospitalById[user.hospitalId]?.name ?? user.hospitalId
                      ) : (
                        <span className="su-muted">{user.role === "superuser" ? "All hospitals" : "—"}</span>
                      )}
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
          FastAPI must verify roles and hospital assignments on every request — this list is a demo view.
        </p>
      </Panel>

      {editing && (
        <UserForm
          user={editing === "new" ? null : editing}
          hospitals={hospitals}
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

