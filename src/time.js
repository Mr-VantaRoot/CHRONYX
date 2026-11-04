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
