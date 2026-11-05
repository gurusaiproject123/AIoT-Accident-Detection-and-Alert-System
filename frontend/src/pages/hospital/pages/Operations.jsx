import { useHospital } from "../HospitalContext";
import { formatDateTime } from "../data";

export default function Operations() {
  const { history, openIncident, motion, setMotion, enableSound } = useHospital();
  return <div className="hd-bottom-grid">
    <section className="hd-panel">
      <div className="hd-panel-title"><h2>Recent alert activity</h2></div>
      <div className="hd-activity-list">
        {!history.length && <p>No activity recorded yet.</p>}
        {history.map((item, index) => <div className="hd-activity-row" key={`${item.id}-${index}`}>
          <button className="hd-text-link" onClick={() => openIncident(item.id)}>{item.code}</button>
          <div>{item.text}<p>{formatDateTime(item.at)}</p></div>
        </div>)}
      </div>
    </section>
    <section className="hd-panel">
      <div className="hd-panel-title"><h2>Workspace preferences</h2></div>
      <div className="hd-activity-list">
        <label><input type="checkbox" checked={motion} onChange={(event) => setMotion(event.target.checked)} /> Enable animations</label>
        <button className="hd-button hd-button-secondary" onClick={enableSound}>Activate or test alarm</button>
      </div>
    </section>
  </div>;
}
