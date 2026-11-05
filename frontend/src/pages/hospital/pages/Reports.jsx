import { useHospital } from "../HospitalContext";
import { Icon, Orb } from "../components/ui";

export default function Reports() {
  const { incidents, exportCsv, hospitalName } = useHospital();
  return (
    <>
      <div className="hd-report-hero">
        <div>
          <span className="hd-eyebrow">HOSPITAL ACTIVITY</span>
          <h2>A clearer view of your response.</h2>
          <p>
            Export the alert summary for your hospital.
          </p>
          <button className="hd-button hd-button-primary" onClick={exportCsv}>
            <Icon name="download" size={17} /> Export incident CSV
          </button>
        </div>
        <Orb small />
      </div>
      <div className="hd-report-grid">
        <section className="hd-panel">
          <div className="hd-panel-title">
            <h2>Incident status breakdown</h2>
          </div>
          <div className="hd-bars">
            {[
              "New",
              "Acknowledged",
              "Accepted",
              "Declined",
              "Timed out",
              "Withdrawn",
              "Closed",
            ].map((s) => {
              const count = incidents.filter((i) => i.status === s).length;
              return (
                <div key={s}>
                  <div>
                    <span>{s}</span>
                    <strong>{count}</strong>
                  </div>
                  <div className="hd-bar-track">
                    <span
                      style={{
                        width: `${(count / Math.max(1, incidents.length)) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </section>
        <section className="hd-panel hd-report-summary">
          <Icon name="shield" size={30} />
          <h2>Hospital-scoped reporting</h2>
          <p>
            {incidents.length} alerts are available for {hospitalName}.{" "}
            {incidents.filter((i) => i.lat !== null).length} have reported GPS
            coordinates.
          </p>
          <p>
            These figures describe workflow activity. They do not measure
            crash-detection accuracy, ambulance dispatch or patient outcomes.
          </p>
        </section>
      </div>
    </>
  );
}
