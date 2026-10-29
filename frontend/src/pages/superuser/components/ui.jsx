import { useEffect, useId, useRef } from "react";
import { Link } from "react-router";
import Icon from "./Icon";
import { formatDateTime, pad2 } from "../data";

/* ------------------------------------------------------------------ */
/* Badges                                                              */
/* ------------------------------------------------------------------ */

export function Badge({ tone = "grey", children, dot = true }) {
  return (
    <span className={`su-badge su-tone-${tone}`}>
      {dot && <span className="su-badge-dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

/** Renders a status badge from one of the vocabularies in data.js. */
export function StatusBadge({ map, value }) {
  const entry = map[value] ?? { label: value ?? "Unknown", tone: "grey" };
  return <Badge tone={entry.tone}>{entry.label}</Badge>;
}

/* ------------------------------------------------------------------ */
/* Layout building blocks                                              */
/* ------------------------------------------------------------------ */

export function PageHeading({ eyebrow, title, subtitle, actions }) {
  return (
    <div className="su-page-heading">
      <div>
        {eyebrow && <p className="su-eyebrow">{eyebrow}</p>}
        <h1 className="su-title">
          {title}
          <span className="su-title-dot">.</span>
        </h1>
        {subtitle && <p className="su-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="su-page-actions">{actions}</div>}
    </div>
  );
}

export function Panel({ title, subtitle, count, action, icon, className = "", children }) {
  return (
    <section className={`su-panel ${className}`}>
      {(title || action) && (
        <header className="su-panel-head">
          <div>
            <h2 className="su-panel-title">
              {title}
              {count != null && <span className="su-count">{count}</span>}
            </h2>
            {subtitle && <p className="su-panel-sub">{subtitle}</p>}
          </div>
          {action}
          {!action && icon && <Icon name={icon} size={18} className="su-muted-icon" />}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, hint, icon, tone = "green", to }) {
  const content = (
    <>
      <div className="su-stat-top">
        <span className="su-stat-label">{label}</span>
        <span className={`su-stat-icon su-tone-${tone}`}>
          <Icon name={icon} size={17} />
        </span>
      </div>
      <strong className="su-stat-value">{typeof value === "number" ? pad2(value) : value}</strong>
      <span className="su-stat-hint">{hint}</span>
    </>
  );
  return to ? (
    <Link to={to} className="su-stat su-stat-link">
      {content}
    </Link>
  ) : (
    <div className="su-stat">{content}</div>
  );
}

export function EmptyState({ icon = "search", title, children }) {
  return (
    <div className="su-empty">
      <span className="su-empty-icon">
        <Icon name={icon} size={22} />
      </span>
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder = "Search" }) {
  return (
    <label className="su-search">
      <Icon name="search" size={16} />
      <span className="su-visually-hidden">{placeholder}</span>
      <input
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

/** Segmented filter, e.g. All / Online / Offline. */
export function FilterTabs({ options, value, onChange, label = "Filter" }) {
  return (
    <div className="su-tabs" role="tablist" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={value === option.value}
          className={value === option.value ? "is-active" : ""}
          onClick={() => onChange(option.value)}
        >
          {option.label}
          {option.count != null && <span className="su-tab-count">{option.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function DetailList({ items }) {
  return (
    <dl className="su-detail-list">
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ------------------------------------------------------------------ */
/* Modal                                                               */
/* ------------------------------------------------------------------ */

export function Modal({ title, subtitle, onClose, children, footer, size = "md" }) {
  const titleId = useId();
  const dialogRef = useRef(null);

  useEffect(() => {
    const previous = document.activeElement;
    const node = dialogRef.current;
    const focusable = node?.querySelector("input, select, textarea, button");
    focusable?.focus();

    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.classList.add("su-modal-open");
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("su-modal-open");
      previous?.focus?.();
    };
  }, [onClose]);

  return (
    <div className="su-modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={dialogRef}
        className={`su-modal su-modal-${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header className="su-modal-head">
          <div>
            <h2 id={titleId}>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button type="button" className="su-icon-btn" onClick={onClose} aria-label="Close dialog">
            <Icon name="x" />
          </button>
        </header>
        <div className="su-modal-body">{children}</div>
        {footer && <footer className="su-modal-foot">{footer}</footer>}
      </div>
    </div>
  );
}

export function ConfirmDialog({ title, message, confirmLabel = "Confirm", tone = "primary", onConfirm, onClose }) {
  return (
    <Modal
      title={title}
      onClose={onClose}
      size="sm"
      footer={
        <>
          <button type="button" className="su-btn su-btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className={`su-btn ${tone === "danger" ? "su-btn-danger" : "su-btn-primary"}`}
            onClick={() => {
              onConfirm();
              onClose();
            }}
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      <p className="su-modal-text">{message}</p>
    </Modal>
  );
}

export function Field({ label, error, hint, children }) {
  return (
    <label className={`su-field ${error ? "has-error" : ""}`}>
      <span className="su-field-label">{label}</span>
      {children}
      {error ? <span className="su-field-error">{error}</span> : hint && <span className="su-field-hint">{hint}</span>}
    </label>
  );
}

/* ------------------------------------------------------------------ */
/* Visual pieces                                                       */
/* ------------------------------------------------------------------ */

/** Animated concentric ring used in the hero banner. */
export function PulseRing({ alert = false, animated = true }) {
  const rings = [0, 1, 2, 3, 4, 5, 6];
  return (
    <div
      className={`su-ring ${alert ? "is-alert" : ""} ${animated ? "is-animated" : ""}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 200 200">
        <defs>
          <linearGradient id="su-ring-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#6ee7c8" />
            <stop offset="55%" stopColor="#5aa9e6" />
            <stop offset="100%" stopColor="#a78bfa" />
          </linearGradient>
        </defs>
        {rings.map((ring) => (
          <ellipse
            key={ring}
            className="su-ring-line"
            cx="100"
            cy="100"
            rx={78 + ring * 1.6}
            ry={76 - ring * 1.1}
            transform={`rotate(${ring * 26} 100 100)`}
            style={{ animationDelay: `${ring * -1.4}s` }}
          />
        ))}
      </svg>
      <span className="su-ring-core">
        <Icon name="pulse" size={30} strokeWidth={1.8} />
      </span>
    </div>
  );
}

export function Toasts({ toasts, onDismiss }) {
  return (
    <div className="su-toasts" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`su-toast su-tone-${toast.tone}`}>
          <span className="su-badge-dot" aria-hidden="true" />
          <span>{toast.message}</span>
          <button type="button" onClick={() => onDismiss(toast.id)} aria-label="Dismiss notification">
            <Icon name="x" size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}

/** Shared incidents table: Incident ID | Device | Time | Location | Status | Action. */
export function IncidentTable({ incidents, statusMap, compact = false }) {
  return (
    <div className="su-table-wrap">
      <table className="su-table">
        <thead>
          <tr>
            <th scope="col">Incident ID</th>
            <th scope="col">Device</th>
            <th scope="col">Time</th>
            {!compact && <th scope="col">Location</th>}
            <th scope="col">Status</th>
            <th scope="col" className="su-align-right">
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((incident) => (
            <tr key={incident.id}>
              <td>
                <span className="su-mono su-strong">{incident.id}</span>
              </td>
              <td className="su-mono">{incident.deviceId}</td>
              <td>{formatDateTime(incident.detectedAt)}</td>
              {!compact && (
                <td className="su-cell-location">
                  <Icon name="mapPin" size={14} />
                  <span>{incident.location?.label ?? "Location unavailable"}</span>
                </td>
              )}
              <td>
                <StatusBadge map={statusMap} value={incident.status} />
              </td>
              <td className="su-align-right">
                <Link to={`/superuser/incidents/${incident.id}`} className="su-btn su-btn-soft su-btn-sm">
                  View details
                  <Icon name="chevronRight" size={14} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

