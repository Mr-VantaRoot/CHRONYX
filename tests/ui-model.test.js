import test from 'node:test';
import assert from 'node:assert/strict';
import {matchesEventFilters} from '../src/filter-model.js';
import {deadlineCountdown} from '../src/event-model.js';
import {calendarItemsForDay} from '../src/calendar-model.js';
import {validateImportFile} from '../src/import-export.js';

const event = {
  id: 'event-1', name: 'Sample CTF', category: 'CTF', status: 'Registered', priority: 'High',
  start: '2030-01-02T00:00:00Z', end: '', deadline: '2030-01-01T01:00:00Z', timezone: 'UTC',
};

test('All status and priority options reset their filters', () => {
  assert.equal(matchesEventFilters(event, {status: 'All', priority: 'All'}), true);
  assert.equal(matchesEventFilters(event, {status: 'Completed', priority: 'All'}), false);
});

test('registration deadline countdown uses the deadline and preserves terminal status', () => {
  const now = Date.parse('2030-01-01T00:00:00Z');
  assert.equal(deadlineCountdown(event, now), '0d 01h 00m 00s');
  assert.equal(deadlineCountdown({...event, deadline: '2029-12-31T23:59:59Z'}, now), 'Closed');
  assert.equal(deadlineCountdown({...event, status: 'Completed'}, now), 'Completed');
});

test('calendar exposes registration deadlines as separate date markers', () => {
  assert.deepEqual(calendarItemsForDay([event], '2030-01-01').map(item => item.kind), ['deadline']);
});

test('JSON import validator skips invalid events with an indexed reason', () => {
  const valid = {...event, created: '2029-01-01T00:00:00Z'};
  const report = validateImportFile([valid, {...valid, priority: 'Urgent'}]);
  assert.equal(report.valid.length, 1);
  assert.deepEqual(report.skipped.map(item => item.index), [1]);
  assert.match(report.skipped[0].reason, /priority/);
});
