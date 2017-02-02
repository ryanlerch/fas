# -*- coding: utf-8 -*-
#
# Copyright © 2014-2016 Xavier Lamien.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# __author__ = 'Xavier Lamien <laxathom@fedoraproject.org>'


from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest
from fas.forms.account import AccountPermissionForm, TrustedPermissionForm
from fas.models.la import LicenseAgreementStatus
from fas.models.group import GroupStatus
from fas.models.people import AccountStatus, AccountPermissionType
from fas.forms.people import ContactInfosForm
from fas.forms.group import EditGroupTypeForm
from fas.forms.group import GroupListForm, GroupTypeListForm
from fas.forms.la import EditLicenseForm, SignLicenseForm, LicenseListForm
from fas.forms.certificates import EditCertificateForm
from fas.forms.certificates import CreateClientCertificateForm
from fas.events import GroupRemovalRequested, GroupCreated, GroupDeleted
from fas.events import GroupTypeRemovalRequested
from fas.events import LicenseRemovalRequested
from fas.security import generate_token
from fas.views import redirect_to
from fas.lib.captcha import Captcha
from fas.util import Config, setup_group_form
from fas.lib.certificatemanager import CertificateManager
from fas.events import NewClientCertificateCreated
from cryptography.fernet import Fernet

import fas.models.provider as provider
import fas.models.register as register
import logging

log = logging.getLogger(__name__)


class Admin(object):
    def __init__(self, request):
        self.request = request
        self.notify = self.request.registry.notify
        self.id = -1
        self.status = 'error'
        self.msg = 'Unable to process your request'

    @view_config(route_name='settings', permission='admin',
                 renderer='/admin/panel.xhtml')
    def index(self):
        """ Admin panel page."""
        people = provider.get_people(count=True)
        groups = provider.get_groups(count=True)
        licenses = len(provider.get_licenses())
        trusted_apps = len(provider.get_trusted_perms())

        group_form = GroupListForm(self.request.POST)
        grouptype_form = GroupTypeListForm(self.request.POST)
        license_form = LicenseListForm(self.request.POST)
        token_form = AccountPermissionForm(self.request.POST)
        trustedperm_form = TrustedPermissionForm(self.request.POST)

        group_form.id.choices = [
            (group.id, group.name) for group in provider.get_groups()]

        grouptype_form.id.choices = [
            (gt.id, gt.name) for gt in provider.get_group_types()
            ]

        license_form.id.choices = [
            (la.id, la.name) for la in provider.get_licenses()
            ]

        trustedperm_form.id.choices = [
            (tp.id, tp.application) for tp in provider.get_trusted_perms()
            ]

        if self.request.method == 'POST':
            key = None
            if ('form.remove.group' in self.request.params) \
                    and group_form.validate():
                key = group_form.id.data
                self.notify(GroupRemovalRequested(self.request, key))
                register.remove_group(key)

            if ('form.remove.grouptype' in self.request.params) \
                    and grouptype_form.validate():
                key = grouptype_form.id.data
                self.notify(GroupTypeRemovalRequested(self.request, key))
                register.remove_grouptype(key)

            if ('form.remove.license' in self.request.params) \
                    and license_form.validate():
                key = license_form.id.data
                self.notify(LicenseRemovalRequested(self.request, key))
                register.remove_license(key)
            if ('form.generate.key' in self.request.params) \
                    and token_form.validate():
                token = generate_token()
                secret = Fernet.generate_key()
                register.add_token(
                    description=token_form.desc.data,
                    permission=token_form.perm.data,
                    token=token,
                    trusted=True,
                    secret=secret)
                self.request.session.flash(token, 'tokens')
                self.request.session.flash(secret, 'secret')
            if ('form.revoke.token' in self.request.params) \
                    and trustedperm_form.validate():
                register.remove_trusted_token(trustedperm_form.id.data)
                # TODO: Add notifications

        return dict(people=people,
                    groups=groups,
                    licenses=licenses,
                    trusted_apps=trusted_apps,
                    groupform=group_form,
                    gtypeform=grouptype_form,
                    licenseform=license_form,
                    trustedpermform=trustedperm_form,
                    tpermform=token_form)

    @view_config(route_name='captcha-image', renderer='jpeg')
    def captcha_image(self):
        try:
            cipherkey = self.request.matchdict['cipherkey']
        except KeyError:
            return HTTPBadRequest

        captcha = Captcha()

        return captcha.get_image(cipherkey)

    @view_config(route_name='add-group', permission='group_edit',
                 renderer='/groups/edit.xhtml')
    def add_group(self):
        """ Group addition page."""

        form = setup_group_form(self.request)

        if self.request.method == 'POST' \
                and ('form.save.group-details' in self.request.params):
            if form.validate():
                group = register.add_group(form)
                self.notify(GroupCreated(
                    self.request, group, person=self.request.get_user)
                )
                return redirect_to(self.request, 'group-details', id=group.id)

        return dict(form=form)

    @view_config(route_name='dump-data', permission='admin', renderer='json')
    def dump(self):
        query = None
        query_order = None
        limit = 0
        offset = 0

        key = self.request.matchdict.get('key')
        log.debug(self.request.params)
        #try:
        if self.request.params['search[value]'] != '':
            query = self.request.params['search[value]']

        #query_order = self.request.params['order']

        limit = int(self.request.params['length'])
        offset = int(self.request.params['start'])
        log.debug(limit)
        log.debug(offset)
        #except KeyError:
            #pass

        data = dict()
        data.setdefault('total')
        data.setdefault('rows')

        # # Compute page number
        # offset = (offset / int(limit))
        # offset += 1 if offset == 1 else 0

        if query:
            if '*' in query:
                query = query.replace('*', '%')
            else:
                query += '%'

        if 'people' == key:
            log.debug(limit)
            log.debug(offset)
            items_count = provider.get_people(count=True)
            if query:
                filtered_items_count = provider.get_people(count=True,
                                        pattern=query, status=AccountStatus)
            else:
                filtered_items_count = items_count
            order_column = self.request.params['order[0][column]']
            orderby = self.request.params['columns['+order_column+'][data]']
            ordering = self.request.params['order[0][dir]']
            items = [i.to_json(AccountPermissionType.CAN_READ_PUBLIC_INFO)
                     for i in
                     provider.get_people(limit=int(limit), pattern=query,
                                         offset=offset, status=AccountStatus, orderby=orderby, ordering=ordering) if
                     i is not None]
        elif 'groups' == key:
            order_column = self.request.params['order[0][column]']
            orderby = self.request.params['columns['+order_column+'][data]']
            ordering = self.request.params['order[0][dir]']
            items = [i.to_json(AccountPermissionType.CAN_READ_PUBLIC_INFO, True)
                     for i in
                     provider.get_groups(limit=int(limit), pattern=query,
                                         status=GroupStatus, offset=offset,
                                         orderby=orderby, ordering=ordering) if
                     i is not None]
            items_count = provider.get_groups(count=True)
            if query:
                filtered_items_count = provider.get_groups(count=True,
                                        pattern=query, status=GroupStatus)
            else:
                filtered_items_count = items_count
        elif 'grouptypes' == key:
            gt = provider.get_group_types()
            items_count = len(gt)
            items = [i.to_json() for i in gt if i is not None]
        elif 'licenses' == key:
            la = provider.get_licenses()
            items = [i.to_json() for i in la if i is not None]
            items_count = len(la)
        elif 'certificates' == key:
            certs = provider.get_certificates()
            items = [i.to_json() for i in certs if certs is not None]
            items_count = len(certs)
        elif 'trustedapps' == key:
            apps = provider.get_trusted_perms()
            items = [i.to_json() for i in apps if apps is not None]
            items_count = len(apps)
        else:
            items = []
            items_count = 0

        log.warn('Offset is: {}'.format(offset))
        if items is not None:
            data['draw'] = int(self.request.params['draw'])
            data['recordsFiltered'] = filtered_items_count
            data['recordsTotal'] = items_count
            data['data'] = items
        log.debug(data)
        return data

    @view_config(route_name='remove-group', permission='admin')
    @view_config(route_name='remove-group', permission='admin', xhr=True,
                 renderer='json')
    def remove_group(self):
        """ Remove a group from system."""
        try:
            self.id = self.request.matchdict['id']
        except KeyError:
            return HTTPBadRequest()

        # TODO: Add a confirmation form if group has members and child groups?.
        group = provider.get_group_by_id(self.id)

        if group.members and len(group.members) > 1:
            status = "failed"
            msg_type = 'error'
            msg = "Cannot remove group {0:s}. Revoke membership first.".format(
                group.name)
            self.request.response.status_code = 403
        else:
            status = "success"
            msg_type = 'info'
            msg = "Group {0:s} has been deleted from system".format(group.name)

            register.remove_group(group)
            self.notify(GroupDeleted(self.request, group))

        if self.request.is_xhr:  # We only use js that set this in header
            return {"status": status, "msg": msg}

        self.request.session.flash(msg, msg_type)

        if status == "failed":
            return redirect_to(self.request, 'group-details', id=group.id)
        else:
            return redirect_to(self.request, 'groups')

    @view_config(route_name='add-license', permission='admin',
                 renderer='/admin/edit-license.xhtml')
    def add_license(self):
        """ Add license page."""
        form = EditLicenseForm(self.request.POST)

        if self.request.method == 'POST' \
                and ('form.save.license' in self.request.params):
            if form.validate():
                la = register.add_license(form)
                # return redirect_to('/settings/option#licenses%s' % la.id)
                # Redirect to home as admin page not view-able now
                return redirect_to(self.request, 'home')

        return dict(form=form)

    @view_config(route_name='edit-license', permission='admin',
                 renderer='/admin/edit-license.xhtml')
    def edit_license(self):
        """ Edit license infos form page."""
        try:
            self.id = self.request.matchdict['id']
        except KeyError:
            return HTTPBadRequest()

        la = provider.get_license_by_id(self.id)

        form = EditLicenseForm(self.request.POST, la)

        if self.request.method == 'POST' \
                and ('form.save.license' in self.request.params):
            if form.validate():
                form.populate_obj(la)
                # Redirect to home as admin page not view-able now
                return redirect_to(self.request, 'home')

        return dict(form=form)

    @view_config(route_name='remove-license', permission='admin')
    def remove_license(self):
        """ Remove a license from system. """
        try:
            self.id = self.request.matchdict['id']
        except KeyError:
            return HTTPBadRequest()

        register.remove_license(self.id)

        # Redirect to home as admin page not view-able now
        return redirect_to(self.request, 'home')

        return dict()

    @view_config(route_name='sign-license', permission='authenticated')
    def sign_license(self):
        """ Sign license from given people """
        try:
            self.id = self.request.matchdict['id']
        except KeyError:
            return HTTPBadRequest()

        person = self.request.get_user
        userform = ContactInfosForm(self.request.POST, person)
        form = SignLicenseForm(self.request.POST)

        userform.username.data = person.username
        userform.fullname.data = person.fullname
        userform.email.data = person.email

        if self.request.method == 'POST' \
                and ('form.sign.license' in self.request.params):
            if userform.validate() and form.validate():
                userform.populate_obj(person)

                form.people.data = person.id
                form.license.data = self.id
                register.add_signed_license(form)

                return redirect_to(self.request.params['form.sign.license'])

        return redirect_to(self.request, 'home')

    @view_config(route_name='add-grouptype', permission='admin',
                 renderer='/admin/edit-grouptype.xhtml')
    def add_grouptype(self):
        """ Add/Edit group type's page."""
        form = EditGroupTypeForm(self.request.POST)

        if self.request.method == 'POST' \
                and ('form.save.grouptype' in self.request.params):
            if form.validate():
                gt = register.add_grouptype(form)
                # return redirect_to('/settings/option#GroupsType%s' % la.id)
                # Redirect to home as admin page not view-able now
                return redirect_to(self.request, 'home')

        return dict(form=form)

    @view_config(route_name='edit-grouptype', permission='admin',
                 renderer='/admin/edit-grouptype.xhtml')
    def edit_grouptype(self):
        """ Edit group type' infos form page."""
        try:
            self.id = self.request.matchdict['id']
        except KeyError:
            return HTTPBadRequest()

        gt = provider.get_grouptype_by_id(self.id)

        form = EditLicenseForm(self.request.POST, gt)

        if self.request.method == 'POST' \
                and ('form.save.grouptype' in self.request.params):
            if form.validate():
                form.populate_obj(gt)
                # Redirect to home as admin page not view-able now
                return redirect_to(self.request, 'home')

        return dict(form=form)

    @view_config(route_name='remove-grouptype', permission='admin')
    @view_config(route_name='remove-grouptype', permission='admin', xhr=True,
                 renderer='json')
    def remove_grouptype(self):
        """ Remove group type page."""
        return dict()

    @view_config(route_name='add-certificate', permission='admin',
                 renderer='/admin/edit-certificate.xhtml')
    def add_certificate(self):
        """ Add new certificates form page. """
        form = EditCertificateForm(self.request.POST)

        if self.request.method == 'POST' \
                and ('form.save.certificate' in self.request.params):
            if form.validate():
                register.add_certificate(form)
                return redirect_to(self.request, 'settings')

        return dict(form=form)

    @view_config(route_name='get-client-cert', permission='authenticated')
    def get_client_cert(self):
        """ Generate and return as attachment client certificate. """
        response = self.request.response
        person = self.request.get_user
        form = CreateClientCertificateForm(self.request.POST)

        if self.request.method == 'POST' \
                and ('form.create.client_cert' in self.request.params):
            if not form.validate():
                # Should redirect to previous url
                log.error('Invalid form value from requester :'
                          'cacert: %s, group_id: %s, group_name: %s' %
                          (form.cacert.data, form.group_id.data,
                           form.group_name.data))
                raise redirect_to(self.request, 'home')
            else:
                # Setup headers
                headers = response.headers
                headers['Accept'] = 'text'
                headers['Content-Description'] = 'Files transfer'
                headers['Content-Type'] = 'text'
                headers['Accept-Ranges'] = 'bytes'
                headers['Content-Disposition'] = \
                    'attachment; filename=%s-%s.cert' \
                    % (Config.get('project.name'), str(form.group_name.data))

                client_cert = provider.get_people_certificate(
                    form.cacert.data, person)

                serial = 1

                if client_cert:
                    log.debug('Found client certificate')
                    cacert = client_cert.cacert
                    if not Config.get('project.group.cert.always_renew'):
                        response.body = client_cert.certificate
                        return response
                    else:
                        serial = client_cert.serial + 1
                else:
                    cacert = provider.get_certificate(form.cacert.data)

                certm = CertificateManager(cacert.cert, cacert.cert_key, Config)

                (new_cert, new_key) = certm.create_client_certificate(
                    person.username,
                    person.email,
                    form.client_cert_desc.data,
                    serial)

                cert = new_cert
                cert += new_key

                log.debug('Registering client certificate: %s', cert)

                register.add_client_certificate(cacert, person, cert, serial)
                self.notify(NewClientCertificateCreated(
                    self.request, person, form.group_name.data))

                response.body = cert

                return response

        raise redirect_to(self.request, 'home')

    @view_config(route_name='lock', permission='authenticated', xhr=True,
                 renderer='json')
    def lock(self):
        try:
            self.id = self.request.matchdict['id']
            context = self.request.matchdict['context']
        except KeyError:
            return HTTPBadRequest()

        if context == 'people':
            people = provider.get_people_by_id(self.id)
            people.status = AccountStatus.LOCKED_BY_ADMIN.value
            self.msg = '{0:s} {1:s} has been locked'.format(context,
                                                            people.username)
        elif context == 'group':
            group = provider.get_group_by_id(self.id)
            group.status = GroupStatus.LOCKED.value
            self.msg = '{0:s} {1:s} has been locked'.format(context, group.name)
        else:
            return {'status': 'error', 'msg': 'invalid ctx: {0:s}'.format(context)}

        return {'status': 'success', 'msg': self.msg}

    @view_config(route_name='unlock', permission='authenticated', xhr=True,
                 renderer='json')
    def unlock(self):
        try:
            self.id = self.request.matchdict['id']
            context = self.request.matchdict['context']
        except KeyError:
            return HTTPBadRequest()

        if context == 'people':
            people = provider.get_people_by_id(self.id)
            people.status = AccountStatus.ACTIVE.value
            self.msg = '{0:s} {1:s} has been unlocked'.format(context,
                                                              people.username)
        elif context == 'group':
            group = provider.get_group_by_id(self.id)
            group.status = GroupStatus.ACTIVE.value
            self.msg = '{0:s} {1:s} has been unlocked'.format(context, group.name)
        else:
            return {'status': 'error', 'msg': 'invalid ctx: {0:s}'.format(context)}

        return dict(status='success',
                    msg='{0:s} {1:s} has been unlocked.'.format(
                        context, people.username
                    ))

    @view_config(route_name='archive', permission='authenticated', xhr=True,
                 renderer='json')
    def archive(self):
        try:
            self.id = self.request.matchdict['id']
            context = self.request.matchdict['context']
        except KeyError:
            return HTTPBadRequest()

        if context == 'people':
            people = provider.get_people_by_id(self.id)
            people.status = AccountStatus.DISABLED.value
            self.msg = 'Account {0:s} has been disabled and archived'.format(
                people.username)
        elif context == 'group':
            group = provider.get_group_by_id(self.id)
            group.status = GroupStatus.DISABLED.value
            self.msg = 'Group {0:s} has been disabled'.format(group.name)
        elif context == 'license':
            license = provider.get_license_by_id(self.id)
            license.status = LicenseAgreementStatus.DISABLED.value
            self.msg = 'License {0:s} has been disabled'.format(license.name)
        else:
            logging.error(self.msg)

        return {'status': 'success', 'msg': self.msg}
