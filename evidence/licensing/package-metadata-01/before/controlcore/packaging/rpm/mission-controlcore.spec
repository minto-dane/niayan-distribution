# SPDX-License-Identifier: BSD-3-Clause
# Integration source; rpmbuild and this artifact have NOT been qualified.
Name: mission-controlcore
Version: 0.2.0
Release: 0.20260906.unified%{?dist}
Summary: Mission Core signed local workflow and recovery management
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
BuildRequires: python3
BuildRequires: libsodium-devel
BuildRequires: libarchive-devel
BuildRequires: libcurl-devel
BuildRequires: libxml2-devel

%description
Independent local workflow management with native receiver authorization.
No implicit daemon activation, key generation, host ownership migration or
production qualification. Site policy and signed plan provisioning are separate.

%prep
%autosetup -n %{name}-%{version}
%build
make compile-all
make build
%check
make test
%install
install -d -m0755 %{buildroot}%{_libexecdir}/mission-core/controlcore
install -p -m0755 build/bin/missionctl build/bin/mission_sign %{buildroot}%{_libexecdir}/mission-core/controlcore/
%files
%license LICENSE
%doc README.ja.md SECURITY.md docs/
%{_libexecdir}/mission-core/controlcore/
# No %post, auto-start, trust enrollment, privileged setup or state deletion.
