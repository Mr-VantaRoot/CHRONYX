import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ApiError,
  loadEvents,
  saveEvent,
  deleteEvent,
  importEvents,
  loadReminderSettings,
  saveReminderSettings,
} from '../src/event-store.js';

const event = (id = 'evt-1') => ({
  id,
  name: 'Sample CTF',
  start: '2030-01-01T00:00:00Z',
  timezone: 'UTC',
});

function useMemoryStorage() {
  const values = new Map();
  globalThis.localStorage = {
    getItem: (key) => (values.has(key) ? values.get(key) : null),
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
  return values;
}

const jsonResponse = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {'content-type': 'application/json'},
  });

test('failed local HTTP response is reported and does not masquerade as an offline save', async () => {
  const values = useMemoryStorage();
  values.set('vantaEvents', JSON.stringify([event()]));
  globalThis.fetch = async () => jsonResponse({error: 'Invalid competition'}, 400);
  await assert.rejects(saveEvent({...event(), name: 'Changed'}, true), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 400);
    return true;
  });
  assert.deepEqual(JSON.parse(values.get('vantaEvents')), [event()]);
  assert.equal(values.has('vantaEventOutbox'), false);
});

test('network-failed saves persist locally and synchronize when service returns', async () => {
  const values = useMemoryStorage();
  globalThis.fetch = async () => {
    throw new TypeError('connection refused');
  };
  const saved = await saveEvent(event(), false);
  assert.equal(saved.offline, true);
  assert.deepEqual(saved.events, [event()]);
  assert.equal(JSON.parse(values.get('vantaEventOutbox')).length, 1);

  const requests = [];
  globalThis.fetch = async (url, options = {}) => {
    requests.push([url, options.method || 'GET']);
    if (url === '/api/events' && !options.method) return jsonResponse([]);
    if (url === '/api/events' && options.method === 'PUT') return jsonResponse(event());
    throw new Error(`Unexpected request ${url}`);
  };
  const loaded = await loadEvents();
  assert.equal(loaded.offline, false);
  assert.deepEqual(loaded.events, [event()]);
  assert.deepEqual(requests, [
    ['/api/events', 'GET'],
    ['/api/events', 'PUT'],
  ]);
  assert.deepEqual(JSON.parse(values.get('vantaEvents')), [event()]);
  assert.deepEqual(JSON.parse(values.get('vantaEventOutbox')), []);
});

test('queued saves use POST when the event no longer exists on the server', async () => {
  const values = useMemoryStorage();
  globalThis.fetch = async () => {
    throw new TypeError('connection refused');
  };
  await saveEvent(event(), false);

  const requests = [];
  globalThis.fetch = async (url, options = {}) => {
    const method = options.method || 'GET';
    requests.push([url, method]);
    if (url === '/api/events' && method === 'GET') return jsonResponse([]);
    if (url === '/api/events' && method === 'PUT') return jsonResponse({error: 'Competition not found'}, 404);
    if (url === '/api/events' && method === 'POST') return jsonResponse(event(), 201);
    throw new Error(`Unexpected request ${method} ${url}`);
  };

  const loaded = await loadEvents();
  assert.deepEqual(loaded.events, [event()]);
  assert.deepEqual(requests, [
    ['/api/events', 'GET'],
    ['/api/events', 'PUT'],
    ['/api/events', 'POST'],
  ]);
  assert.deepEqual(JSON.parse(values.get('vantaEventOutbox')), []);
});

test('network-failed deletions are queued and stay deleted after synchronization', async () => {
  const values = useMemoryStorage();
  values.set('vantaEvents', JSON.stringify([event()]));
  globalThis.fetch = async () => {
    throw new TypeError('service offline');
  };
  const deleted = await deleteEvent('evt-1');
  assert.equal(deleted.offline, true);
  assert.deepEqual(deleted.events, []);

  const requests = [];
  globalThis.fetch = async (url, options = {}) => {
    requests.push([url, options.method || 'GET']);
    if (url === '/api/events' && !options.method) return jsonResponse([event()]);
    if (url === '/api/events/evt-1' && options.method === 'DELETE') return jsonResponse({ok: true});
    throw new Error(`Unexpected request ${url}`);
  };
  const loaded = await loadEvents();
  assert.deepEqual(loaded.events, []);
  assert.deepEqual(requests, [
    ['/api/events', 'GET'],
    ['/api/events/evt-1', 'DELETE'],
  ]);
  assert.deepEqual(JSON.parse(values.get('vantaEventOutbox')), []);
});

test('malformed remote data is rejected instead of clearing the cached data', async () => {
  const values = useMemoryStorage();
  values.set('vantaEvents', JSON.stringify([event()]));
  globalThis.fetch = async () => jsonResponse([{name: 'missing id'}]);
  await assert.rejects(loadEvents(), /malformed competition data/);
  assert.deepEqual(JSON.parse(values.get('vantaEvents')), [event()]);
});

test('reminder preferences queue offline and sync on next read', async () => {
  const values = useMemoryStorage();
  globalThis.fetch = async () => {
    throw new TypeError('service offline');
  };
  const first = await saveReminderSettings({'7d': false, '3d': true, '1d': false, '1h': true, customHours: 12});
  assert.equal(first.offline, true);
  assert.equal(JSON.parse(values.get('vantaReminderOutbox')).customHours, 12);

  const seen = [];
  globalThis.fetch = async (url, options = {}) => {
    seen.push([url, options.method || 'GET']);
    if (url === '/api/settings' && !options.method) return jsonResponse({'7d': true});
    if (url === '/api/settings' && options.method === 'PATCH') return jsonResponse(JSON.parse(options.body));
    throw new Error(`Unexpected request ${url}`);
  };
  const loaded = await loadReminderSettings();
  assert.equal(loaded.offline, false);
  assert.deepEqual(loaded.settings, first.settings);
  assert.deepEqual(seen, [
    ['/api/settings', 'GET'],
    ['/api/settings', 'PATCH'],
  ]);
  assert.equal(values.has('vantaReminderOutbox'), false);
});

test('invalid server response errors are not masked by local settings', async () => {
  useMemoryStorage().set('vantaReminders', JSON.stringify({'7d': true}));
  globalThis.fetch = async () => jsonResponse({error: 'Invalid value'}, 400);
  await assert.rejects(
    saveReminderSettings({'7d': false}),
    (error) => error instanceof ApiError && error.status === 400,
  );
});

test('JSON import uses one batch request and validates the import report', async () => {
  let seen;
  globalThis.fetch = async (url, options) => {
    seen = [url, options.method, JSON.parse(options.body)];
    return jsonResponse({imported: 1, skipped: [{index: 3, name: 'Bad row', reason: 'Unknown category'}]});
  };
  const report = await importEvents([event()], [2]);
  assert.deepEqual(seen, ['/api/events/import', 'POST', {events: [event()], indices: [2]}]);
  assert.equal(report.imported, 1);
  assert.equal(report.skipped[0].index, 3);
});

test('invalid batch import response is rejected', async () => {
  globalThis.fetch = async () => jsonResponse({imported: 1, skipped: 'not-an-array'});
  await assert.rejects(importEvents([], []), /invalid import report/);
});

test('a permanently rejected queued change is discarded and does not block the changes behind it', async () => {
  const values = useMemoryStorage();
  values.set(
    'vantaEventOutbox',
    JSON.stringify([
      {type: 'save', id: 'bad', event: {...event('bad'), name: 'Broken'}},
      {type: 'save', id: 'good', event: event('good')},
    ]),
  );
  const requests = [];
  globalThis.fetch = async (url, options = {}) => {
    const method = options.method || 'GET';
    requests.push(`${method} ${url}`);
    if (method === 'GET') return jsonResponse([]);
    const body = JSON.parse(options.body);
    if (body.id === 'bad') return jsonResponse({error: 'Invalid category'}, 400);
    return jsonResponse(body);
  };
  const loaded = await loadEvents();
  assert.equal(loaded.syncError, '');
  assert.deepEqual(loaded.rejected, [{id: 'bad', type: 'save', name: 'Broken', reason: 'Invalid category'}]);
  assert.deepEqual(
    loaded.events.map((item) => item.id),
    ['good'],
  );
  assert.deepEqual(JSON.parse(values.get('vantaEventOutbox')), []);
  assert.deepEqual(
    JSON.parse(values.get('vantaEvents')).map((item) => item.id),
    ['good'],
  );
  assert.deepEqual(requests, ['GET /api/events', 'PUT /api/events', 'PUT /api/events']);
});

test('temporary server errors keep queued changes so they are retried', async () => {
  const values = useMemoryStorage();
  values.set('vantaEventOutbox', JSON.stringify([{type: 'save', id: 'evt-1', event: event()}]));
  globalThis.fetch = async (url, options = {}) => {
    if (!options.method) return jsonResponse([]);
    return jsonResponse({error: 'database is locked'}, 500);
  };
  const loaded = await loadEvents();
  assert.match(loaded.syncError, /database is locked/);
  assert.deepEqual(loaded.rejected, []);
  assert.equal(JSON.parse(values.get('vantaEventOutbox')).length, 1);
  assert.deepEqual(
    loaded.events.map((item) => item.id),
    ['evt-1'],
  );
});

test('a forbidden response is kept queued because it is fixable, not a bad change', async () => {
  const values = useMemoryStorage();
  values.set('vantaEventOutbox', JSON.stringify([{type: 'save', id: 'evt-1', event: event()}]));
  globalThis.fetch = async (url, options = {}) =>
    options.method ? jsonResponse({error: 'Forbidden origin'}, 403) : jsonResponse([]);
  const loaded = await loadEvents();
  assert.deepEqual(loaded.rejected, []);
  assert.equal(JSON.parse(values.get('vantaEventOutbox')).length, 1);
});

test('a queued change that cannot be recreated after a 404 is discarded with its reason', async () => {
  const values = useMemoryStorage();
  values.set('vantaEventOutbox', JSON.stringify([{type: 'save', id: 'evt-1', event: event()}]));
  globalThis.fetch = async (url, options = {}) => {
    if (!options.method) return jsonResponse([]);
    if (options.method === 'PUT') return jsonResponse({error: 'Competition not found'}, 404);
    return jsonResponse({error: 'Competition already exists'}, 409);
  };
  const loaded = await loadEvents();
  assert.equal(loaded.rejected.length, 1);
  assert.equal(loaded.rejected[0].reason, 'Competition already exists');
  assert.deepEqual(JSON.parse(values.get('vantaEventOutbox')), []);
  assert.deepEqual(loaded.events, []);
});

test('saving an event deleted elsewhere recreates it instead of failing', async () => {
  useMemoryStorage();
  const methods = [];
  globalThis.fetch = async (url, options = {}) => {
    methods.push(options.method);
    if (options.method === 'PUT') return jsonResponse({error: 'Competition not found'}, 404);
    return jsonResponse(event(), 201);
  };
  const saved = await saveEvent(event(), true);
  assert.deepEqual(methods, ['PUT', 'POST']);
  assert.deepEqual(saved.events, [event()]);
});

test('other save errors on an existing event are still reported, not retried as creates', async () => {
  useMemoryStorage();
  const methods = [];
  globalThis.fetch = async (url, options = {}) => {
    methods.push(options.method);
    return jsonResponse({error: 'Invalid competition'}, 400);
  };
  await assert.rejects(saveEvent(event(), true), (error) => error.status === 400);
  assert.deepEqual(methods, ['PUT']);
});
