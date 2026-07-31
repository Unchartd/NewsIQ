/**
 * Date and timezone utilities for NewsIQ Admin Console.
 * Formats timestamps in the user's local device/browser timezone.
 */

export function formatLocalDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  
  let iso = dateStr.trim();
  // Ensure UTC designator if string lacks explicit timezone offset
  if (
    !iso.endsWith("Z") &&
    !iso.includes("+") &&
    !/-\d{2}:\d{2}$/.test(iso) &&
    !/-\d{4}$/.test(iso)
  ) {
    iso = `${iso}Z`;
  }

  const d = new Date(iso);
  if (isNaN(d.getTime())) return dateStr;

  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}

export function formatLocalDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  let iso = dateStr.trim();
  if (
    !iso.endsWith("Z") &&
    !iso.includes("+") &&
    !/-\d{2}:\d{2}$/.test(iso) &&
    !/-\d{4}$/.test(iso)
  ) {
    iso = `${iso}Z`;
  }
  const d = new Date(iso);
  if (isNaN(d.getTime())) return dateStr;

  return d.toLocaleDateString();
}

export function formatLocalTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  let iso = dateStr.trim();
  if (
    !iso.endsWith("Z") &&
    !iso.includes("+") &&
    !/-\d{2}:\d{2}$/.test(iso) &&
    !/-\d{4}$/.test(iso)
  ) {
    iso = `${iso}Z`;
  }
  const d = new Date(iso);
  if (isNaN(d.getTime())) return dateStr;

  return d.toLocaleTimeString();
}
