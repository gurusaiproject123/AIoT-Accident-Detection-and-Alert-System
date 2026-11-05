/** Soft floating background shapes behind the main content area. */
export default function Background({ animated = true }) {
  return (
    <div className={`su-bg ${animated ? "is-animated" : ""}`} aria-hidden="true">
      <span className="su-bg-blob su-bg-blob-1" />
      <span className="su-bg-blob su-bg-blob-2" />
      <span className="su-bg-blob su-bg-blob-3" />
      <span className="su-bg-grid" />
    </div>
  );
}

