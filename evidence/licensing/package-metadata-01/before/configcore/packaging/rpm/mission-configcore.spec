# SPDX-License-Identifier: BSD-3-Clause
# SUSE source integration only; no native RPMDB takeover or service activation.
Name: mission-configcore
Version: 0.1.0
Release: 0.20260906.suseconfig%{?dist}
Summary: Mission Core configuration compatibility diagnostics and contracts
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
Read-only diagnostics and explicit integration interfaces. Exact SUSE build inputs
and GNAT toolchain must be qualified separately; this spec is not a certification.

%prep
%autosetup -n %{name}-%{version}

%build
make compile-all
make build

%check
make test

%install
install -d -m0755 %{buildroot}%{_libexecdir}/mission-core/configcore
install -p -m0755 build/bin/configctl %{buildroot}%{_libexecdir}/mission-core/configcore/configctl

%files
%license LICENSE
%doc README.md SECURITY.md docs/
%{_libexecdir}/mission-core/configcore/
