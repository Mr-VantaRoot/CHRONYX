import {fromZonedDateTime} from './time.js';
const fmt = (v: string, opts: Intl.DateTimeFormatOptions = {
  month: 'short',
  day: 'numeric',
  year: 'numeric'
}) => v ? new Intl.DateTimeFormat(undefined, opts).format(new Date(v)) : 'Not set';
const inputInZone = (v: string, z: string) => {
  if (!v) return '';
  try {
    const p = new Intl.DateTimeFormat('en-CA', {
      timeZone: z,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    }).formatToParts(new Date(v)).reduce((a: any, x) => ({
      ...a,
      [x.type]: x.value
    }), {});
    return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
  } catch {
    return '';
  }
};
const fromZone = (v: string, z: string) => fromZonedDateTime(v, z) || '';
const calendarDateKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
function safeExternalUrl(value: string) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
  } catch {
    return '';
  }
}
async function openExternal(value: string) {
  const url = safeExternalUrl(value);
  if (!url) return;
  try {
    const response = await fetch('/api/open', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url}),
    });
    if (!response.ok) throw new Error('Could not open link in the system browser.');
  } catch (error) {
    console.error(error);
  }
}
export {fmt, inputInZone, fromZone, calendarDateKey, safeExternalUrl, openExternal};
