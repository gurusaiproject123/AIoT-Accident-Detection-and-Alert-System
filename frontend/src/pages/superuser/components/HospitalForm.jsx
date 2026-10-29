import { useState } from "react";
import { Field, Modal } from "./ui";

const EMPTY = {
  name: "",
  city: "",
  address: "",
  phone: "",
  email: "",
  lat: "",
  lng: "",
  active: true,
};

function validate(values, hospitals, editingId) {
  const errors = {};
  const name = values.name.trim();
  if (!name) errors.name = "Hospital name is required.";
  else if (
    hospitals.some((h) => h.name.toLowerCase() === name.toLowerCase() && h.id !== editingId)
  ) {
    errors.name = "A hospital with this name is already registered.";
  }
  if (!values.city.trim()) errors.city = "City or town is required.";
  if (!values.phone.trim()) errors.phone = "An emergency contact number is required.";
  else if (!/^[+\d][\d\s-]{6,}$/.test(values.phone.trim())) errors.phone = "Enter a valid phone number.";
  if (!values.email.trim()) errors.email = "A notification email is required.";
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) errors.email = "Enter a valid email address.";

  const lat = Number(values.lat);
  const lng = Number(values.lng);
  if (values.lat === "" || Number.isNaN(lat) || lat < -90 || lat > 90) errors.lat = "Latitude between -90 and 90.";
  if (values.lng === "" || Number.isNaN(lng) || lng < -180 || lng > 180) errors.lng = "Longitude between -180 and 180.";
  return errors;
}

/** Register / edit hospital dialog. */
export default function HospitalForm({ hospital, hospitals, onSave, onClose }) {
  const isEdit = Boolean(hospital);
  const [values, setValues] = useState(() =>
    hospital
      ? { ...EMPTY, ...hospital, lat: String(hospital.lat ?? ""), lng: String(hospital.lng ?? "") }
      : EMPTY,
  );
  const [errors, setErrors] = useState({});

  const set = (key) => (event) => {
    const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const submit = (event) => {
    event.preventDefault();
    const found = validate(values, hospitals, hospital?.id);
    setErrors(found);
    if (Object.keys(found).length) return;
    onSave({
      ...(hospital ?? {}),
      name: values.name.trim(),
      city: values.city.trim(),
      address: values.address.trim(),
      phone: values.phone.trim(),
      email: values.email.trim(),
      lat: Number(values.lat),
      lng: Number(values.lng),
      active: values.active,
    });
    onClose();
  };

  return (
    <Modal
      title={isEdit ? `Edit ${hospital.name}` : "Register hospital"}
      subtitle={
        isEdit
          ? `${hospital.id} · changes are recorded in the activity history.`
          : "Registered hospitals can receive incident notifications when active."
      }
      onClose={onClose}
      footer={
        <>
          <button type="button" className="su-btn su-btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="hospital-form" className="su-btn su-btn-primary">
            {isEdit ? "Save changes" : "Register hospital"}
          </button>
        </>
      }
    >
      <form id="hospital-form" className="su-form-grid" onSubmit={submit} noValidate>
        <Field label="Hospital name" error={errors.name}>
          <input value={values.name} onChange={set("name")} placeholder="e.g. Bindura Hospital" />
        </Field>
        <Field label="City / town" error={errors.city}>
          <input value={values.city} onChange={set("city")} placeholder="e.g. Bindura" />
        </Field>
        <Field label="Address" hint="Optional">
          <input value={values.address} onChange={set("address")} placeholder="Street and area" />
        </Field>
        <Field label="Emergency phone" error={errors.phone}>
          <input value={values.phone} onChange={set("phone")} placeholder="+263 …" inputMode="tel" />
        </Field>
        <Field label="Notification email" error={errors.email}>
          <input value={values.email} onChange={set("email")} placeholder="emergency@example.com" type="email" />
        </Field>
        <div className="su-form-pair">
          <Field label="Latitude" error={errors.lat}>
            <input value={values.lat} onChange={set("lat")} placeholder="-17.3019" inputMode="decimal" />
          </Field>
          <Field label="Longitude" error={errors.lng}>
            <input value={values.lng} onChange={set("lng")} placeholder="31.3306" inputMode="decimal" />
          </Field>
        </div>
        <label className="su-switch su-form-full">
          <input type="checkbox" checked={values.active} onChange={set("active")} />
          <span className="su-switch-track" aria-hidden="true" />
          <span>
            <strong>Active</strong>
            <small>Active hospitals are included in automatic incident routing.</small>
          </span>
        </label>
      </form>
    </Modal>
  );
}

