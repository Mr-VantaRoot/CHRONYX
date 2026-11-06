import {fromZonedDateTime} from './time.js';

const categories = new Set([
  'CTF',
  'Hackathon',
  'AI / ML',
  'Robotics',
  'Programming',
  'Scholarship',
  'Technology',
  'Other',
]);
const statuses = new Set([
  'Interested',
  'Registered',
  'Registration closed',
  'Participating',
  'Completed',
  'Cancelled',
]);
const priorities = new Set(['Low', 'Medium', 'High', 'Critical']);
const limits = {
  id: 128,
  name: 200,
  description: 8000,
  category: 40,
  organizer: 200,
  website: 2048,
  registrationUrl: 2048,
  timezone: 128,
  status: 40,
  priority: 20,
  notes: 16000,
};
const optionalText = ['description', 'organizer', 'website', 'registrationUrl', 'end', 'deadline', 'notes'];

function normalizeInstant(value, field, zone, required) {
  if (value === '' && !required) return {value: ''};
  if (typeof value !== 'string' || !value) return {error: `${field} must be an ISO 8601 timestamp`};
  if (/(?:[zZ]|[+-]\d{2}:\d{2})$/.test(value)) {
    if (!Number.isFinite(Date.parse(value))) return {error: `${field} must be a valid ISO 8601 timestamp`};
    return {value: new Date(value).toISOString()};
  }
  const normalized = fromZonedDateTime(value, zone);
  return normalized
    ? {value: normalized}
    : {error: `${field} must include a UTC offset or be a valid local time in ${zone}`};
}

function validUrl(value, field) {
  if (!value) return '';
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || !url.hostname) throw new Error();
    return '';
  } catch {
    return `${field} must be an http or https URL`;
  }
}

export function validateImportFile(value) {
  if (!Array.isArray(value)) throw new Error('JSON backup must contain an array of competitions.');
  const valid = [];
  const skipped = [];
  value.forEach((original, index) => {
    const fail = (reason) =>
      skipped.push({index, name: typeof original?.name === 'string' ? original.name.slice(0, 200) : '', reason});
    if (!original || typeof original !== 'object' || Array.isArray(original))
      return fail('Event must be a JSON object');
    const event = {...original};
    for (const field of optionalText) if (event[field] === undefined) event[field] = '';
    for (const field of Object.keys(limits)) {
      if (typeof event[field] !== 'string' || event[field].length > limits[field]) {
        fail(`${field} must be text no longer than ${limits[field]} characters`);
        return;
      }
    }
    for (const field of ['id', 'name', 'category', 'timezone', 'status', 'priority', 'created']) {
      if (typeof event[field] !== 'string' || !event[field].trim()) {
        fail('Missing required event fields');
        return;
      }
    }
    event.id = event.id.trim();
    event.name = event.name.trim();
    event.category = event.category.trim();
    event.timezone = event.timezone.trim();
    event.status = event.status.trim();
    event.priority = event.priority.trim();
    if (!categories.has(event.category)) return fail('Unknown competition category');
    if (!statuses.has(event.status)) return fail('Unknown registration status');
    if (!priorities.has(event.priority)) return fail('Unknown priority');
    try {
      new Intl.DateTimeFormat('en', {timeZone: event.timezone});
    } catch {
      return fail('Timezone must be a valid IANA timezone');
    }
    for (const field of ['start', 'end', 'deadline', 'created']) {
      const normalized = normalizeInstant(
        event[field] ?? '',
        field,
        event.timezone,
        field === 'start' || field === 'created',
      );
      if (normalized.error) return fail(normalized.error);
      event[field] = normalized.value;
    }
    if (event.end && event.end < event.start) return fail('End must be at or after start');
    for (const field of ['website', 'registrationUrl']) {
      const error = validUrl(event[field], field);
      if (error) return fail(error);
    }
    valid.push({index, event});
  });
  return {valid, skipped};
}
