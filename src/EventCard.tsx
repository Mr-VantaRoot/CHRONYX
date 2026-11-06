import {AlarmClock, ArrowUpRight, CalendarDays, MoreHorizontal} from 'lucide-react';
import type {Event} from './types';
import {deadlineCountdown, eventCountdown} from './event-model.js';
import {fmt, openExternal, safeExternalUrl} from './view-utils';
type EventCardProps = {
  e: Event;
  open: (event?: Event) => void;
  menu: string;
  setMenu: (id: string) => void;
  remove: (id: string) => void;
  complete: (event: Event) => void;
  notify: (message: string) => void;
};
const linkLabels = (e: Event): [string, string][] => [
  ['Website', e.website],
  ['Register', e.registrationUrl],
];
export function EventCard({e, open, menu, setMenu, remove, complete, notify}: EventCardProps) {
  return (
    <article className="event-card" onClick={() => open()}>
      <div className="card-top">
        <span className="category-pill">
          <span className="category-dot" />
          {e.category}
        </span>
        <button
          className="dots"
          onClick={(x) => {
            x.stopPropagation();
            setMenu(menu === e.id ? '' : e.id);
          }}
        >
          <MoreHorizontal size={17} />
        </button>
        {menu === e.id && (
          <div className="popmenu" onClick={(x) => x.stopPropagation()}>
            <button onClick={() => open()}>View / edit details</button>
            <button
              onClick={() => {
                open({
                  ...e,
                  id: crypto.randomUUID(),
                  name: `${e.name} (copy)`,
                  created: new Date().toISOString(),
                  status: 'Interested',
                });
              }}
            >
              Duplicate competition
            </button>
            <button onClick={() => complete(e)}>Mark completed</button>
            <button className="danger" onClick={() => remove(e.id)}>
              Delete
            </button>
          </div>
        )}
      </div>
      <h3>{e.name}</h3>
      <p>{e.description || 'No description added.'}</p>
      <div className="card-date">
        <CalendarDays size={14} />
        <span>
          {fmt(e.start, {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            timeZone: e.timezone,
          })}
        </span>
        <span className="date-time">
          {fmt(e.start, {
            hour: '2-digit',
            minute: '2-digit',
            timeZone: e.timezone,
          })}
        </span>
      </div>
      <div className="card-foot">
        <span className="status">{e.status}</span>
        <span className={`priority ${e.priority.toLowerCase()}`}>
          <i /> {e.priority}
        </span>
        <span className="card-count">{eventCountdown(e)}</span>
      </div>
      {e.deadline && (
        <div className="deadline-line">
          <AlarmClock size={12} /> Registration closes{' '}
          {fmt(e.deadline, {
            month: 'short',
            day: 'numeric',
            timeZone: e.timezone,
          })}{' '}
          · {deadlineCountdown(e)}
        </div>
      )}
      <div className="card-links">
        {linkLabels(e)
          .filter(([, url]) => safeExternalUrl(url))
          .map(([label, url]) => (
            <button
              key={label}
              onClick={(event) => {
                event.stopPropagation();
                openExternal(url).catch((error: Error) => notify(error.message));
              }}
            >
              {label}
              <ArrowUpRight size={12} />
            </button>
          ))}
      </div>
    </article>
  );
}
