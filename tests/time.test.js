import test from 'node:test';
import assert from 'node:assert/strict';
import {countdown, calendarDayKey, fromZonedDateTime} from '../src/time.js';

test('formats the exact day/hour/minute/second boundary',()=>{
  const now=Date.parse('2030-01-01T00:00:00Z');
  assert.equal(countdown('2030-01-02T01:02:03Z',now),'1d 01h 02m 03s');
});

test('calendar grouping uses the event timezone around UTC midnight',()=>{
  assert.equal(calendarDayKey('2030-01-01T00:30:00Z','America/Los_Angeles'),'2029-12-31');
  assert.equal(calendarDayKey('2030-01-01T00:30:00Z','Africa/Nairobi'),'2030-01-01');
  assert.equal(calendarDayKey('2030-01-01T00:30:00Z','Invalid/Zone'),'');
});

test('local event inputs preserve intended wall time and reject DST gaps',()=>{
  assert.equal(fromZonedDateTime('2025-03-30T03:30','Europe/Berlin'),'2025-03-30T01:30:00.000Z');
  assert.equal(fromZonedDateTime('2025-03-30T02:30','Europe/Berlin'),null);
  // The repeated autumn wall time resolves deterministically to the earlier instant.
  assert.equal(fromZonedDateTime('2025-10-26T02:30','Europe/Berlin'),'2025-10-26T00:30:00.000Z');
  assert.equal(fromZonedDateTime('2025-01-01T10:00','Invalid/Zone'),null);
});
test('handles expired, same instant and invalid timestamps',()=>{
  const now=Date.parse('2030-01-01T00:00:00Z');
  assert.equal(countdown('2029-12-31T23:59:59Z',now),'Passed');
  assert.equal(countdown('2030-01-01T00:00:00Z',now),'0d 00h 00m 00s');
  assert.equal(countdown('bad-date',now),'Invalid date');
});
