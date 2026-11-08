import {useEffect, useMemo, useState} from 'react';
import {AlarmClock, ArrowUpRight, Bell, CalendarClock, Clock3, FileText} from 'lucide-react';
import type {Event, ReminderPrefs} from './types';
import {loadReminderSettings} from './event-store.js';

type RemindersPageProps = {
  events: Event[];
  now: number;
  open: (event?: Event) => void;
  openSettings: () => void;
};

type ReminderItem = {
  event: Event;
  target: 'start' | 'deadline';
  targetAt: number;
  reminderAt: number;
  windowLabel: string;
};

const defaults: ReminderPrefs = {'7d': true, '3d': true, '1d': true, '1h': true, customHours: 0};
const windows: {key: keyof Omit<ReminderPrefs, 'customHours'>; hours: number; label: string}[] = [
  {key: '7d', hours: 168, label: '7 days before'},
  {key: '3d', hours: 72, label: '3 days before'},
  {key: '1d', hours: 24, label: '1 day before'},
  {key: '1h', hours: 1, label: '1 hour before'},
];

function dateParts(value: number, timezone: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      timeZone: timezone,
    }).format(new Date(value));
  } catch {
    return new Date(value).toLocaleString();
  }
}

function timeLeft(target: number, now: number) {
  const seconds = Math.max(0, Math.floor((target - now) / 1000));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;
  if (days) return `${days}d ${String(hours).padStart(2, '0')}h left`;
  if (hours) return `${hours}h ${String(minutes).padStart(2, '0')}m left`;
  return `${minutes}m ${String(remainingSeconds).padStart(2, '0')}s left`;
}

function buildReminderItems(events: Event[], prefs: ReminderPrefs, now: number): ReminderItem[] {
  const configured = windows.filter((item) => prefs[item.key]);
  if (prefs.customHours > 0) {
    configured.push({key: '1h', hours: prefs.customHours, label: `${prefs.customHours} hours before`});
  }

  return events
    .filter((event) => !['Completed', 'Cancelled'].includes(event.status))
    .flatMap((event) => {
      const targets: {kind: ReminderItem['target']; value: string}[] = [
        {kind: 'start', value: event.start},
        {kind: 'deadline', value: event.deadline},
      ];
      return targets.flatMap(({kind, value}) => {
        const targetAt = Date.parse(value);
        if (!value || !Number.isFinite(targetAt) || targetAt <= now) return [];
        const next = configured
          .map((item) => ({
            reminderAt: targetAt - item.hours * 3600000,
            windowLabel: item.label,
          }))
          .filter((item) => item.reminderAt > now && item.reminderAt < targetAt)
          .sort((a, b) => a.reminderAt - b.reminderAt)[0];
        return next ? [{event, target: kind, targetAt, ...next}] : [];
      });
    })
    .sort((a, b) => a.reminderAt - b.reminderAt);
}

export function RemindersPage({events, now, open, openSettings}: RemindersPageProps) {
  const [prefs, setPrefs] = useState(defaults);
  const [settingsError, setSettingsError] = useState('');

  useEffect(() => {
    let mounted = true;
    loadReminderSettings()
      .then((result) => {
        if (mounted) setPrefs({...defaults, ...result.settings});
      })
      .catch((error) => {
        if (mounted) setSettingsError(error instanceof Error ? error.message : 'Reminder settings are unavailable.');
      });
    return () => {
      mounted = false;
    };
  }, []);

  const items = useMemo(() => buildReminderItems(events, prefs, now), [events, prefs, now]);
  const coveredEvents = new Set(items.map((item) => item.event.id)).size;
  const deadlines = items.filter((item) => item.target === 'deadline').length;
  const next = items[0];

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><Bell size={12} /> PERSONAL REMINDER SCHEDULE</div>
          <h1>Reminders</h1>
          <p>See when your next alerts are scheduled and how much time remains for each event.</p>
        </div>
        <button className="outline-button" onClick={openSettings}>
          <AlarmClock size={15} /> Reminder settings <ArrowUpRight size={13} />
        </button>
      </div>

      {settingsError && <div className="notice" role="status">{settingsError} Showing saved reminder defaults.</div>}

      <div className="reminder-stats">
        <section className="reminder-stat">
          <div><Bell size={15} /><span>UPCOMING ALERTS</span></div>
          <strong>{items.length}</strong>
          <small>Next configured notification points</small>
        </section>
        <section className="reminder-stat">
          <div><CalendarClock size={15} /><span>COMPETITIONS COVERED</span></div>
          <strong>{coveredEvents}</strong>
          <small>With at least one upcoming alert</small>
        </section>
        <section className="reminder-stat">
          <div><Clock3 size={15} /><span>DEADLINE ALERTS</span></div>
          <strong>{deadlines}</strong>
          <small>Registration deadlines with alerts ahead</small>
        </section>
      </div>

      <div className="reminder-section-head">
        <div>
          <h2>Next up</h2>
          <p>Scheduled from your reminder preferences in Settings.</p>
        </div>
        <span>{items.length} scheduled</span>
      </div>

      <div className="reminder-list">
        {items.map((item) => (
          <button
            type="button"
            className="reminder-row"
            key={`${item.event.id}:${item.target}`}
            onClick={() => open(item.event)}
          >
            <span className="reminder-date">
              <CalendarClock size={16} />
              <b>{dateParts(item.reminderAt, item.event.timezone)}</b>
              <small>{item.windowLabel}</small>
            </span>
            <span className="reminder-main">
              <span className="reminder-title-line">
                <strong>{item.event.name}</strong>
                <i className={`reminder-kind ${item.target === 'deadline' ? 'deadline' : ''}`}>
                  {item.target === 'deadline' ? 'Registration deadline' : 'Competition start'}
                </i>
              </span>
              <span className="reminder-meta">
                {item.event.category} <span>·</span> {item.event.status} <span>·</span> {item.event.priority} priority
              </span>
              <span className="reminder-note">
                <FileText size={13} />
                {item.event.notes || item.event.description || 'No personal notes added.'}
              </span>
            </span>
            <span className="reminder-countdown">
              <small>{item.target === 'deadline' ? 'DEADLINE IN' : 'STARTS IN'}</small>
              <b>{timeLeft(item.targetAt, now)}</b>
              <span>Target {dateParts(item.targetAt, item.event.timezone)}</span>
            </span>
            <ArrowUpRight size={16} className="reminder-open-icon" />
          </button>
        ))}
        {!items.length && (
          <div className="reminder-empty">
            <span><Bell size={20} /></span>
            <h3>No upcoming reminders</h3>
            <p>Add an event with a future start or registration deadline, or adjust your reminder windows.</p>
            <button className="outline-button" onClick={openSettings}>Review reminder settings</button>
          </div>
        )}
      </div>
    </>
  );
}
