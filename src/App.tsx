import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {
  AlarmClock,
  ArrowDownWideNarrow,
  Bell,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  Clock3,
  Download,
  Filter,
  LayoutDashboard,
  List,
  Plus,
  Search,
  Settings,
  Shield,
  Sun,
  Trash2,
  Trophy,
  type LucideIcon,
} from 'lucide-react';

import {loadEvents, saveEvent, deleteEvent, importEvents} from './event-store.js';
import {validateImportFile} from './import-export.js';
import {matchesEventFilters} from './filter-model.js';
import type {Event, ImportReportData, SkippedRow} from './types';
import {cats, priorityList, statusList} from './constants';

import {EventCard} from './EventCard';
import {Dashboard} from './Dashboard';
import {Editor} from './Editor';
import {CalendarPage} from './CalendarPage';
import {RemindersPage} from './RemindersPage';
import {SettingsPage} from './SettingsPage';

const blank = (): Event => ({
  id: crypto.randomUUID(),
  name: '',
  description: '',
  category: 'CTF',
  organizer: '',
  website: '',
  registrationUrl: '',
  start: '',
  end: '',
  deadline: '',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  status: 'Interested',
  priority: 'Medium',
  notes: '',
  created: new Date().toISOString(),
});
function readLocal(key: string, fallback = '') {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}
const navItems: [LucideIcon, string][] = [
  [LayoutDashboard, 'Dashboard'],
  [List, 'All Competitions'],
  [Bell, 'Reminders'],
  [CalendarDays, 'Calendar'],
  [Clock3, 'Upcoming'],
  [AlarmClock, 'Registration Deadlines'],
  [Trophy, 'Completed'],
];
function App() {
  const [events, setEvents] = useState<Event[]>([]),
    [notice, setNotice] = useState(''),
    inFlight = useRef(false),
    [view, setView] = useState('Dashboard'),
    [modal, setModal] = useState(false),
    [edit, setEdit] = useState<Event | null>(null),
    [query, setQuery] = useState(''),
    [filter, setFilter] = useState('All'),
    [filterStatus, setFilterStatus] = useState('All'),
    [filterPriority, setFilterPriority] = useState('All'),
    [sortBy, setSortBy] = useState('start'),
    [theme, setTheme] = useState(readLocal('theme', 'dark')),
    [profilePicture, setProfilePicture] = useState(readLocal('chronyxProfilePicture')),
    [tick, setTick] = useState(Date.now()),
    [month, setMonth] = useState(new Date()),
    [menu, setMenu] = useState(''),
    searchRef = useRef<HTMLInputElement | null>(null),
    [deleteTarget, setDeleteTarget] = useState<Event | null>(null),
    [importReport, setImportReport] = useState<ImportReportData | null>(null),
    [discardNotice, setDiscardNotice] = useState('');
  const refresh = useCallback(async () => {
    try {
      const result = await loadEvents();
      setEvents(result.events);
      if (result.rejected?.length) {
        const count = result.rejected.length;
        setDiscardNotice(
          `${count} offline change${count === 1 ? ' was' : 's were'} rejected by the local service and discarded: ` +
            result.rejected.map((item) => `${item.name} (${item.reason})`).join('; '),
        );
      }
      setNotice(
        result.syncError
          ? `Some offline changes are still pending: ${result.syncError}`
          : result.offline
            ? 'Service unavailable. Changes are being saved on this device and will sync when it returns.'
            : '',
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not load competitions.');
    }
  }, []);
  useEffect(() => {
    refresh();
    const t = setInterval(() => setTick(Date.now()), 1000);
    const h = setInterval(refresh, 15000);
    return () => {
      clearInterval(t);
      clearInterval(h);
    };
  }, [refresh]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem('theme', theme);
    } catch {
      // Storage can be unavailable; the theme still applies for this session.
    }
  }, [theme]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
  const active = events.filter((e) => !['Completed', 'Cancelled'].includes(e.status));
  const next = active
    .filter((e) => new Date(e.start) > new Date())
    .sort((a, b) => +new Date(a.start) - +new Date(b.start))[0];
  const shown = useMemo(
    () =>
      events
        .filter(
          (e) =>
            (view === 'Completed'
              ? e.status === 'Completed'
              : view === 'Upcoming'
                ? new Date(e.start) > new Date()
                : view === 'Registration Deadlines'
                  ? e.deadline &&
                    new Date(e.deadline) > new Date() &&
                    new Date(e.deadline) < new Date(Date.now() + 7 * 864e5)
                  : true) &&
            (!query || `${e.name} ${e.category} ${e.organizer}`.toLowerCase().includes(query.toLowerCase())) &&
            matchesEventFilters(e, {category: filter, status: filterStatus, priority: filterPriority}),
        )
        .sort(
          (a, b) =>
            +new Date(sortBy === 'deadline' ? a.deadline || a.start : a.start) -
            +new Date(sortBy === 'deadline' ? b.deadline || b.start : b.start),
        ),
    [events, view, query, filter, filterStatus, filterPriority, sortBy],
  );
  async function save(e: Event) {
    if (inFlight.current) return false;
    inFlight.current = true;
    try {
      const result = await saveEvent(
        e,
        events.some((x) => x.id === e.id),
      );
      setEvents(result.events);
      setNotice(
        result.offline
          ? 'Service unavailable. This change is saved locally and will sync when the service returns.'
          : '',
      );
      setModal(false);
      setEdit(null);
      return true;
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not save competition.');
      return false;
    } finally {
      inFlight.current = false;
    }
  }
  function remove(id: string) {
    setDeleteTarget(events.find((e) => e.id === id) || null);
  }
  async function confirmRemove() {
    if (!deleteTarget || inFlight.current) return;
    inFlight.current = true;
    try {
      const result = await deleteEvent(deleteTarget.id);
      setEvents(result.events);
      setNotice(
        result.offline
          ? 'Service unavailable. This deletion is queued locally and will sync when the service returns.'
          : '',
      );
      setDeleteTarget(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not delete competition.');
    } finally {
      inFlight.current = false;
    }
  }
  async function complete(e: Event) {
    await save({
      ...e,
      status: 'Completed',
    });
  }
  function open(e?: Event) {
    setEdit(e || blank());
    setModal(true);
  }
  async function exportData(kind: 'json' | 'csv') {
    const anchor = document.createElement('a');
    anchor.href = `/api/export.${kind}`;
    anchor.download = `chronyx-competitions.${kind}`;
    anchor.style.display = 'none';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }
  async function importJSON(file: File) {
    try {
      if (file.size > 4 * 1024 * 1024) throw new Error('Import file exceeds the 4 MB limit.');
      const parsed = JSON.parse(await file.text());
      const {valid, skipped: localSkipped} = validateImportFile(parsed);
      const result = await importEvents(
        valid.map((row) => row.event),
        valid.map((row) => row.index),
      );
      const byIndex = new Map<number, SkippedRow>(localSkipped.map((row: SkippedRow) => [row.index, row]));
      for (const item of result.skipped) byIndex.set(item.index, item);
      const skipped = [...byIndex.values()].sort((a, b) => a.index - b.index);
      await refresh();
      setImportReport({
        title: 'Import complete',
        imported: result.imported,
        skipped,
      });
    } catch (error) {
      setImportReport({
        title: 'Import failed',
        imported: 0,
        skipped: [],
        message: error instanceof Error ? error.message : 'The JSON file could not be imported.',
      });
    }
  }
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Shield size={19} />
          </div>
          <div>
            <b>CHRONYX</b>
            <small>COMPETITION TRACKER</small>
          </div>
        </div>
        <div className="side-label">WORKSPACE</div>
        <nav>
          {navItems.map(([Icon, label]) => (
            <button
              key={label}
              className={`nav-item ${view === label ? 'selected' : ''}`}
              onClick={() => setView(label)}
            >
              <Icon size={17} />
              <span>{label}</span>
              {label === 'Upcoming' && <i>{active.filter((e) => new Date(e.start) > new Date()).length}</i>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button className={`nav-item ${view === 'Settings' ? 'selected' : ''}`} onClick={() => setView('Settings')}>
            <Settings size={17} />
            Settings
          </button>
          <div className="profile">
            <div className="avatar">{profilePicture ? <img src={profilePicture} alt="Profile" /> : 'V'}</div>
            <div>
              <b>My workspace</b>
              <small>Local · private</small>
            </div>
          </div>
        </div>
      </aside>
      <main>
        <header>
          <div className="crumb">
            <span>Workspace</span>
            <ChevronRight size={14} />
            <b>{view}</b>
          </div>
          <div className="header-actions">
            <label className="search">
              <Search size={16} />
              <input
                ref={searchRef}
                placeholder="Search competitions…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <kbd>⌘ K</kbd>
            </label>
            <button
              className="icon-button"
              title="Toggle theme"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            >
              <Sun size={17} />
            </button>
            <button className="add-button" onClick={() => open()}>
              <Plus size={16} /> Add competition
            </button>
          </div>
        </header>
        <div className="content">
          {discardNotice && (
            <div className="notice" role="alert">
              {discardNotice}{' '}
              <button className="text-button" onClick={() => setDiscardNotice('')}>
                Dismiss
              </button>
            </div>
          )}
          {notice && (
            <div className="notice" role="status">
              {notice}
            </div>
          )}
          {view === 'Settings' ? (
            <SettingsPage
              theme={theme}
              setTheme={setTheme}
              profilePicture={profilePicture}
              setProfilePicture={setProfilePicture}
              setNotice={setNotice}
              exportData={exportData}
              importJSON={importJSON}
            />
          ) : view === 'Reminders' ? (
            <RemindersPage events={events} now={tick} open={open} openSettings={() => setView('Settings')} />
          ) : view === 'Calendar' ? (
            <CalendarPage events={events} month={month} setMonth={setMonth} open={open} />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    <span className="live-dot" /> YOUR COMPETITION COMMAND CENTER
                  </div>
                  <h1>{view === 'Dashboard' ? 'Good to have you back.' : view}</h1>
                  <p>
                    {view === 'Dashboard'
                      ? 'Every deadline, start time and opportunity—kept in view.'
                      : `Track and manage your ${view.toLowerCase()} opportunities.`}
                  </p>
                </div>
                <button className="outline-button" onClick={() => exportData('json')}>
                  <Download size={15} /> Export
                </button>
              </div>
              {view === 'Dashboard' && (
                <Dashboard
                  events={events}
                  active={active}
                  next={next}
                  tick={tick}
                  open={open}
                  setView={setView}
                  menu={menu}
                  setMenu={setMenu}
                  remove={remove}
                  complete={complete}
                  notify={setNotice}
                />
              )}
              {view !== 'Dashboard' && (
                <>
                  <div className="list-toolbar">
                    <div className="filters">
                      <div className="filter-select">
                        <Filter size={15} />
                        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
                          <option value="All">All categories</option>
                          {cats.map((x) => (
                            <option key={x} value={x}>
                              {x}
                            </option>
                          ))}
                        </select>
                        <ChevronDown size={13} />
                      </div>
                      <div className="filter-select">
                        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
                          <option value="All">All statuses</option>
                          {statusList.map((x) => (
                            <option key={x} value={x}>
                              {x}
                            </option>
                          ))}
                        </select>
                        <ChevronDown size={13} />
                      </div>
                      <div className="filter-select">
                        <select value={filterPriority} onChange={(e) => setFilterPriority(e.target.value)}>
                          <option value="All">All priorities</option>
                          {priorityList.map((x) => (
                            <option key={x} value={x}>
                              {x}
                            </option>
                          ))}
                        </select>
                        <ChevronDown size={13} />
                      </div>
                      <div className="filter-select">
                        <ArrowDownWideNarrow size={14} />
                        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                          <option value="start">Nearest start</option>
                          <option value="deadline">Registration deadline</option>
                        </select>
                        <ChevronDown size={13} />
                      </div>
                    </div>
                    <span>{shown.length} competitions</span>
                  </div>
                  <div className="event-grid">
                    {shown.map((e) => (
                      <EventCard
                        key={e.id}
                        e={e}
                        open={() => open(e)}
                        menu={menu}
                        setMenu={setMenu}
                        remove={remove}
                        complete={complete}
                        notify={setNotice}
                      />
                    ))}
                    {!shown.length && (
                      <div className="empty-card">
                        <CalendarDays size={22} />
                        <b>No competitions found</b>
                        <span>Try another search or add a competition.</span>
                        <button className="text-button" onClick={() => open()}>
                          Add competition <Plus size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </main>
      {modal && edit && (
        <Editor
          initial={edit}
          close={() => {
            setModal(false);
            setEdit(null);
          }}
          save={save}
        />
      )}
      {deleteTarget && (
        <ConfirmDelete event={deleteTarget} cancel={() => setDeleteTarget(null)} confirm={confirmRemove} />
      )}
      {importReport && <ImportReport report={importReport} close={() => setImportReport(null)} />}
    </div>
  );
}
function ConfirmDelete({event, cancel, confirm}: {event: Event; cancel: () => void; confirm: () => void}) {
  return (
    <div className="scrim modal-layer" onMouseDown={cancel}>
      <section
        className="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-title"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="eyebrow">PERMANENT ACTION</div>
        <h2 id="delete-title">Delete competition?</h2>
        <p>“{event.name}” will be removed from this device. This cannot be undone.</p>
        <div className="editor-foot">
          <button className="outline-button" onClick={cancel}>
            Keep competition
          </button>
          <button className="danger-button" onClick={confirm}>
            <Trash2 size={15} /> Delete permanently
          </button>
        </div>
      </section>
    </div>
  );
}
function ImportReport({report, close}: {report: ImportReportData; close: () => void}) {
  return (
    <div className="scrim modal-layer" onMouseDown={close}>
      <section
        className="confirm-dialog import-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-title"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="eyebrow">DATA & BACKUP</div>
        <h2 id="import-title">{report.title}</h2>
        {report.message ? (
          <p role="alert">{report.message}</p>
        ) : (
          <>
            <p>
              Imported {report.imported} competition{report.imported === 1 ? '' : 's'}
              {report.skipped.length ? `; skipped ${report.skipped.length}.` : '.'}
            </p>
            {report.skipped.length > 0 && (
              <ul>
                {report.skipped.map((item) => (
                  <li key={`${item.index}:${item.reason}`}>
                    Entry {item.index + 1}
                    {item.name ? ` (“${item.name}”)` : ''}: {item.reason}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
        <div className="editor-foot">
          <button className="add-button" onClick={close}>
            Done
          </button>
        </div>
      </section>
    </div>
  );
}
export default App;
