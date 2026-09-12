# SPDX-License-Identifier: BSD-3-Clause
# SUSE/RPM integration source; rpmbuild and the resulting RPM are NOT qualified.
# Installation neither takes over native RPMDB nor provisions trust or starts services.
Name: mission-assurance
Version: 0.1.0
Release: 0.20260906.unified%{?dist}
Summary: Mission Core assurance independent tools and integration interfaces
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

%description
Independent Mission Core assurance tools. Source-level contracts and qualification
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
install -d -m0755 %{buildroot}%{_libexecdir}/mission-core/assurance
install -p -m0755 build/bin/assure %{buildroot}%{_libexecdir}/mission-core/assurance/assure
install -p -m0755 build/bin/controlctl %{buildroot}%{_libexecdir}/mission-core/assurance/controlctl
install -p -m0755 build/bin/platformctl %{buildroot}%{_libexecdir}/mission-core/assurance/platformctl

%files
%license LICENSE
%doc README.md SECURITY.md docs/
%{_libexecdir}/mission-core/assurance/

# Deliberately no %post, %preun, service presets, daemon reload or state removal.
# Opt-in unit activation must follow site review of identities, LSM policy and paths.
