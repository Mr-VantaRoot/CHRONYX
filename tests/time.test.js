import test from 'node:test';
import assert from 'node:assert/strict';
import {countdown} from '../src/time.js';

test('formats the exact day/hour/minute/second boundary',()=>{
  const now=Date.parse('2030-01-01T00:00:00Z');
  assert.equal(countdown('2030-01-02T01:02:03Z',now),'1d 01h 02m 03s');
});
test('handles expired, same instant and invalid timestamps',()=>{
  const now=Date.parse('2030-01-01T00:00:00Z');
  assert.equal(countdown('2029-12-31T23:59:59Z',now),'Passed');
  assert.equal(countdown('2030-01-01T00:00:00Z',now),'0d 00h 00m 00s');
  assert.equal(countdown('bad-date',now),'Invalid date');
});
