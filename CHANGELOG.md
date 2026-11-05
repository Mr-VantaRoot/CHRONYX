# Changelog

Notable user-facing changes are recorded here.

## 1.0.0-8 — 2026-11-05

- Deliver the RPM through GitHub Releases with SHA-256 checksums instead of committing package binaries.
- Package only the desktop launcher, server, compiled frontend, public assets, and license.
- Add calendar deadline markers, multi-day event spans, searchable website links, and tested deadline countdowns.
- Add missed-reminder catch-up and prune stale notification records.
- Harden localhost Host/Origin checks, request handling, and static file serving.
- Fix queued event upserts and import/export reporting; guard CSV formula cells.
- Split the React interface into feature components and prevent duplicate Windows desktop instances.
- Add regression tests for filters, deadlines, calendar markers, imports, and desktop instance ownership.

## 1.0.0-7 — 2026-11-05

- Add retryable notification delivery and local API validation.
- Add Windows uninstall support and Fedora notification dependencies.

## 1.0.0-6 — 2026-11-05

- Add device-local profile picture support.

## 1.0.0-5 — 2026-11-05

- Add the Windows WebView2 launcher, user data path, and toast notifications.

## 1.0.0-4 — 2026-11-05

- Fix the event countdown scope issue that blanked the embedded view.
- Rebuild bundled frontend assets and bypass stale WebKit cache.

## 1.0.0-3 — 2026-11-05

- Ship the full stylesheet and correct the user-level launcher wrapper.

## 1.0.0-2 — 2026-11-05

- Initial local release with SQLite persistence and desktop reminders.
