Name:           vanta
Version:        1.0.0
Release:        6%{?dist}
Summary:        Local competition tracker
License:        MIT
BuildArch:      noarch
Requires:       python3
Requires:       gtk3
Requires:       webkit2gtk4.1
Requires:       python3-gobject
Source0:        %{name}-%{version}.tar.gz

%description
Offline competition tracker with SQLite persistence and local reminders.

%prep
%setup -q

%install
mkdir -p %{buildroot}%{_datadir}/vanta %{buildroot}%{_bindir} %{buildroot}%{_datadir}/applications %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
cp -a . %{buildroot}%{_datadir}/vanta/
cat > %{buildroot}%{_bindir}/vanta <<EOF
#!/bin/sh
exec /usr/bin/python3 %{_datadir}/vanta/desktop.py "\$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/vanta
sed 's|Exec=.*|Exec=vanta|' packaging/vanta.desktop > %{buildroot}%{_datadir}/applications/vanta.desktop
cp public/vanta.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/vanta.svg

%files
%{_bindir}/vanta
%{_datadir}/vanta
%{_datadir}/applications/vanta.desktop
%{_datadir}/icons/hicolor/scalable/apps/vanta.svg

%changelog
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
