import test from 'node:test';
import assert from 'node:assert/strict';
import {validateImportFile} from '../src/import-export.js';

const event = (overrides = {}) => ({
  id: 'ctf-1',
  name: 'Sample CTF',
  category: 'CTF',
  organizer: 'Org',
  description: 'An event',
  website: 'https://example.test',
  registrationUrl: '',
  start: '2030-06-01T09:30',
  end: '',
  deadline: '',
  timezone: 'Africa/Nairobi',
  status: 'Registered',
  priority: 'High',
  notes: '',
  created: '2030-01-01T08:00',
  ...overrides,
});

test('import normalizes offset-free wall times using the event timezone', () => {
  const result = validateImportFile([event()]);
  assert.equal(result.skipped.length, 0);
  assert.equal(result.valid[0].event.start, '2030-06-01T06:30:00.000Z');
  assert.equal(result.valid[0].event.created, '2030-01-01T05:00:00.000Z');
  assert.equal(result.valid[0].event.description, 'An event');
});

test('import reports category, status, priority, timezone, timestamp, URL and length errors by index', () => {
  const values = [
    event({category: 'Mystery'}),
    event({status: 'Maybe'}),
    event({priority: 'Urgent'}),
    event({timezone: 'Mars/Olympus'}),
    event({start: '2030-03-10T02:30', timezone: 'America/New_York'}),
    event({website: 'javascript:alert(1)'}),
    event({name: 'x'.repeat(201)}),
  ];
  const result = validateImportFile(values);
  assert.equal(result.valid.length, 0);
  assert.deepEqual(
    result.skipped.map((item) => item.index),
    [0, 1, 2, 3, 4, 5, 6],
  );
  assert.match(result.skipped[0].reason, /category/);
  assert.match(result.skipped[4].reason, /valid local time/);
  assert.match(result.skipped[5].reason, /http or https/);
  assert.match(result.skipped[6].reason, /200 characters/);
});

test('import rejects non-array backup roots', () => {
  assert.throws(() => validateImportFile({events: []}), /array of competitions/);
});

test('malformed timestamps do not crash batch validation', () => {
  const result = validateImportFile([event({created: 123}), event({start: null})]);
  assert.equal(result.valid.length, 0);
  assert.equal(result.skipped.length, 2);
  assert.match(result.skipped[0].reason, /required event fields/);
  assert.match(result.skipped[1].reason, /ISO 8601/);
});
