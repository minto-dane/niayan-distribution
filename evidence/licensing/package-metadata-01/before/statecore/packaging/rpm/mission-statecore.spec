# SPDX-License-Identifier: BSD-3-Clause
# SUSE/RPM integration source; rpmbuild and the resulting RPM are NOT qualified.
# Installation neither takes over native RPMDB nor provisions trust or starts services.
Name: mission-statecore
Version: 0.1.0
Release: 0.20260906.unified%{?dist}
Summary: Mission Core statecore independent tools and integration interfaces
License: MIT
Source0: %{name}-%{version}.tar.gz
ExclusiveArch: x86_64
%if 0%{?suse_version}
BuildRequires: gcc-ada
%else
BuildRequires: gcc-gnat
%endif
BuildRequires: gprbuild
BuildRequires: make
BuildRequires: libsodium-devel
BuildRequires: libarchive-devel
BuildRequires: libcurl-devel
BuildRequires: libxml2-devel
BuildRequires: systemd-rpm-macros
Requires: systemd

%description
Independent Mission Core statecore tools. Source-level contracts and qualification
interfaces are included in the project; this build is not a production qualification.
No automatic host ownership migration, network change, key enrollment or activation.

%prep
%autosetup -n %{name}-%{version}

%build
make compile-all
make build

%check
make test

%install
install -d -m0755 %{buildroot}%{_libexecdir}/mission-core/statecore
install -p -m0755 build/bin/statectl %{buildroot}%{_libexecdir}/mission-core/statecore/statectl
install -p -m0755 build/bin/state_worker %{buildroot}%{_libexecdir}/mission-core/statecore/state_worker
install -p -m0755 build/bin/state_recovery_worker %{buildroot}%{_libexecdir}/mission-core/statecore/state_recovery_worker
install -p -m0755 build/bin/state_healing_admin %{buildroot}%{_libexecdir}/mission-core/statecore/state_healing_admin
install -D -p -m0755 build/bin/hostctl %{buildroot}%{_bindir}/mc-hostctl
install -D -p -m0644 deploy/systemd/mission-host-observer.service %{buildroot}%{_unitdir}/mission-host-observer.service
install -D -p -m0644 deploy/systemd/mission-host-observer.timer %{buildroot}%{_unitdir}/mission-host-observer.timer

%files
%license LICENSE
%doc README.md SECURITY.md docs/
%{_libexecdir}/mission-core/statecore/
%{_bindir}/mc-hostctl
%{_unitdir}/mission-host-observer.service
%{_unitdir}/mission-host-observer.timer

# Deliberately no %post, %preun, service presets, daemon reload or state removal.
# Opt-in unit activation must follow site review of identities, LSM policy and paths.
