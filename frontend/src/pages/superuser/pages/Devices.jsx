import { useState } from "react";
import Icon from "../components/Icon";
import { EmptyState, FilterTabs, PageHeading, Panel, SearchInput, StatCard, StatusBadge } from "../components/ui";
import { useSuperuser } from "../useSuperuser";
import { DEVICE_STATUS, GPS_STATUS, formatCoords, formatDateTime, formatRelative, mapsUrl } from "../data";

export default function Devices() {
  const { devices, incidents, now } = useSuperuser();
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");

  const text = query.trim().toLowerCase();
  const filtered = devices
    .filter((d) => status === "all" || d.status === status)
    .filter((d) =>
      !text ? true : [d.id, d.vehicle, d.vehicleModel, d.owner].join(" ").toLowerCase().includes(text),
    );

  const count = (key) => devices.filter((d) => d.status === key).length;
  const incidentCount = (id) => incidents.filter((i) => i.deviceId === id).length;

  return (
    <div className="su-page">
      <PageHeading
        eyebrow="Superuser / Device monitoring"
        title="Devices"
        subtitle="Connection status, last-seen time and GPS status for every ESP32 unit."
      />

      <div className="su-stats">
        <StatCard label="Online" value={count("online")} hint="Communicating with the system" icon="wifi" tone="green" />
        <StatCard label="Offline" value={count("offline")} hint="No recent heartbeat" icon="wifiOff" tone="grey" />
        <StatCard label="Sensor faults" value={count("fault")} hint="Reporting but readings invalid" icon="alert" tone="red" />
        <StatCard
          label="GPS issues"
          value={devices.filter((d) => d.gps !== "fix").length}
          hint="Outdated or missing location"
          icon="mapPin"
          tone="amber"
        />
      </div>

      <Panel className="su-panel-flush">
        <div className="su-toolbar">
          <FilterTabs
            label="Device status"
            value={status}
            onChange={setStatus}
            options={[
              { value: "all", label: "All", count: devices.length },
              { value: "online", label: "Online", count: count("online") },
              { value: "offline", label: "Offline", count: count("offline") },
              { value: "fault", label: "Fault", count: count("fault") },
            ]}
          />
          <SearchInput value={query} onChange={setQuery} placeholder="Search device, vehicle, owner…" />
        </div>

        {filtered.length === 0 ? (
          <EmptyState icon="cpu" title="No devices match these filters" />
        ) : (
          <div className="su-table-wrap">
            <table className="su-table">
              <thead>
                <tr>
                  <th scope="col">Device</th>
                  <th scope="col">Vehicle</th>
                  <th scope="col">Connection</th>
                  <th scope="col">Last seen</th>
                  <th scope="col">GPS status</th>
                  <th scope="col">Last location</th>
                  <th scope="col">Incidents</th>
                  <th scope="col">Firmware</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((device) => {
                  const url = mapsUrl(device.lat, device.lng);
                  return (
                    <tr key={device.id}>
                      <td>
                        <span className="su-device-cell">
                          <span className={`su-device-icon su-tone-${DEVICE_STATUS[device.status].tone}`}>
                            <Icon name="cpu" size={15} />
                          </span>
                          <span className="su-mono su-strong">{device.id}</span>
                        </span>
                      </td>
                      <td>
                        <span className="su-two-line">
                          <strong>{device.vehicle}</strong>
                          <small>{device.vehicleModel}</small>
                        </span>
                      </td>
                      <td>
                        <StatusBadge map={DEVICE_STATUS} value={device.status} />
                      </td>
                      <td title={formatDateTime(device.lastSeen)}>{formatRelative(device.lastSeen, now)}</td>
                      <td>
                        <StatusBadge map={GPS_STATUS} value={device.gps} />
                      </td>
                      <td>
                        {url ? (
                          <a href={url} target="_blank" rel="noreferrer" className="su-link su-mono">
                            {formatCoords(device.lat, device.lng)} <Icon name="external" size={12} />
                          </a>
                        ) : (
                          <span className="su-muted">Location unavailable</span>
                        )}
                      </td>
                      <td>{incidentCount(device.id)}</td>
                      <td className="su-mono">{device.firmware}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="su-table-foot">
          Demo values only — live heartbeat, network and GPS data will come from the backend.
        </p>
      </Panel>
    </div>
  );
}

