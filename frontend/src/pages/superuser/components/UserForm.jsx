import { useState } from "react";
import { Field, Modal } from "./ui";
import { ROLES } from "../data";
import { validateUserAssignment } from "../userRules";

export default function UserForm({ user, hospitals, owners = [], initialHospitalId = "", onSave, onClose }) {
  const isEdit = Boolean(user);
  const [values, setValues] = useState(() => ({
    name: user?.name ?? "", email: user?.email ?? "",
    role: ["superuser", "car_owner"].includes(user?.role) ? user.role : "hospital_staff",
    ownerId: user?.ownerId ?? "",
    hospitalId: ["superuser", "car_owner"].includes(user?.role) ? "" : user?.hospitalId ?? initialHospitalId,
  }));
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (key) => (event) => {
    const value = event.target.value;
    setValues((current) => ({...current, [key]: value, ...(key === "role" ? {hospitalId: value === "hospital_staff" ? current.hospitalId : "", ownerId: value === "car_owner" ? current.ownerId : ""} : {})}));
    setErrors({}); setFormError("");
  };
  const submit = async (event) => {
    event.preventDefault();
    if (saving) return;
    const record = {
      ...(user ? {id:user.id} : {}), name:values.name.trim(), email:values.email.trim().toLowerCase(),
      role:values.role, hospitalId:values.role === "hospital_staff" ? values.hospitalId : null,
      ownerId:values.role === "car_owner" ? values.ownerId : null,
    };
    const found = validateUserAssignment(record, hospitals, owners);
    setErrors(found); if(Object.keys(found).length) return;
    setSaving(true);
    try {
      const result = await onSave(record);
      if(result?.ok) onClose(); else setFormError(result?.error ?? "Could not save this user.");
    } catch {setFormError("Could not save this user. Please try again.");}
    finally {setSaving(false);}
  };
  return <Modal title={isEdit ? `Edit ${user.name}` : "Add demo user"}
    subtitle="Staff belong to one hospital. Administrators and car owners have no hospital assignment."
    onClose={saving ? () => {} : onClose}
    footer={<><button type="button" className="su-btn su-btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
      <button type="submit" form="user-form" className="su-btn su-btn-primary" disabled={saving}>{saving ? "Saving…" : isEdit ? "Save assignment" : "Add demo user"}</button></>}>
    <form id="user-form" className="su-form-grid" onSubmit={submit} noValidate>
      {formError && <p role="alert" className="su-form-error su-form-full">{formError}</p>}
      <Field label="Full name" error={errors.name}><input value={values.name} onChange={set("name")} placeholder="e.g. Receptionist Thandi" autoComplete="name" disabled={saving} /></Field>
      <Field label="Email address" error={errors.email} hint={isEdit ? "Login email changes must be managed through Supabase Auth." : "Sign-in uses email and password once Auth is connected."}>
        <input value={values.email} onChange={set("email")} type="email" autoComplete="email" placeholder="name@example.com" disabled={saving || isEdit} />
      </Field>
      <Field label="Authorised role" error={errors.role} hint="Assigned by the superuser, never chosen during staff signup.">
        <select value={values.role} onChange={set("role")} disabled={saving}>{Object.entries(ROLES).map(([key,role])=><option key={key} value={key}>{role.label}</option>)}</select>
      </Field>
      <Field label="Hospital assignment" error={errors.hospitalId} hint={values.role === "hospital_staff" ? "Many staff may share this hospital; each belongs to exactly one." : "No hospital assignment for this account type."}>
        <select value={values.hospitalId} onChange={set("hospitalId")} disabled={saving || values.role !== "hospital_staff"}>
          <option value="">{values.role === "hospital_staff" ? "Select one hospital" : "No hospital assignment"}</option>
          {hospitals.map(h=><option key={h.id} value={h.id}>{h.name}{h.active ? "" : " (inactive)"}</option>)}
        </select>
      </Field>
      {values.role === "car_owner" && <Field label="Registered car owner" error={errors.ownerId} hint="One owner account can access all cars linked to this registered owner.">
        <select value={values.ownerId} onChange={set("ownerId")} disabled={saving}>
          <option value="">Select the registered owner</option>
          {owners.map(owner=><option key={owner.id} value={owner.id}>{owner.name} · {owner.registrations?.join(", ") || "No registered cars"}</option>)}
        </select>
      </Field>}
      <p className="su-form-full su-muted">This preview saves demo profiles only. It does not create a Supabase login, set a password or send an invitation. Real email/password accounts require the protected FastAPI account-creation endpoint.</p>
    </form>
  </Modal>;
}
