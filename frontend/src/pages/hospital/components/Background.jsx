import medicalBackground from "../assets/medical-background.webp";

export default function Background() {
  return (
    <div className="hd-ambient" aria-hidden="true">
      <div
        className="hd-medical-photo"
        style={{ backgroundImage: `url(${medicalBackground})` }}
      />
      <div className="hd-medical-veil" />
      <span />
      <span />
      <span />
      {Array.from({ length: 12 }, (_, i) => (
        <i key={i} style={{ "--p": i }} />
      ))}
    </div>
  );
}
