import { useHospital } from "../HospitalContext";
import { formatDateTime } from "../data";
import { MapView } from "../components/ui";

export default function Health() {
  const { incidents, lastSync, feedError, refresh } = useHospital();
  return <div className="hd-bottom-grid">
    <section className="hd-panel">
      <div className="hd-panel-title"><h2>Reported incident locations</h2></div>
      <MapView incidents={incidents} />
    </section>
    <section className="hd-panel">
      <div className="hd-panel-title"><h2>Hospital alert feed</h2></div>
      <div className="hd-activity-list">
        <p>{feedError ? "Refresh failed" : "Feed available"} · Last successful update: {formatDateTime(lastSync)}</p>
        <button className="hd-button hd-button-secondary" onClick={refresh}>Refresh feed</button>
      </div>
    </section>
  </div>;
}
