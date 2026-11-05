export function countdown(target, now = Date.now()) {
  const instant = Date.parse(target);
  if (!Number.isFinite(instant)) return 'Invalid date';
  let seconds = Math.floor((instant - now) / 1000);
  if (seconds < 0) return 'Passed';
  const days = Math.floor(seconds / 86400); seconds %= 86400;
  const hours = Math.floor(seconds / 3600); seconds %= 3600;
  const minutes = Math.floor(seconds / 60); seconds %= 60;
  return `${days}d ${String(hours).padStart(2,'0')}h ${String(minutes).padStart(2,'0')}m ${String(seconds).padStart(2,'0')}s`;
}

function partsAt(instant, timeZone) {
  const date = new Date(instant);
  if (!Number.isFinite(date.getTime())) return null;
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
    }).formatToParts(date);
    return Object.fromEntries(parts.map(part => [part.type, part.value]));
  } catch {
    return null;
  }
}

/** A stable YYYY-MM-DD calendar key in the supplied IANA timezone. */
export function calendarDayKey(instant, timeZone) {
  const parts = partsAt(instant, timeZone);
  return parts ? `${parts.year}-${parts.month}-${parts.day}` : '';
}

/**
 * Convert a local datetime input into an instant. Returns null for invalid
 * fields and nonexistent wall times during a daylight-saving spring gap.
 * During a repeated fall-back hour, the earlier matching instant is chosen.
 */
export function fromZonedDateTime(value, timeZone) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value || '');
  if (!match) return null;
  const [, ys, mos, ds, hs, mins] = match;
  const year = Number(ys), month = Number(mos), day = Number(ds);
  const hour = Number(hs), minute = Number(mins);
  const desired = Date.UTC(year, month - 1, day, hour, minute);
  const check = new Date(desired);
  if (check.getUTCFullYear() !== year || check.getUTCMonth() !== month - 1 ||
      check.getUTCDate() !== day || hour > 23 || minute > 59) return null;

  let instant = desired;
  for (let i = 0; i < 5; i++) {
    const parts = partsAt(instant, timeZone);
    if (!parts) return null;
    const represented = Date.UTC(Number(parts.year), Number(parts.month) - 1,
      Number(parts.day), Number(parts.hour), Number(parts.minute), Number(parts.second));
    const correction = desired - represented;
    if (correction === 0) break;
    instant += correction;
  }
  const offsets = new Set();
  // Probe the active IANA offsets around this date. This also detects both
  // sides of a daylight-saving fold without guessing the machine's timezone.
  for (let hours = -36; hours <= 36; hours += 6) {
    const probe = instant + hours * 3600000;
    const parts = partsAt(probe, timeZone);
    if (!parts) return null;
    const wallAsUtc = Date.UTC(Number(parts.year), Number(parts.month) - 1,
      Number(parts.day), Number(parts.hour), Number(parts.minute), Number(parts.second));
    offsets.add(wallAsUtc - Math.floor(probe / 1000) * 1000);
  }
  const matches = [];
  for (const offset of offsets) {
    const candidate = desired - offset;
    const parts = partsAt(candidate, timeZone);
    if (parts && Number(parts.year) === year && Number(parts.month) === month &&
        Number(parts.day) === day && Number(parts.hour) === hour && Number(parts.minute) === minute) {
      matches.push(candidate);
    }
  }
  if (!matches.length) return null;
  return new Date(Math.min(...matches)).toISOString();
}
