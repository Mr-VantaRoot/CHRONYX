Name:           chronyx
Version:        1.0.0
Release:        9%{?dist}
Summary:        Local competition tracker
License:        MIT
BuildArch:      noarch
Requires:       python3
Requires:       gtk3
Requires:       webkit2gtk4.1
Requires:       python3-gobject
Requires:       libnotify
Requires:       tzdata
Source0:        %{name}-%{version}.tar.gz
Obsoletes:      vanta < 1.0.0-9
Provides:       vanta = %{version}-%{release}

%description
Offline competition tracker with SQLite persistence and local reminders.

%prep
%setup -q

%install
mkdir -p %{buildroot}%{_datadir}/chronyx/dist %{buildroot}%{_datadir}/chronyx/public %{buildroot}%{_bindir} %{buildroot}%{_datadir}/applications %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
install -m 0644 desktop.py server.py LICENSE %{buildroot}%{_datadir}/chronyx/
cp -a dist/. %{buildroot}%{_datadir}/chronyx/dist/
cp -a public/. %{buildroot}%{_datadir}/chronyx/public/
cat > %{buildroot}%{_bindir}/chronyx <<EOF
#!/bin/sh
exec /usr/bin/python3 %{_datadir}/chronyx/desktop.py "\$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/chronyx
cat > %{buildroot}%{_datadir}/applications/chronyx.desktop <<EOF
[Desktop Entry]
Name=CHRONYX Competition Tracker
Comment=Track competitions, deadlines and reminders
Exec=chronyx
Icon=chronyx
Terminal=false
Type=Application
Categories=Office;
StartupNotify=true
EOF
cp public/chronyx.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/chronyx.svg

%files
%{_bindir}/chronyx
%{_datadir}/chronyx/desktop.py
%{_datadir}/chronyx/server.py
%{_datadir}/chronyx/dist
%{_datadir}/chronyx/public
%license %{_datadir}/chronyx/LICENSE
%{_datadir}/applications/chronyx.desktop
%{_datadir}/icons/hicolor/scalable/apps/chronyx.svg

%changelog
* Fri Nov 06 2026 Mr-VantaRoot <Mr-VantaRoot@users.noreply.github.com> - 1.0.0-9
- Rename the application from VANTA to CHRONYX (package, command, desktop entry, icon)
- Replace the package "vanta" and copy existing competitions from the old data folder on first launch

* Thu Nov 05 2026 Mr-VantaRoot <Mr-VantaRoot@users.noreply.github.com> - 1.0.0-8
- Harden the local API and improve cross-platform desktop startup
- Add reminder catch-up and prune generated RPMs from source control

* Thu Nov 05 2026 VANTA Team <local@localhost> - 1.0.0-7
- Require libnotify for Fedora desktop reminders
- Add reminder delivery retries, API validation, and Windows uninstall support

* Thu Nov 05 2026 VANTA Team <local@localhost> - 1.0.0-6
- Add persistent device-local profile pictures

* Thu Nov 05 2026 VANTA Team <local@localhost> - 1.0.0-5
- Add Windows WebView2 launcher and per-user data location
- Add Windows toast notifications and cross-platform path tests

* Thu Nov 05 2026 VANTA Team <local@localhost> - 1.0.0-4
- Fix the eventCountdown scope error that blanked the WebKit window
- Rebuild the bundled assets from the corrected source
- Bypass stale WebKit cache for the application shell

* Thu Nov 05 2026 VANTA Team <local@localhost> - 1.0.0-3
- Ship the complete stylesheet so the interface renders correctly
- Fix the user-level launcher wrapper

* Thu Nov 05 2026 VANTA Team <local@localhost> - 1.0.0-2
- Initial local release
