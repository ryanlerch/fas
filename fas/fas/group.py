import turbogears
from turbogears import controllers, expose, paginate, identity, redirect, widgets, validate, validators, error_handler

import ldap

import fas.fasLDAP

from fas.fasLDAP import UserAccount
from fas.fasLDAP import Person
from fas.fasLDAP import Groups
from fas.fasLDAP import UserGroup

from fas.auth import *

from fas.user import knownUser, userNameExists

class knownGroup(validators.FancyValidator):
    '''Make sure that a group already exists'''
    def _to_python(self, value, state):
        return value.strip()
    def validate_python(self, value, state):
        g = Groups.groups(value)
        if not g:
            raise validators.Invalid(_("The group '%s' does not exist.") % value, value, state)

class unknownGroup(validators.FancyValidator):
    '''Make sure that a group doesn't already exist'''
    def _to_python(self, value, state):
        return value.strip()
    def validate_python(self, value, state):
        g = Groups.groups(value)
        if g:
            raise validators.Invalid(_("The group '%s' already exists.") % value, value, state)

class createGroup(validators.Schema):
    groupName = validators.All(unknownGroup(not_empty=True, max=10), validators.String(max=32, min=3))
    fedoraGroupDesc = validators.NotEmpty
    fedoraGroupOwner = validators.All(knownUser(not_empty=True, max=10), validators.String(max=32, min=3))

class editGroup(validators.Schema):
    groupName = validators.All(knownGroup(not_empty=True, max=10), validators.String(max=32, min=3))
    fedoraGroupDesc = validators.NotEmpty
    fedoraGroupOwner = validators.All(knownUser(not_empty=True, max=10), validators.String(max=32, min=3))

class userNameGroupNameExists(validators.Schema):
    groupName = validators.All(knownGroup(not_empty=True, max=10), validators.String(max=32, min=3))
    userName = validators.All(knownUser(not_empty=True, max=10), validators.String(max=32, min=3))

class groupNameExists(validators.Schema):
    groupName = validators.All(knownGroup(not_empty=True, max=10), validators.String(max=32, min=3))

#class findUser(widgets.WidgetsList): 
#    userName = widgets.AutoCompleteField(label=_('Username'), search_controller='search', search_param='userName', result_name='people')   
#    action = widgets.HiddenField(default='apply', validator=validators.String(not_empty=True)) 
#    groupName = widgets.HiddenField(validator=validators.String(not_empty=True)) 
#
#findUserForm = widgets.ListForm(fields=findUser(), submit_text=_('Invite')) 

class Group(controllers.Controller):

    def __init__(self):
        '''Create a Group Controller.'''

    def index(self):
        '''Perhaps show a nice explanatory message about groups here?'''
        return dict()

    @expose(template="fas.templates.error")
    def error(self, tg_errors=None):
        '''Show a friendly error message'''
        if not tg_errors:
            turbogears.redirect('/')
        return dict(tg_errors=tg_errors)

    @validate(validators=groupNameExists())
    @error_handler(error)
    @expose(template="fas.templates.group.view")
    @identity.require(turbogears.identity.not_anonymous())
    def view(self, groupName):
        '''View group'''
        groups = Groups.byGroupName(groupName, includeUnapproved=True)
        group = Groups.groups(groupName)[groupName]
        userName = turbogears.identity.current.user_name
        try:
            myStatus = groups[userName].fedoraRoleStatus
        except KeyError:
            # Not in group
            myStatus = 'Not a Member' # This _has_ to stay 'Not a Member'
        except TypeError:
            groups = {}
        try:
            me = groups[userName]
        except:
            me = UserGroup()
        #searchUserForm.groupName.display('group')
        #findUser.groupName.display(value='fff')
        value = {'groupName': groupName}
        return dict(userName=userName, groups=groups, group=group, me=me, value=value)

    @expose(template="fas.templates.group.new")
    @identity.require(turbogears.identity.not_anonymous())
    def new(self):
        '''Display create group form'''
        userName = turbogears.identity.current.user_name
        if not canCreateGroup(userName):
            turbogears.flash(_('Only FAS adminstrators can create groups.'))
            turbogears.redirect('/')
        return dict()

    @validate(validators=createGroup())
    @error_handler(error)
    @expose(template="fas.templates.group.new")
    @identity.require(turbogears.identity.not_anonymous())
    def create(self, groupName, fedoraGroupDesc, fedoraGroupOwner, fedoraGroupNeedsSponsor="FALSE", fedoraGroupUserCanRemove="FALSE", fedoraGroupJoinMsg=""):
        '''Create a group'''
        userName = turbogears.identity.current.user_name
        if not canCreateGroup(userName):
            turbogears.flash(_('Only FAS adminstrators can create groups.'))
            turbogears.redirect('/')
        try:
            fas.fasLDAP.Group.newGroup(groupName.encode('utf8'),
                                       fedoraGroupDesc.encode('utf8'),
                                       fedoraGroupOwner.encode('utf8'),
                                       fedoraGroupNeedsSponsor.encode('utf8'),
                                       fedoraGroupUserCanRemove.encode('utf8'),
                                       fedoraGroupJoinMsg.encode('utf8'),)

        except:
            turbogears.flash(_("The group: '%s' could not be created.") % groupName)
            return dict()
        else:
            try:
                p = Person.byUserName(fedoraGroupOwner) 
                Groups.apply(groupName, fedoraGroupOwner) # Apply...
                p.sponsor(groupName, userName) # Approve...
                p.upgrade(groupName) # Sponsor...
                p.upgrade(groupName) # Admin!
            except:
                turbogears.flash(_("The group: '%(group)s' has been created, but '%(user)' could not be added as a group administrator.") % {'group': groupName, 'user': fedoraGroupOwner})
            else:
                turbogears.flash(_("The group: '%s' has been created.") % groupName)
            turbogears.redirect('/group/view/%s' % groupName)
            return dict()

    @expose(template="fas.templates.group.edit")
    @identity.require(turbogears.identity.not_anonymous())
    def edit(self, groupName):
        '''Display edit group form'''
        userName = turbogears.identity.current.user_name
        if not canAdminGroup(userName, groupName):
            turbogears.flash(_("You cannot edit '%s'.") % groupName)
            turbogears.redirect('/group/view/%s' % groupName)
        group = Groups.groups(groupName)[groupName]
        value = {'groupName': groupName,
                 'fedoraGroupDesc': group.fedoraGroupDesc,
                 'fedoraGroupOwner': group.fedoraGroupOwner,
                 'fedoraGroupType': group.fedoraGroupType,
                 'fedoraGroupNeedsSponsor': (group.fedoraGroupNeedsSponsor.upper() == 'TRUE'),
                 'fedoraGroupUserCanRemove': (group.fedoraGroupUserCanRemove.upper() == 'TRUE'),
                 #'fedoraGroupRequires': group.fedoraGroupRequires,
                 'fedoraGroupJoinMsg': group.fedoraGroupJoinMsg, }
        return dict(value=value)

    @validate(validators=editGroup())
    @error_handler(error)
    @expose()
    @identity.require(turbogears.identity.not_anonymous())
    def save(self, groupName, fedoraGroupDesc, fedoraGroupOwner, fedoraGroupType=1, fedoraGroupNeedsSponsor="FALSE", fedoraGroupUserCanRemove="FALSE", fedoraGroupJoinMsg=""):
        '''Edit a group'''
        userName = turbogears.identity.current.user_name
        if not canEditGroup(userName, groupName):
            turbogears.flash(_("You cannot edit '%s'.") % groupName)
            turbogears.redirect('/group/view/%s' % groupName)
        # TODO: This is kind of an ugly hack.
        else:
            base = 'cn=%s,ou=FedoraGroups,dc=fedoraproject,dc=org' % groupName
            try:
                fas.fasLDAP.modify(base, 'fedoraGroupDesc', fedoraGroupDesc.encode('utf8'))
                fas.fasLDAP.modify(base, 'fedoraGroupOwner', fedoraGroupOwner.encode('utf8'))
                fas.fasLDAP.modify(base, 'fedoraGroupType', str(fedoraGroupType).encode('utf8'))
                fas.fasLDAP.modify(base, 'fedoraGroupNeedsSponsor', fedoraGroupNeedsSponsor.encode('utf8'))
                fas.fasLDAP.modify(base, 'fedoraGroupUserCanRemove', fedoraGroupUserCanRemove.encode('utf8'))
                fas.fasLDAP.modify(base, 'fedoraGroupJoinMsg', fedoraGroupJoinMsg.encode('utf8'))
            except:
                turbogears.flash(_('The group details could not be saved.'))
            else:
                turbogears.flash(_('The group details have been saved.'))
                turbogears.redirect('/group/view/%s' % groupName)
            return dict()

    @expose(template="fas.templates.group.list")
    @identity.require(turbogears.identity.not_anonymous())
    def list(self, search='*'):
        groups = Groups.groups(search)
        userName = turbogears.identity.current.user_name
        myGroups = Groups.byUserName(userName)
        try:
            groups.keys()
        except:
            turbogears.flash(_("No Groups found matching '%s'") % search)
            groups = {}
        return dict(groups=groups, search=search, myGroups=myGroups)

    @validate(validators=userNameGroupNameExists())
    @error_handler(error)
    @expose(template='fas.templates.group.view')
    @identity.require(turbogears.identity.not_anonymous())
    def apply(self, groupName, userName=None):
        '''Apply to a group'''
        applicant = turbogears.identity.current.user_name
        if not userName:
            userName = applicant
        if not canApplyGroup(applicant, groupName, userName):
            turbogears.flash(_('You cannot apply %(user)s for %(group)s!') % \
                {'user': userName, 'group': groupName})
            turbogears.redirect('/group/view/%s' % groupName)
            return dict()
        else:
            try:
                Groups.apply(groupName, userName)
            except ldap.ALREADY_EXISTS:
                turbogears.flash(_('%(user)s has already applied to %(group)s!') % \
                    {'user': userName, 'group': groupName})
            else:
                turbogears.flash(_('%(user)s has applied to %(group)s!') % \
                    {'user': userName, 'group': groupName})
                turbogears.redirect('/group/view/%s' % groupName)
            return dict()

    @validate(validators=userNameGroupNameExists())
    @error_handler(error)
    @expose(template='fas.templates.group.view')
    @identity.require(turbogears.identity.not_anonymous())
    def sponsor(self, groupName, userName):
        '''Sponsor user'''
        sponsor = turbogears.identity.current.user_name
        if not canSponsorUser(sponsor, groupName, userName):
            turbogears.flash(_("You cannot sponsor '%s'") % userName)
            turbogears.redirect('/group/view/%s' % groupName)
            return dict()
        else:
            p = Person.byUserName(userName)
            # TODO: Check if the person actually applied to the group.
            # (or should this be done in auth.py or fasLDAP.py?)
            # this will probably give a 500 now if the user didn't apply
            try:
                p.sponsor(groupName, sponsor)
            except:
                turbogears.flash(_("'%s' could not be sponsored!") % p.cn)
                turbogears.redirect('/group/view/%s' % groupName)
            else:
                turbogears.flash(_("'%s' has been sponsored!") % p.cn)
                turbogears.redirect('/group/view/%s' % groupName)
            return dict()

    @validate(validators=userNameGroupNameExists())
    @error_handler(error)
    @expose(template='fas.templates.group.view')
    @identity.require(turbogears.identity.not_anonymous())
    def remove(self, groupName, userName):
        '''Remove user from group'''
        # TODO: Add confirmation?
        sponsor = turbogears.identity.current.user_name
        if not canRemoveUser(sponsor, groupName, userName):
            turbogears.flash(_("You cannot remove '%s'.") % userName)
            turbogears.redirect('/group/view/%s' % groupName)
            return dict()
        else:
            try:
                Groups.remove(groupName, userName)
            except:
                turbogears.flash(_('%(name)s could not be removed from %(group)s!') % \
                    {'name': userName, 'group': groupName})
                turbogears.redirect('/group/view/%s' % groupName)
            else:
                turbogears.flash(_('%(name)s has been removed from %(group)s!') % \
                    {'name': userName, 'group': groupName})
                turbogears.redirect('/group/view/%s' % groupName)
            return dict()

    @validate(validators=userNameGroupNameExists())
    @error_handler(error)
    @expose(template='fas.templates.group.view')
    @identity.require(turbogears.identity.not_anonymous())
    def upgrade(self, groupName, userName):
        '''Upgrade user in group'''
        sponsor = turbogears.identity.current.user_name
        if not canUpgradeUser(sponsor, groupName, userName):
            turbogears.flash(_("You cannot upgrade '%s'") % userName)
            turbogears.redirect('/group/view/%s' % groupName)
            return dict()
        else:
            p = Person.byUserName(userName)
            try:
                p.upgrade(groupName)
            except:
                turbogears.flash(_('%(name)s could not be upgraded!') % userName)
                turbogears.redirect('/group/view/%s' % groupName)
            else:
                turbogears.flash(_('%s has been upgraded!') % userName)
                turbogears.redirect('/group/view/%s' % groupName)
            return dict()

    @validate(validators=userNameGroupNameExists())
    @error_handler(error)
    @expose(template='fas.templates.group.view')
    @identity.require(turbogears.identity.not_anonymous())
    def downgrade(self, groupName, userName):
        '''Upgrade user in group'''
        sponsor = turbogears.identity.current.user_name
        if not canDowngradeUser(sponsor, groupName, userName):
            turbogears.flash(_("You cannot downgrade '%s'") % userName)
            turbogears.redirect('/group/view/%s' % groupName)
            return dict()
        else:
            p = Person.byUserName(userName)
            try:
                p.upgrade(groupName)
            except:
                turbogears.flash(_('%(name)s could not be downgraded!') % userName)
                turbogears.redirect('/group/view/%s' % groupName)
            else:
                turbogears.flash(_('%s has been downgraded!') % p.cn)
                turbogears.redirect('/group/view/%s' % groupName)
            return dict()

    @validate(validators=groupNameExists())
    @error_handler(error)
    @expose(template="genshi-text:fas.templates.group.dump", format="text", content_type='text/plain; charset=utf-8')
    @identity.require(turbogears.identity.not_anonymous())
    def dump(self, groupName=None):
        groups = Groups.byGroupName(groupName)
        return dict(groups=groups, Person=Person)

