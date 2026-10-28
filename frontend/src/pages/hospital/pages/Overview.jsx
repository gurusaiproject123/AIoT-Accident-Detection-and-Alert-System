import { Link } from "react-router";
import { useHospital } from "../HospitalContext";
import { time } from "../data";
import { Icon, Orb, MapView, IncidentTable } from "../components/ui";

export default function Overview() {
  const {
    incidents,
    newCount,
    active,
    history,
    openIncident,
    enableSound,
    sound,
  } = useHospital();
  return (
    <>
      <section className="hd-hero">
        <div className="hd-hero-copy">
          <span className="hd-hero-kicker">
            <span /> READY TO RESPOND
          </span>
          <h2>
            Connected care.
            <br />
            <span>Faster awareness.</span>
          </h2>
          <p>
            Your hospital’s accident alerts, locations and response activity —
            together in one place.
          </p>
          <Link className="hd-button hd-button-mint" to="/hospital/incidents">
            Review assigned alerts <Icon name="arrow" size={16} />
          </Link>
          <small>Academic prototype · all incidents are simulated</small>
        </div>
        <div className="hd-hero-art">
          <div className="hd-hero-grid" />
          <Orb />
          <span className="hd-float-chip hd-chip-one">
            <Icon name="pin" size={14} /> Location received
          </span>
          <span className="hd-float-chip hd-chip-two">
            <span className="hd-dot" /> Incident awareness
          </span>
        </div>
      </section>
      <div className="hd-section-title">
        <h2>At a glance</h2>
        <span>Assigned to this hospital</span>
      </div>
      <div className="hd-stats">
        {[
          ["New alerts", newCount, "bell", "rose", "Awaiting acknowledgment"],
          [
            "Acknowledged",
            incidents.filter((i) => i.status === "Acknowledged").length,
            "check",
            "blue",
            "Receipt confirmed",
          ],
          [
            "Accepted",
            incidents.filter((i) => i.status === "Accepted").length,
            "shield",
            "teal",
            "Response accepted",
          ],
          [
            "Closed",
            incidents.filter((i) => i.status === "Closed").length,
            "clock",
            "violet",
            "Recorded outcomes",
          ],
        ].map(([label, value, icon, color, desc]) => (
          <article className="hd-stat" key={label}>
            <div className="hd-stat-top">
              <span>{label}</span>
              <span className={`hd-stat-icon hd-${color}`}>
                <Icon name={icon} size={19} />
              </span>
            </div>
            <strong>{String(value).padStart(2, "0")}</strong>
            <p>{desc}</p>
          </article>
        ))}
      </div>
      <div className="hd-overview-grid">
        <section className="hd-panel hd-alert-panel">
          <div className="hd-panel-title">
            <div>
              <h2>
                Recent incident alerts{" "}
                <span className="hd-count">{active.length}</span>
              </h2>
              <p>Review the latest activity assigned to your team.</p>
            </div>
            <Link to="/hospital/incidents" className="hd-text-link">
              View all <Icon name="arrow" size={14} />
            </Link>
          </div>
          <IncidentTable items={incidents.slice(0, 4)} />
          <div className="hd-panel-footer">
            <Icon name="shield" size={14} />
            <span>
              Acknowledgment confirms receipt. Acceptance confirms a response.
            </span>
          </div>
        </section>
        <section className="hd-panel hd-location-panel">
          <div className="hd-panel-title">
            <div>
              <h2>Incident locations</h2>
              <p>Your hospital’s assigned incidents.</p>
            </div>
            <Icon name="map" size={18} />
          </div>
          <MapView incidents={active} onSelect={openIncident} />
          <div className="hd-map-footer">
            <span>
              <i /> Hospital <b /> Incident
            </span>
            <Link to="/hospital/health" className="hd-text-link">
              Explore map <Icon name="arrow" size={14} />
            </Link>
          </div>
        </section>
      </div>
      <div className="hd-bottom-grid">
        <section className="hd-panel">
          <div className="hd-panel-title">
            <div>
              <h2>Response activity</h2>
              <p>Most recent recorded actions.</p>
            </div>
            <Link to="/hospital/operations" className="hd-text-link">
              History <Icon name="arrow" size={14} />
            </Link>
          </div>
          <div className="hd-activity-list">
            {history.slice(0, 3).map((e, i) => (
              <div className="hd-activity-row" key={`${e.id}-${i}`}>
                <span className="hd-activity-icon">
                  <Icon name={i === 0 ? "bell" : "check"} size={15} />
                </span>
                <div>
                  <strong>{e.id}</strong>
                  <p>{e.text}</p>
                </div>
                <small>{time(e.at)}</small>
              </div>
            ))}
          </div>
        </section>
        <section className="hd-readiness">
          <span className="hd-stat-icon hd-teal">
            <Icon name="pulse" />
          </span>
          <div>
            <h3>A clear picture. A prepared team.</h3>
            <p>
              The alarm stays armed and rings for new incidents. Acknowledge
              every new incident to stop the sound.
            </p>
            <button className="hd-text-link" onClick={enableSound}>
              {sound ? "Test alarm" : "Activate audio"}{" "}
              <Icon name="arrow" size={14} />
            </button>
          </div>
        </section>
      </div>
    </>
  );
}
