import {Activity, AlarmClock, ArrowUpRight, CalendarDays, Clock3, Flag, Grid2X2, Plus, Target} from 'lucide-react';
import type {Event} from './types';
import {EventCard} from './EventCard';
import {Stat} from './Stat';
import {fmt} from './view-utils';
import {countdown} from './time.js';
type DashboardProps = {
  events: Event[];
  active: Event[];
  next?: Event;
  tick: number;
  open: (event?: Event) => void;
  setView: (view: string) => void;
  menu: string;
  setMenu: (id: string) => void;
  remove: (id: string) => void;
  complete: (event: Event) => void;
  notify: (message: string) => void;
};
export function Dashboard({
  events,
  active,
  next,
  tick,
  open,
  setView,
  menu,
  setMenu,
  remove,
  complete,
  notify,
}: DashboardProps) {
  return (
    <>
      <section className="stats">
        <Stat icon={<Grid2X2 />} label="TOTAL EVENTS" value={events.length} note="Across all categories" />
        <Stat
          icon={<ArrowUpRight />}
          label="UPCOMING"
          value={active.filter((e) => new Date(e.start) > new Date()).length}
          note="On your calendar"
        />
        <Stat
          icon={<AlarmClock />}
          label="DEADLINES · 7 DAYS"
          value={
            active.filter(
              (e) =>
                e.deadline &&
                new Date(e.deadline) > new Date() &&
                new Date(e.deadline) < new Date(Date.now() + 7 * 864e5),
            ).length
          }
          note="Registration closing"
        />
        <Stat
          icon={<Target />}
          label="IN PROGRESS"
          value={events.filter((e) => e.status === 'Participating').length}
          note={`${events.filter((e) => e.status === 'Completed').length} completed`}
        />
      </section>
      {next ? (
        <section className="featured">
          <div className="featured-top">
            <span className="section-tag">
              <span className="live-dot" /> NEXT UP
            </span>
            <span className={`priority ${next.priority.toLowerCase()}`}>{next.priority} priority</span>
          </div>
          <div className="featured-row">
            <div className="featured-info">
              <div className="category-line">
                <span className="category-dot" /> {next.category} <span className="separator">/</span>{' '}
                {next.organizer || 'Independent event'}
              </div>
              <h2>{next.name}</h2>
              <p>{next.description || 'Your next competition is on the horizon. Keep preparing.'}</p>
              <div className="featured-meta">
                <span>
                  <CalendarDays size={15} />
                  {fmt(next.start, {
                    weekday: 'short',
                    month: 'short',
                    day: 'numeric',
                    timeZone: next.timezone,
                  })}
                </span>
                <span>
                  <Clock3 size={15} />
                  {fmt(next.start, {
                    hour: '2-digit',
                    minute: '2-digit',
                    timeZone: next.timezone,
                  })}{' '}
                  · {next.timezone}
                </span>
                <span>
                  <Flag size={15} />
                  {next.status}
                </span>
              </div>
            </div>
            <div className="countdown">
              <div className="count-label">STARTS IN</div>
              <strong>{countdown(next.start, tick)}</strong>
              <button onClick={() => open(next)}>
                View event <ArrowUpRight size={14} />
              </button>
            </div>
          </div>
          <div className="featured-line">
            <span
              style={{
                width: `${Math.max(4, Math.min(100, 100 - ((new Date(next.start).getTime() - tick) / (30 * 864e5)) * 100))}%`,
              }}
            />
          </div>
        </section>
      ) : (
        <section className="featured empty-feature">
          <div>
            <span className="section-tag">ALL CLEAR</span>
            <h2>No upcoming competitions yet</h2>
            <p>Add your next opportunity and VANTA will keep the countdown.</p>
          </div>
          <button className="add-button" onClick={() => open()}>
            <Plus size={16} /> Add competition
          </button>
        </section>
      )}
      <div className="section-head">
        <div>
          <h2>Coming up</h2>
          <p>Your next events at a glance</p>
        </div>
        <button className="text-button" onClick={() => setView('Upcoming')}>
          View all <ArrowUpRight size={14} />
        </button>
      </div>
      <div className="event-grid">
        {active
          .filter((e) => new Date(e.start) > new Date())
          .slice(0, 3)
          .map((e) => (
            <EventCard
              key={e.id}
              e={e}
              open={() => open(e)}
              menu={menu}
              setMenu={setMenu}
              remove={remove}
              complete={complete}
              notify={notify}
            />
          ))}
        {!active.some((e) => new Date(e.start) > new Date()) && (
          <div className="empty-card">
            <CalendarDays size={22} />
            <b>Your schedule is open</b>
            <span>New opportunities will show up here.</span>
            <button className="text-button" onClick={() => open()}>
              Add your first competition <Plus size={14} />
            </button>
          </div>
        )}
      </div>
      <div className="section-head activity-head">
        <div>
          <h2>Recent activity</h2>
          <p>Your latest competition updates</p>
        </div>
        <span className="muted">{events.length} events tracked</span>
      </div>
      <div className="activity-list">
        {[...events]
          .sort((a, b) => b.created.localeCompare(a.created))
          .slice(0, 4)
          .map((e) => (
            <div className="activity-row" key={e.id}>
              <div className="activity-icon">
                <Activity size={15} />
              </div>
              <div>
                <b>
                  {e.status === 'Completed' ? 'Completed' : 'Added'} <strong>{e.name}</strong>
                </b>
                <small>
                  {e.category} ·{' '}
                  {fmt(e.created, {
                    month: 'short',
                    day: 'numeric',
                  })}
                </small>
              </div>
              <span className={`status ${e.status.toLowerCase().replaceAll(' ', '-')}`}>{e.status}</span>
            </div>
          ))}
        {!events.length && (
          <div className="activity-empty">Recent additions and completed events will appear here.</div>
        )}
      </div>
    </>
  );
}
