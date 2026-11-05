import {useState} from 'react';
import {ChevronLeft, ChevronRight} from 'lucide-react';
import type {Event} from './types';
import {calendarDayKey} from './time.js';
import {calendarItemsForDay, calendarItemsForMonth} from './calendar-model.js';
import {calendarDateKey, fmt} from './view-utils';
export function CalendarPage({
  events,
  month,
  setMonth,
  open
}: any) {
  const [mode, setMode] = useState('Month');
  const year = month.getFullYear(),
    m = month.getMonth(),
    first = new Date(year, m, 1),
    days = new Date(year, m + 1, 0).getDate(),
    offset = (first.getDay() + 6) % 7;
  const dayStart = new Date(month);
  dayStart.setHours(0, 0, 0, 0);
  if (mode === 'Week') dayStart.setDate(dayStart.getDate() - (dayStart.getDay() + 6) % 7);
  const dayEnd = new Date(dayStart);
  dayEnd.setDate(dayStart.getDate() + (mode === 'Week' ? 7 : 1));
  const shift = (n: number) => {
    const d = new Date(month);
    if (mode === 'Month' || mode === 'Agenda') {
      d.setDate(1);
      d.setMonth(d.getMonth() + n);
    } else d.setDate(d.getDate() + n * (mode === 'Week' ? 7 : 1));
    setMonth(d);
  };
  const monthItems = calendarItemsForMonth(events, year, m);
  const dayName = (key: string) => {
    const [y, mo, d] = key.split('-').map(Number);
    return new Date(y, mo - 1, d).toLocaleDateString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    });
  };
  const marker = (item: any, key: string, compact = false) => {
    const {
      event,
      kind
    } = item;
    const deadline = kind === 'deadline';
    const startKey = calendarDayKey(event.start, event.timezone);
    const label = deadline ? 'Deadline' : key === startKey ? fmt(event.start, {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: event.timezone
    }) : 'Continues';
    return <button key={`${event.id}:${kind}:${key}`} title={`${deadline ? 'Registration deadline' : 'Competition'}: ${event.name}`} className={`calendar-event ${deadline ? 'calendar-deadline' : ''}`} onClick={() => open(event)}>{deadline ? 'Deadline · ' : !compact ? `${label} · ` : ''}{event.name}{!compact && <small>{deadline ? 'Registration closes' : event.category}</small>}</button>;
  };
  return <><div className="page-heading"><div><div className="eyebrow">YOUR SCHEDULE</div><h1>Calendar</h1><p>Competition dates and deadlines, in one view.</p></div><div className="calendar-tools"><div className="view-switch">{['Month', 'Week', 'Day', 'Agenda'].map((x: string) => <button key={x} className={mode === x ? 'chosen' : ''} onClick={() => setMode(x)}>{x}</button>)}</div><div className="month-nav"><button onClick={() => shift(-1)}><ChevronLeft /></button><b>{mode === 'Month' || mode === 'Agenda' ? month.toLocaleDateString(undefined, {
              month: 'long',
              year: 'numeric'
            }) : mode === 'Day' ? dayStart.toLocaleDateString(undefined, {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
              year: 'numeric'
            }) : `${dayStart.toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric'
            })} – ${new Date(dayEnd.getTime() - 1).toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
              year: 'numeric'
            })}`}</b><button onClick={() => shift(1)}><ChevronRight /></button></div></div></div>
 {mode === 'Month' ? <div className="calendar"><div className="weekdays">{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(x => <span key={x}>{x}</span>)}</div><div className="calendar-grid">{Array.from({
          length: offset
        }, (_, i) => <div className="day muted-day" key={`empty-${i}`} />)}{Array.from({
          length: days
        }, (_, i) => {
          const d = i + 1,
            key = calendarDateKey(new Date(year, m, d)),
            items = calendarItemsForDay(events, key);
          return <div className={`day ${new Date().toDateString() === new Date(year, m, d).toDateString() ? 'today' : ''}`} key={key}><span>{d}</span>{items.map(item => marker(item, key, true))}</div>;
        })}</div></div> : mode === 'Agenda' ? <div className="agenda-list">{monthItems.sort((a: any, b: any) => a.dayKey.localeCompare(b.dayKey) || a.kind.localeCompare(b.kind)).map((item: any) => <button className={`agenda-item ${item.kind === 'deadline' ? 'agenda-deadline' : ''}`} key={`${item.event.id}:${item.kind}:${item.dayKey}`} onClick={() => open(item.event)}><span className="agenda-date">{dayName(item.dayKey)}</span><span className="category-dot" /><span className="agenda-name">{item.event.name}<small>{item.kind === 'deadline' ? 'Deadline · Registration closes' : `${item.event.category} · ${item.event.status}`}</small></span><span className="agenda-time">{item.kind === 'deadline' ? fmt(item.event.deadline, {
            hour: '2-digit',
            minute: '2-digit',
            timeZone: item.event.timezone
          }) : calendarDayKey(item.event.start, item.event.timezone) === item.dayKey ? fmt(item.event.start, {
            hour: '2-digit',
            minute: '2-digit',
            timeZone: item.event.timezone
          }) : 'Continues'}</span><ChevronRight size={15} /></button>)}{!monthItems.length && <div className="activity-empty">Your calendar is empty. Add a competition to get started.</div>}</div> : <div className="day-schedule">{mode === 'Week' && <div className="weekdays">{Array.from({
          length: 7
        }, (_, i) => {
          const d = new Date(dayStart);
          d.setDate(d.getDate() + i);
          return <span key={calendarDateKey(d)}>{d.toLocaleDateString(undefined, {
              weekday: 'short',
              day: 'numeric'
            })}</span>;
        })}</div>}{Array.from({
        length: mode === 'Week' ? 7 : 1
      }, (_, i) => {
        const d = new Date(dayStart);
        d.setDate(d.getDate() + i);
        const key = calendarDateKey(d),
          items = calendarItemsForDay(events, key);
        return <div className="schedule-day" key={key}><b>{d.toLocaleDateString(undefined, {
              weekday: 'long',
              month: 'short',
              day: 'numeric'
            })}</b>{items.map(item => marker(item, key))}{!items.length && <span className="muted">No competitions scheduled.</span>}</div>;
      })}</div>}</>;
}
