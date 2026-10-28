import { useState } from "react";
import { Field, Modal } from "./ui";
import { ROLES } from "../data";

/** Add user / edit role assignment dialog. */
export default function UserForm({ user, hospitals, onSave, onClose }) {
  const isEdit = Boolean(user);
  const [values, setValues] = useState(() => ({
    name: user?.name ?? "",
    email: user?.email ?? "",
    role: user?.role ?? "hospital_staff",
    hospitalId: user?.hospitalId ?? "",
  }));
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");

  const choices = hospitals.filter((h) => h.active || h.id === user?.hospitalId);

  const set = (key) => (event) => {
    setValues((current) => ({ ...current, [key]: event.target.value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
    setFormError("");
  };

  const submit = (event) => {
    event.preventDefault();
    const found = {};
    if (!values.name.trim()) found.name = "Name is required.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) found.email = "Enter a valid email address.";
    if (values.role === "hospital_staff" && !values.hospitalId) found.hospitalId = "Hospital staff must be assigned to a hospital.";
    setErrors(found);
    if (Object.keys(found).length) return;

    const result = onSave({
      ...(user ?? {}),
      name: values.name.trim(),
      email: values.email.trim(),
      role: values.role,
      hospitalId: values.role === "hospital_staff" ? values.hospitalId : null,
    });
    if (result?.ok) onClose();
    else setFormError(result?.error ?? "Could not save this user.");
  };

  return (
    <Modal
      title={isEdit ? `Edit ${user.name}` : "Add user"}
      subtitle={
        isEdit
          ? "Change the authorised role and hospital assignment."
          : "The account is created in Supabase Auth once the backend is connected."
      }
      onClose={onClose}
      footer={
        <>
          <button type="button" className="su-btn su-btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="user-form" className="su-btn su-btn-primary">
            {isEdit ? "Save assignment" : "Add user"}
          </button>
        </>
      }
    >
      <form id="user-form" className="su-form-grid" onSubmit={submit} noValidate>
        {formError && <p className="su-form-error su-form-full">{formError}</p>}
        <Field label="Full name" error={errors.name}>
          <input value={values.name} onChange={set("name")} placeholder="e.g. Response operator" />
        </Field>
        <Field label="Email address" error={errors.email}>
          <input value={values.email} onChange={set("email")} type="email" placeholder="name@example.com" />
        </Field>
        <Field label="Authorised role" hint="Roles are assigned by a superuser — users cannot choose their own.">
          <select value={values.role} onChange={set("role")}>
            {Object.entries(ROLES).map(([key, role]) => (
              <option key={key} value={key}>
                {role.label}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label="Hospital assignment"
          error={errors.hospitalId}
          hint={values.role === "hospital_staff" ? "Staff only see incidents for this hospital." : "Only hospital staff are assigned to a hospital."}
        >
          <select value={values.hospitalId} onChange={set("hospitalId")} disabled={values.role !== "hospital_staff"}>
            <option value="">{values.role === "hospital_staff" ? "Select a hospital" : "Not applicable"}</option>
            {choices.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name}
                {h.active ? "" : " (inactive)"}
              </option>
            ))}
          </select>
        </Field>
      </form>
    </Modal>
  );
}

