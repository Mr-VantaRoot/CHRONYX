export type Event = {
  id: string;
  name: string;
  description: string;
  category: string;
  organizer: string;
  website: string;
  registrationUrl: string;
  start: string;
  end: string;
  deadline: string;
  timezone: string;
  status: string;
  priority: string;
  notes: string;
  created: string;
};

export type ReminderPrefs = {
  '7d': boolean;
  '3d': boolean;
  '1d': boolean;
  '1h': boolean;
  customHours: number;
};

export type CalendarItem = {event: Event; kind: string; dayKey?: string};

export type SkippedRow = {index: number; reason: string; name?: string};

export type ImportReportData = {
  title: string;
  imported: number;
  skipped: SkippedRow[];
  message?: string;
};
