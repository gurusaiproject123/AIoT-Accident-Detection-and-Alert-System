import { useHospital } from "../HospitalContext";
import { HOSPITAL, time, date } from "../data";
import { Icon } from "../components/ui";

export default function Operations() {
  const {
    history,
    openIncident,
    enableSound,
    sound,
    motion,
    setMotion,
    resetDemo,
  } = useHospital();
  return (
    <div className="hd-operations-grid">
      <section className="hd-panel">
        <div className="hd-panel-title">
          <div>
            <h2>Hospital action timeline</h2>
            <p>Local demo actions, most recent first.</p>
          </div>
          <span className="hd-pill">{history.length} events</span>
        </div>
        <div className="hd-history">
          {history.map((e, i) => (
            <div className="hd-history-row" key={`${e.id}-${i}`}>
              <span className="hd-history-node">
                <Icon name="clock" size={17} />
              </span>
              <div>
                <button
                  className="hd-text-link"
                  onClick={() => openIncident(e.id)}
                >
                  {e.id} <Icon name="arrow" size={13} />
                </button>
                <p>{e.text}</p>
                <small>
                  {e.user} · {date(e.at)} at {time(e.at)}
                </small>
              </div>
            </div>
          ))}
        </div>
      </section>
      <section className="hd-panel hd-settings">
        <div className="hd-panel-title">
          <div>
            <h2>Workspace preferences</h2>
            <p>Changes apply to this browser’s demonstration only.</p>
          </div>
          <Icon name="settings" />
        </div>
        <div className="hd-setting-row">
          <div>
            <strong>Alert sound</strong>
            <p>
              Always armed. Rings while New incidents remain and stops after
              acknowledgment. Your first click activates browser audio.
            </p>
          </div>
          <button
            className="hd-button hd-button-secondary"
            onClick={enableSound}
          >
            <Icon name="sound" size={17} />
            {sound ? "Test alarm" : "Activate audio"}
          </button>
        </div>
        <div className="hd-setting-row">
          <div>
            <strong>Ambient animation</strong>
            <p>
              Slow floating ribbons and background particles. Device
              reduced-motion preferences take precedence.
            </p>
          </div>
          <button
            className={`hd-toggle ${motion ? "is-on" : ""}`}
            role="switch"
            aria-checked={motion}
            aria-label="Ambient animation"
            onClick={() => setMotion(!motion)}
          >
            <span />
          </button>
        </div>
        <div className="hd-setting-row">
          <div>
            <strong>Hospital workspace</strong>
            <p>
              {HOSPITAL.name} · {HOSPITAL.id}
              <br />
              Demo hospital operator · Supabase authentication not connected.
            </p>
          </div>
          <Icon name="hospital" />
        </div>
        <div className="hd-setting-row">
          <div>
            <strong>Reset demonstration</strong>
            <p>
              Restore sample incidents and remove this browser’s demo response
              history.
            </p>
          </div>
          <button
            className="hd-button hd-button-danger-outline"
            onClick={resetDemo}
          >
            Reset demo
          </button>
        </div>
      </section>
    </div>
  );
}
