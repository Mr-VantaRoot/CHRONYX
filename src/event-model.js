import {countdown} from './time.js';

export function eventCountdown(event, now = Date.now()) {
  return event.status === 'Completed' || event.status === 'Cancelled' ? event.status : countdown(event.start, now);
}

export function deadlineCountdown(event, now = Date.now()) {
  if (event.status === 'Completed' || event.status === 'Cancelled') return event.status;
  if (!event.deadline) return 'Not set';
  const value = countdown(event.deadline, now);
  return value === 'Passed' ? 'Closed' : value;
}
