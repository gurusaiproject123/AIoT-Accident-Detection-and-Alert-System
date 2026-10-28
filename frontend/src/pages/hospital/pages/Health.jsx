import { useHospital } from "../HospitalContext";
import { Icon, MapView } from "../components/ui";

export default function Health() {
  const { incidents, openIncident } = useHospital();
  return (
    <>
      <section className="hd-panel hd-health-summary">
        <div className="hd-panel-title">
          <div>
            <h2>Connection status</h2>
            <p>
              Only device IDs associated with this hospital’s incidents are
              listed.
            </p>
          </div>
          <span className="hd-pill">Demo mode</span>
        </div>
        <div className="hd-health-status">
          <Icon name="pulse" />
          <div>
            <strong>Live services not connected</strong>
            <p>
              FastAPI telemetry and hospital notifications are not connected. No
              live heartbeat or network health is being measured.
            </p>
          </div>
        </div>
        <div className="hd-health-devices">
          {[...new Set(incidents.map((i) => i.device))].map((device) => (
            <div key={device}>
              <Icon name="car" size={17} />
              <strong>{device}</strong>
              <span>Connection unknown · sample record</span>
            </div>
          ))}
        </div>
      </section>
      <>
        <div className="hd-map-page">
          <section className="hd-panel">
            <div className="hd-panel-title">
              <div>
                <h2>Location overview</h2>
                <p>
                  Schematic preview. Open an incident for its coordinate link.
                </p>
              </div>
              <span className="hd-pill">
                {incidents.filter((i) => i.lat !== null).length} GPS available
              </span>
            </div>
            <MapView incidents={incidents} onSelect={openIncident} large />
          </section>
          <section className="hd-panel">
            <div className="hd-panel-title">
              <h2>Assigned locations</h2>
            </div>
            <div className="hd-location-list">
              {incidents.map((i) => (
                <button key={i.id} onClick={() => openIncident(i.id)}>
                  <span className="hd-location-dot">
                    <Icon name="pin" size={17} />
                  </span>
                  <span>
                    <strong>{i.location}</strong>
                    <small>
                      {i.id} ·{" "}
                      {i.lat === null
                        ? "GPS unavailable"
                        : `${i.lat}, ${i.lng}`}
                    </small>
                  </span>
                  <Icon name="arrow" size={16} />
                </button>
              ))}
            </div>
          </section>
        </div>
        <p className="hd-footnote">
          Marker positions are illustrative. Actual sample coordinates are shown
          in incident details; replace this schematic with a geographic map
          during backend integration.
        </p>
      </>
    </>
  );
}
