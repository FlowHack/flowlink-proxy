Name:           flowlink-proxy
Version:        %{?version}%{!?version:0.3.0}
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

%install
mkdir -p %{buildroot}/usr/local/bin
mkdir -p %{buildroot}/usr/local/share/%{name}
mkdir -p %{buildroot}%{_datadir}/applications

install -m 755 flowlink-proxy %{buildroot}/usr/local/bin/flowlink-proxy

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
/usr/local/bin/flowlink-proxy
%{_datadir}/applications/flowlink-proxy.desktop

%changelog
* Sat Jul 13 2026 FlowLink Proxy <flowlink.proxy@atomicmail.io> - 0.3.0-1
- System autostart support
- Browser auto-detection
- Standalone binary with PyInstaller
