const EVENTS_KEY = 'vantaEvents';
const OUTBOX_KEY = 'vantaEventOutbox';
const REMINDERS_KEY = 'vantaReminders';
const REMINDERS_OUTBOX_KEY = 'vantaReminderOutbox';

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function storage() {
  return globalThis.localStorage;
}

function cachedEvents() {
  try {
    const raw = storage()?.getItem(EVENTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) throw new Error('Saved competition cache is malformed');
    return parsed.filter(item => item && typeof item.id === 'string' && typeof item.name === 'string');
  } catch (error) {
    if (error instanceof SyntaxError) throw new ApiError('Saved competition cache is damaged. Use your JSON backup to restore it.');
    throw error;
  }
}

function bestEffortCachedEvents() {
  try { return cachedEvents(); }
  catch (error) { console.error('Ignoring unreadable local competition cache:', error); return []; }
}

function outbox() {
  try {
    const raw = storage()?.getItem(OUTBOX_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) throw new Error('Saved offline changes are malformed');
    return parsed.filter(op => op && typeof op.id === 'string' && ['save', 'delete'].includes(op.type));
  } catch (error) {
    if (error instanceof SyntaxError) throw new ApiError('Saved offline changes are damaged. Export available events before continuing.');
    throw error;
  }
}

function writeCache(events) {
  try { storage()?.setItem(EVENTS_KEY, JSON.stringify(events)); }
  catch (error) { console.error('Could not update the local competition cache:', error); }
}

function writeOutbox(operations) {
  try {
    const store = storage();
    if (!store) throw new Error('Browser storage is unavailable');
    store.setItem(OUTBOX_KEY, JSON.stringify(operations));
  }
  catch { throw new ApiError('Offline changes could not be saved in browser storage. Free some storage space and retry.'); }
}

function overlay(events, operations) {
  const byId = new Map(events.map(event => [event.id, event]));
  for (const op of operations) {
    if (op.type === 'delete') byId.delete(op.id);
    else byId.set(op.id, op.event);
  }
  return [...byId.values()].sort((a, b) => Date.parse(a.start) - Date.parse(b.start));
}

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    if (error instanceof TypeError) throw error;
    throw new ApiError('The local data service could not be reached.');
  }
  let result;
  try { result = await response.json(); }
  catch { throw new ApiError('The local data service returned an invalid response.', response.status); }
  if (!response.ok) throw new ApiError(result?.error || `The local data service returned HTTP ${response.status}.`, response.status);
  return result;
}

async function syncOutbox(remoteEvents, operations) {
  const remaining = [...operations];
  for (const op of operations) {
    const path = op.type === 'delete' ? `/api/events/${encodeURIComponent(op.id)}` : '/api/events';
    const options = op.type === 'delete'
      ? { method: 'DELETE' }
      : { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify(op.event) };
    try {
      await requestJson(path, options);
    } catch (error) {
      // Deleting an already-absent row has the same final state.
      if (op.type === 'save' && error instanceof ApiError && error.status === 404) {
        await requestJson('/api/events', {
          method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(op.event),
        });
      } else if (!(op.type === 'delete' && error instanceof ApiError && error.status === 404)) {
        throw error;
      }
    }
    remaining.shift();
    writeOutbox(remaining);
  }
  const merged = overlay(remoteEvents, operations);
  writeCache(merged);
  return merged;
}

export async function loadEvents() {
  try {
    const remote = await requestJson('/api/events');
    if (!Array.isArray(remote) || remote.some(item => !item || typeof item.id !== 'string' || typeof item.name !== 'string')) {
      throw new ApiError('The local data service returned malformed competition data.');
    }
    const operations = outbox();
    let synchronized = remote;
    let syncError = '';
    if (operations.length) {
      try { synchronized = await syncOutbox(remote, operations); }
      catch (error) {
        if (error instanceof TypeError) throw error;
        syncError = error instanceof Error ? error.message : 'Offline changes could not be synchronized.';
        synchronized = overlay(remote, outbox());
      }
    }
    writeCache(synchronized);
    return { events: synchronized, offline: false, syncError };
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    const operations = outbox();
    const events = overlay(cachedEvents(), operations);
    return { events, offline: true };
  }
}

export async function saveEvent(event, existing) {
  const method = existing ? 'PUT' : 'POST';
  const options = { method, headers: { 'content-type': 'application/json' }, body: JSON.stringify(event) };
  try {
    const saved = await requestJson('/api/events', options);
    const events = overlay(bestEffortCachedEvents(), [{ type: 'save', id: saved.id, event: saved }]);
    writeCache(events);
    return { events, offline: false };
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    const events = overlay(cachedEvents(), [{ type: 'save', id: event.id, event }]);
    const operations = outbox().filter(op => op.id !== event.id);
    operations.push({ type: 'save', id: event.id, event });
    writeOutbox(operations);
    writeCache(events);
    return { events, offline: true };
  }
}

export async function deleteEvent(id) {
  try {
    await requestJson(`/api/events/${encodeURIComponent(id)}`, { method: 'DELETE' });
    const events = bestEffortCachedEvents().filter(event => event.id !== id);
    writeCache(events);
    return { events, offline: false };
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    const events = cachedEvents().filter(event => event.id !== id);
    const operations = outbox().filter(op => op.id !== id);
    operations.push({ type: 'delete', id });
    writeOutbox(operations);
    writeCache(events);
    return { events, offline: true };
  }
}

export async function importEvents(events, indices) {
  const result = await requestJson('/api/events/import', {
    method: 'POST',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify({events, indices}),
  });
  if (!Number.isInteger(result?.imported) || result.imported < 0 || !Array.isArray(result.skipped)) {
    throw new ApiError('The local data service returned an invalid import report.');
  }
  if (result.skipped.some(item => !Number.isInteger(item?.index) || typeof item?.reason !== 'string')) {
    throw new ApiError('The local data service returned malformed import errors.');
  }
  return result;
}

function reminderCache() {
  try {
    const raw = storage()?.getItem(REMINDERS_KEY);
    return raw ? JSON.parse(raw) : {'7d': true, '3d': true, '1d': true, '1h': true, customHours: 0};
  } catch (error) {
    if (error instanceof SyntaxError) throw new ApiError('Saved reminder preferences are damaged.');
    throw error;
  }
}

function validateReminders(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ApiError('The local data service returned malformed reminder preferences.');
  const result = {};
  for (const key of ['7d', '3d', '1d', '1h']) {
    if (key in value && typeof value[key] !== 'boolean') throw new ApiError(`Reminder setting ${key} is invalid.`);
    if (key in value) result[key] = value[key];
  }
  if ('customHours' in value) {
    if (!Number.isInteger(value.customHours) || value.customHours < 0 || value.customHours > 8760) throw new ApiError('Custom reminder hours are invalid.');
    result.customHours = value.customHours;
  }
  return result;
}

export async function loadReminderSettings() {
  try {
    const remote = validateReminders(await requestJson('/api/settings'));
    const pending = storage()?.getItem(REMINDERS_OUTBOX_KEY);
    if (pending) {
      const local = validateReminders(JSON.parse(pending));
      const synced = validateReminders(await requestJson('/api/settings', {
        method: 'PATCH', headers: {'content-type': 'application/json'}, body: JSON.stringify(local),
      }));
      storage()?.removeItem(REMINDERS_OUTBOX_KEY);
      storage()?.setItem(REMINDERS_KEY, JSON.stringify(synced));
      return {settings: synced, offline: false};
    }
    storage()?.setItem(REMINDERS_KEY, JSON.stringify(remote));
    return {settings: remote, offline: false};
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    return {settings: validateReminders(reminderCache()), offline: true};
  }
}

let reminderWriteQueue = Promise.resolve();

async function performSaveReminderSettings(settings) {
  const clean = validateReminders(settings);
  try {
    const saved = validateReminders(await requestJson('/api/settings', {
      method: 'PATCH', headers: {'content-type': 'application/json'}, body: JSON.stringify(clean),
    }));
    try { storage()?.setItem(REMINDERS_KEY, JSON.stringify(saved)); } catch (error) { console.error('Could not update reminder cache:', error); }
    try { storage()?.removeItem(REMINDERS_OUTBOX_KEY); } catch (error) { console.error('Could not clear reminder outbox:', error); }
    return {settings: saved, offline: false};
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    try {
      const store = storage();
      if (!store) throw new Error('Browser storage is unavailable');
      store.setItem(REMINDERS_KEY, JSON.stringify(clean));
      store.setItem(REMINDERS_OUTBOX_KEY, JSON.stringify(clean));
    }
    catch { throw new ApiError('Reminder changes could not be queued in local storage.'); }
    return {settings: clean, offline: true};
  }
}

export function saveReminderSettings(settings) {
  const operation = reminderWriteQueue.then(() => performSaveReminderSettings(settings));
  reminderWriteQueue = operation.catch(() => {});
  return operation;
}
