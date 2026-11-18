// Normalize legacy incident descriptions for display, including existing records.
export function incidentText(value) {
  if (typeof value !== "string") return value;
  return value.replace(/\bsuspected accident(s)?(?: detected)?\b/gi, (match, plural) => {
    const text = plural ? "accidents detected" : "accident detected";
    return /^[A-Z]/.test(match) ? text[0].toUpperCase() + text.slice(1) : text;
  });
}
