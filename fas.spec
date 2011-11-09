%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:           fas
Version:        0.8.8.92
Release:        1%{?dist}
Summary:        Fedora Account System

Group:          Development/Languages
License:        GPLv2
URL:            https://fedorahosted.org/fas/
Source0:        https://fedorahosted.org/releases/f/a/fas/%{name}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:      noarch
BuildRequires:  python2-devel
BuildRequires:  python-setuptools
BuildRequires:  TurboGears
BuildRequires:  gettext
Requires: TurboGears >= 1.0.4
Requires: python-sqlalchemy
Requires: python-TurboMail
Requires: python-fedora >= 0.3.25
Requires: babel
Requires: pygpgme
Requires: python-babel
Requires: python-genshi
Requires: python-kitchen
Requires: pytz
Requires: python-openid
Requires: python-GeoIP
Requires: pyOpenSSL
Requires: python-memcached
Requires: python-webob
Requires: tulrich-tuffy-fonts

%description
The Fedora Account System is a web application that manages the accounts of
Fedora Project Contributors.  It's built in TurboGears and comes with a json
API for querying against remotely.

The python-fedora-infrastructure package has a TurboGears identity provider
that works with the Account System.

%package clients
Summary: Clients for the Fedora Account System
Group: Applications/System
Requires: python-fedora >= 0.3.12.1
Requires: authconfig
Requires: nss_db
Requires: libselinux-python

%description clients
Additional scripts that work as clients to the accounts system.

%prep
%setup -q -n %{name}-%{version}


%build
%{__python} setup.py build --install-data='%{_datadir}'


%install
%{__rm} -rf %{buildroot}
%{__python} setup.py install --skip-build --install-data='%{_datadir}' --root %{buildroot}
%{__mkdir_p} %{buildroot}%{_sbindir}
%{__mkdir_p} %{buildroot}%{_sysconfdir}
%{__mv} %{buildroot}%{_bindir}/start-fas %{buildroot}%{_sbindir}
%{__install} fas.wsgi %{buildroot}%{_sbindir}
# Unreadable by others because it's going to contain a database password.
%{__install} -m 640 fas.cfg.sample %{buildroot}%{_sysconfdir}/fas.cfg
%{__install} -m 600 client/fas.conf %{buildroot}%{_sysconfdir}
%{__install} -m 700 -d %{buildroot}%{_localstatedir}/lib/fas

%{__install} -m 0755 scripts/export-bugzilla.py %{buildroot}%{_sbindir}/export-bugzilla
%{__install} -m 0600 scripts/export-bugzilla.cfg %{buildroot}%{_sysconfdir}/

%{__install} -m 0755 scripts/account-expiry.py %{buildroot}%{_sbindir}/account-expiry
%{__install} -m 0600 scripts/account-expiry.cfg %{buildroot}%{_sysconfdir}/

cp -pr updates/ %{buildroot}%{_datadir}/fas

%find_lang %{name}

%clean
%{__rm} -rf %{buildroot}


%pre
/usr/sbin/useradd -c 'Fedora Account System user' -s /sbin/nologin \
    -r -M -d %{_datadir}/fas fas &> /dev/null || :


%files -f %{name}.lang
%defattr(-,root,root,-)
%doc README TODO COPYING NEWS fas2.sql fas.spec fas.conf.wsgi
%{python_sitelib}/*
%{_datadir}/fas/
%{_sbindir}/start-fas
%{_sbindir}/fas.wsgi
%{_sbindir}/export-bugzilla
%{_sbindir}/account-expiry
%attr(-,root,fas) %config(noreplace) %{_sysconfdir}/fas.cfg
%attr(-,root,fas) %config(noreplace) %{_sysconfdir}/export-bugzilla.cfg
%attr(-,root,fas) %config(noreplace) %{_sysconfdir}/account-expiry.cfg

%files clients
%defattr(-,root,root,-)
%{_bindir}/*
%config(noreplace) %{_sysconfdir}/fas.conf
%attr(0700,root,root) %dir %{_localstatedir}/lib/fas

%changelog
* Thu Oct 27 2011 Toshio Kuratomi <toshio@fedoraproject.org> - 0.8.8.92-1
- Going to to daily new rpms until release so translators can see their work.

* Thu Oct 27 2011 Toshio Kuratomi <toshio@fedoraproject.org> - 0.8.8.91-1
- Second beta

* Thu Oct 27 2011 Toshio Kuratomi <toshio@fedoraproject.org> - 0.8.8.90-1
- Beta of the 0.8.9 release.

* Mon May 2 2011 Toshio Kuratomi <toshio@fedoraproject.org> - 0.8.8-1
- Final release

* Tue Apr 5 2011 Toshio Kuratomi <toshio@fedoraproject.org> - 0.8.8-0.1.a1
- Update for FPCA
- Move fas.wsgi into /usr/sbin
- Include the updates directory in the package
- Make the apache configfile %%doc instead of installing it

* Mon Feb 07 2011 Jim Lieb <lieb@sea-troll.net> - 0.8.7.5-1.1
- Localize UI to Yahoo.
- Make wsgi instantiation work

* Fri Sep 24 2010 Mike McGrath <mmcgrath@redhat.com> - 0.8.7.5-1
- Upstream released new version

* Thu Sep 09 2010 Mike McGrath <mmcgrath@redhat.com> - 0.8.7.4-1
- Upstream released new version

* Fri Aug 27 2010 Mike McGrath <mmcgrath@redhat.com> - 0.8.7.3-1
- Upstream released new version

* Tue Aug 10 2010 Mike McGrath <mmcgrath@redhat.com> - 0.8.7.1-1
- New upstream release
- Removed python-webob dep (was a false dep anyway)

* Mon Aug 09 2010 Mike McGrath <mmcgrath@redhat.com> - 0.8.7-1
- New upstream release

* Fri Jul 30 2010 Jon Stanley <jstanley@fedoraproject.org> - 0.8.6.2.6-1
- New upstream release

* Thu Jul 29 2010 Jon Stanley <jstanley@fedoraproject.org> - 0.8.6.2.5-2
- Fix fas.cfg=>fas.cfg.sample rename upstream

* Thu Jul 29 2010 Jon Stanley - 0.8.6.2.5-1
- New upstream release
- Now conflicts with python-sqlalchemy, and requires python-sqlalchemy0.5

* Wed Sep 16 2009 Toshio Kuratomi <toshio@fedoraproject.org> - 0.8.6.2.3-1
- New release that implements a captcha for new accounts and fixes a few
  bugs.

* Tue Jun 11 2009 Ricky Zhou <ricky@fedoraproject.org> - 0.8.6.2.2-1
- Add Requires on python-memcached.
- Fix /var/lib/fas directory.
- Some export-bugzilla fixes.

* Tue Jun  6 2009 Ricky Zhou <ricky@fedoraproject.org> - 0.8.6.2.1-1
- Typo fix release.

* Tue Jun  4 2009 Ricky Zhou <ricky@fedoraproject.org> - 0.8.6.2-1
- Upstream released a new version.

* Tue Jun  3 2009 Ricky Zhou <ricky@fedoraproject.org> - 0.8.6.1-1
- Upstream released a new version.

* Tue Jun  2 2009 Mike McGrath <mmcgrath@fedoraproject.org> - 0.8.6-1
- Upstream released new version
- Cached group/user data

* Sun Apr 12 2009 Ricky Zhou <ricky@fedoraproject.org> - 0.8.5.2-3
- Fix fas user's home directory (was missing a slash).

* Thu Mar 13 2009 Ricky Zhou <ricky@fedoraproject.org> - 0.8.5.2-2
- Add /var/lib/fas directory.

* Thu Mar 12 2009 Toshio Kuratomi <toshio@fedoraproject.org> - 0.8.5.2-1
- Bugfix for fasClient alias generation and template fixes for the csrf token.

* Mon Mar 9 2009 Toshio Kuratomi <toshio@fedoraproject.org> - 0.8.5.1-1
- Quick little bugfix for using the login method via json.

* Sat Mar 7 2009 Toshio Kuratomi <toshio@fedoraproject.org> - 0.8.5-1
- Beta new upstream release with CSRF fixes.

* Thu Feb 12 2009 Ricky Zhou <ricky@fedoraproject.org> - 0.8.4.8-1
- New upstream release that fixes some security issues.
