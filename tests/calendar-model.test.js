import test from 'node:test';
import assert from 'node:assert/strict';
import {calendarItemsForDay, calendarItemsForMonth} from '../src/calendar-model.js';

const event = {
  id: 'event-1',
  name: 'Robotics Cup',
  timezone: 'Africa/Nairobi',
  start: '2030-06-01T08:00:00+03:00',
  end: '2030-06-03T17:00:00+03:00',
  deadline: '2030-06-02T10:00:00+03:00',
};

test('calendar includes each day of a multi-day event and a distinct deadline marker', () => {
  assert.deepEqual(
    calendarItemsForDay([event], '2030-06-02').map((x) => x.kind),
    ['competition', 'deadline'],
  );
  assert.deepEqual(
    calendarItemsForDay([event], '2030-06-03').map((x) => x.kind),
    ['competition'],
  );
  assert.deepEqual(calendarItemsForDay([event], '2030-06-04'), []);
});

test('agenda expands multi-day events and registration deadlines into dated rows', () => {
  const rows = calendarItemsForMonth([event], 2030, 5);
  assert.equal(rows.length, 4);
  assert.deepEqual(
    rows.map((x) => x.dayKey),
    ['2030-06-01', '2030-06-02', '2030-06-02', '2030-06-03'],
  );
});

test('calendar groups a deadline by its event timezone near UTC midnight', () => {
  const nearMidnight = {...event, start: '2030-05-31T21:30:00Z', end: '', deadline: '2030-05-31T21:30:00Z'};
  assert.deepEqual(
    calendarItemsForDay([nearMidnight], '2030-06-01').map((x) => x.kind),
    ['competition', 'deadline'],
  );
});
