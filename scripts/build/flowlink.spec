Name:           FlowLink-Proxy
Version:        %{?version}%{!?version:0.1.0}
Release:        1%{?dist}
Summary:        FlowLink Proxy — шлюз для маршрутизации трафика
License:        AGPLv3
URL:            https://github.com/FlowHack/flowlink-proxy
Source0:        %{name}-%{version}.tar.gz

%description
FlowLink Proxy — Python proxy-gateway с Chrome-расширением
для маршрутизации трафика через SOCKS5 прокси с масками.

%prep
%setup -q

%build
# Бинарник уже собран, сборка не требуется

# Отключение brp-strip-* скриптов: бинарник "FlowLink Proxy" содержит пробел,
# который ломает парсинг в стандартных brp-скриптах RPM.
%global __brp_strip %{nil}
%global __brp_strip_static_archive %{nil}
%global __brp_strip_comment_note %{nil}

%install
mkdir -p %{buildroot}/usr/local/bin
mkdir -p %{buildroot}/usr/local/share/%{name}
mkdir -p %{buildroot}%{_datadir}/applications

install -m 755 "FlowLink Proxy" "%{buildroot}/usr/local/bin/FlowLink Proxy"

for doc in EULA.rtf LICENSE.txt; do
    if [ -f "$doc" ]; then
        install -m 644 "$doc" %{buildroot}/usr/local/share/%{name}/"$doc"
    fi
done

if [ -f flowlink.desktop ]; then
    install -m 644 flowlink.desktop %{buildroot}%{_datadir}/applications/flowlink-proxy.desktop
fi

%files
%license LICENSE.txt
%doc EULA.rtf
"/usr/local/bin/FlowLink Proxy"
/usr/local/share/%{name}
%{_datadir}/applications/flowlink-proxy.desktop

%changelog
* Mon Aug 10 2026 FlowLink Proxy <flowlink.proxy@atomicmail.io> - 0.1.0-1
- System autostart support
- Browser auto-detection
- Standalone binary with PyInstaller
