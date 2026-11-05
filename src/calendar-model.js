import { calendarDayKey } from './time.js';

/** Return the competition and deadline markers visible on one calendar day. */
export function calendarItemsForDay(events, dayKey) {
  const items = [];
  for (const event of events) {
    const startDay = calendarDayKey(event.start, event.timezone);
    const endDay = calendarDayKey(event.end || event.start, event.timezone);
    if (startDay && endDay && startDay <= dayKey && dayKey <= endDay) {
      items.push({ event, kind: 'competition' });
    }
    if (event.deadline && calendarDayKey(event.deadline, event.timezone) === dayKey) {
      items.push({ event, kind: 'deadline' });
    }
  }
  return items;
}

/** Return one agenda row per visible event/deadline marker in a month. */
export function calendarItemsForMonth(events, year, month) {
  const days = new Date(year, month + 1, 0).getDate();
  const items = [];
  for (let day = 1; day <= days; day += 1) {
    const key = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    for (const item of calendarItemsForDay(events, key)) items.push({ ...item, dayKey: key });
  }
  return items;
}
