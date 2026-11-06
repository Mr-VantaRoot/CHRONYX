import {useState, type FormEvent} from 'react';
import {Check, X} from 'lucide-react';
import type {Event} from './types';
import {cats, priorityList, statusList} from './constants';
import {fromZone, inputInZone} from './view-utils';
type EditorProps = {initial: Event; close: () => void; save: (event: Event) => Promise<boolean>};
export function Editor({initial, close, save}: EditorProps) {
  const [e, setE] = useState<Event>({
      ...initial,
    }),
    [formError, setFormError] = useState('');
  const set = (k: keyof Event, v: string) =>
    setE({
      ...e,
      [k]: v,
    });
  function setLocalDate(k: 'start' | 'end' | 'deadline', value: string) {
    if (!value) {
      set(k, '');
      return;
    }
    const instant = fromZone(value, e.timezone);
    if (!instant) {
      setFormError(
        'That local time is invalid or does not exist because of a daylight-saving clock change. Choose a valid time.',
      );
      return;
    }
    setFormError('');
    set(k, instant);
  }
  function submit(ev: FormEvent) {
    ev.preventDefault();
    if (!e.name.trim() || !e.start) {
      setFormError('Competition name and start date are required.');
      return;
    }
    if (e.end && new Date(e.end) < new Date(e.start)) {
      setFormError('End date must be after start date.');
      return;
    }
    try {
      new Intl.DateTimeFormat('en', {
        timeZone: e.timezone,
      }).format(new Date());
    } catch {
      setFormError('Enter a valid IANA time zone, for example Africa/Nairobi.');
      return;
    }
    setFormError('');
    save(e);
  }
  return (
    <div className="scrim" onMouseDown={close}>
      <form className="editor" onSubmit={submit} onMouseDown={(e) => e.stopPropagation()}>
        <div className="editor-head">
          <div>
            <div className="eyebrow">COMPETITION DETAILS</div>
            <h2>{e.name ? 'Edit competition' : 'Add competition'}</h2>
          </div>
          <button type="button" className="icon-button" onClick={close}>
            <X size={18} />
          </button>
        </div>
        <div className="form-scroll">
          {formError && (
            <div className="form-error" role="alert">
              {formError}
            </div>
          )}
          <label>
            Competition name *
            <input
              required
              autoFocus
              value={e.name}
              onChange={(x) => set('name', x.target.value)}
              placeholder="e.g. DEF CON CTF"
            />
          </label>
          <label>
            Description
            <textarea
              rows={2}
              value={e.description}
              onChange={(x) => set('description', x.target.value)}
              placeholder="What is this competition about?"
            />
          </label>
          <div className="form-row">
            <label>
              Category
              <select value={e.category} onChange={(x) => set('category', x.target.value)}>
                {cats.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>
              Organisation
              <input
                value={e.organizer}
                onChange={(x) => set('organizer', x.target.value)}
                placeholder="Organizer name"
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              Start date & time *
              <input
                required
                type="datetime-local"
                value={inputInZone(e.start, e.timezone)}
                onChange={(x) => setLocalDate('start', x.target.value)}
              />
            </label>
            <label>
              End date & time
              <input
                type="datetime-local"
                value={inputInZone(e.end, e.timezone)}
                onChange={(x) => setLocalDate('end', x.target.value)}
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              Registration deadline
              <input
                type="datetime-local"
                value={inputInZone(e.deadline, e.timezone)}
                onChange={(x) => setLocalDate('deadline', x.target.value)}
              />
            </label>
            <label>
              Time zone
              <input
                value={e.timezone}
                onChange={(x) => set('timezone', x.target.value)}
                placeholder="Africa/Nairobi"
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              Registration status
              <select value={e.status} onChange={(x) => set('status', x.target.value)}>
                {statusList.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label>
              Priority
              <select value={e.priority} onChange={(x) => set('priority', x.target.value)}>
                {priorityList.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="form-row">
            <label>
              Competition website
              <input
                type="url"
                value={e.website}
                onChange={(x) => set('website', x.target.value)}
                placeholder="https://"
              />
            </label>
            <label>
              Registration URL
              <input
                type="url"
                value={e.registrationUrl}
                onChange={(x) => set('registrationUrl', x.target.value)}
                placeholder="https://"
              />
            </label>
          </div>
          <label>
            Personal notes
            <textarea
              rows={3}
              value={e.notes}
              onChange={(x) => set('notes', x.target.value)}
              placeholder="Notes, preparation reminders…"
            />
          </label>
        </div>
        <div className="editor-foot">
          <button type="button" className="outline-button" onClick={close}>
            Cancel
          </button>
          <button type="submit" className="add-button">
            <Check size={16} /> Save competition
          </button>
        </div>
      </form>
    </div>
  );
}
