# (c) 2003 Nuxeo SARL <http://nuxeo.com>
# $Id$
""" here we go
"""

import os
import sys
from Globals import package_home
from AccessControl import getSecurityManager
from zLOG import LOG, INFO, DEBUG
from Products.CMFCore.ActionInformation import ActionInformation
from Products.CMFCore.CMFCorePermissions import View, ModifyPortalContent, \
     ReviewPortalContent, RequestReview
from Products.PythonScripts.PythonScript import PythonScript

from Products.CPSCore.CPSWorkflow import \
     TRANSITION_INITIAL_PUBLISHING, TRANSITION_INITIAL_CREATE, \
     TRANSITION_ALLOWSUB_CREATE, TRANSITION_ALLOWSUB_PUBLISHING, \
     TRANSITION_BEHAVIOR_PUBLISHING, TRANSITION_BEHAVIOR_FREEZE, \
     TRANSITION_BEHAVIOR_DELETE, TRANSITION_BEHAVIOR_MERGE, \
     TRANSITION_ALLOWSUB_CHECKOUT, TRANSITION_INITIAL_CHECKOUT, \
     TRANSITION_BEHAVIOR_CHECKOUT, TRANSITION_ALLOW_CHECKIN, \
     TRANSITION_BEHAVIOR_CHECKIN, TRANSITION_ALLOWSUB_DELETE, \
     TRANSITION_ALLOWSUB_MOVE, TRANSITION_ALLOWSUB_COPY

from Products.DCWorkflow.Transitions import TRIGGER_USER_ACTION
from Products.CPSDefault import cpsdefault_globals
from Products.CMFCore.utils import minimalpath
from Products.ExternalMethod.ExternalMethod import ExternalMethod


class InstallLogger:

    def __init__(self, modulename):
        self.modulename = modulename
        self.messages = []

    def log(self, message):
        self.messages.append(message)
        LOG(self.modulename, INFO, message)

    def flush(self):
        return '\n'.join(self.messages)


class InstallHelper:

    def __init__(self, script, logger):
        self.portal = script.portal_url.getPortalObject()
        self.logger = logger

    def portalhas(self, id):
        return id in self.portal.objectIds()

    def hasAction(self, tool, actionid):
        for action in self.portal[tool].listActions():
            if action.id == actionid:
                return 1
        return 0

    def addAction(self, tool, **kw):
        result = ' Verifying action %s...' % kw['id']
        if self.hasAction(tool, id):
            result += 'exists.'
        else:
            self.portal[tool].addAction(**kw)
            result += 'added.'
        self.logger.log(result)

    def verifyActions(self, actionslist):
        for a in actionslist:
            self.addAction(**a)

    def hideActions(self, actions):
        for tool, actionids in actions.items():
            actions = list(self.portal[tool]._actions)
            for ac in actions:
                id = ac.id
                if id in actionids:
                    if ac.visible:
                        ac.visible = 0
                        self.logger.log(" Hiding action %s from %s" % (id, tool))
            self.portal[tool]._actions = actions

    def deleteActions(self, actions):
        for tool, actionids in actions.items():
            actions = list(self.portal[tool]._actions)
            for ac in actions:
                id = ac.id
                if id in actionids:
                    if ac.visible:
                        ac.visible = 0
                        self.logger.log(" Deleting action %s from %s" % (id, tool))
            self.portal[tool]._actions = actions

    def addRoles(self, roles):
        already = self.portal.valid_roles()
        for role in roles:
            if role not in already:
                self.portal._addRole(role)
                self.logger.log(" Add role %s" % role)

    def verifySkins(self, skindefs):
        """XXX: write some docstring here stating what a skindefs is"""

        self.logger.log("Verifying skins")

        cmfcore = self.portal.portal_skins.manage_addProduct['CMFCore']

        for skin, path in skindefs.items():
            path = path.replace('/', os.sep)
            self.logger.log(" FS Directory View '%s'" % skin)
            if skin in self.portal.portal_skins.objectIds():
                dv = self.portal.portal_skins[skin]
                oldpath = dv.getDirPath()
                if oldpath == path:
                    self.logger.log(" Already correctly installed")
                else:
                    self.logger.log("  Incorrectly installed, correcting path")
                    dv.manage_properties(dirpath=path)
            else:
                # XXX: Hack around a CMFCore/DirectoryView bug (?)
                path = os.path.join(package_home(cpsdefault_globals),
                     "..", "..", path)
                path = minimalpath(path)

                cmfcore.manage_addDirectoryView(filepath=path, id=skin)
                self.logger.log("  Creating skin")

        allskins = self.portal.portal_skins.getSkinPaths()
        skins = skindefs.keys()
        for skin_name, skin_path in allskins:
            if skin_name != 'Basic':
                continue
            path = [x.strip() for x in skin_path.split(',')]
            path = [x for x in path if x not in skins] # strip all
            if path and path[0] == 'custom':
                path = path[:1] + list(skins) + path[1:]
            else:
                path = list(skins) + path
            npath = ', '.join(path)
            self.portal.portal_skins.addSkinSelection(skin_name, npath)
            self.logger.log(" Fixup of skin %s" % skin_name)
        self.logger.log(" Resetting skin cache")
        self.portal._v_skindata = None
        self.portal.setupCurrentSkin()


    def createWorkflow(self, wfdef):
        wftool = self.portal.portal_workflow
        wfid = wfdef['wfid']

        if wfid in wftool.objectIds():
            wftool.manage_delObjects([wfid])
        wftool.manage_addWorkflow(id=wfid,
                                  workflow_type='cps_workflow (Web-configurable workflow for CPS)')

        wf = wftool[wfid]
        if wfdef.has_key('permissions'):
            for p in wfdef['permissions']:
                wf.addManagedPermission(p)

        if wfdef.has_key('state_var'):
            wf.variables.setStateVar(wfdef['state_var'])

        return wf


    def setupWorkflow(self, wfdef={}, wfstates={}, wftransitions={},
                      wfscripts={}, wfvariables={}):
        self.logger.log(" Setup workflow %s" % wfdef['wfid'])
        wf = self.createWorkflow(wfdef)

        for stateid in wfstates.keys():
            self.logger.log('  Adding state %s' % stateid)
            wf.states.addState(stateid)

        for transid in wftransitions.keys():
            self.logger.log('  Adding transition %s' % transid)
            wf.transitions.addTransition(transid)

        for stateid, statedef in wfstates.items():
            state = wf.states.get(stateid)
            state.setProperties(title=statedef['title'], transitions=statedef['transitions'])
            for permission in statedef['permissions'].keys():
                state.setPermission(permission, 0, statedef['permissions'][permission])

        for transid, transdef in wftransitions.items():
            trans = wf.transitions.get(transid)
            trans.setProperties(**transdef)

        for scriptid, scriptdef in wfscripts.items():
            wf.scripts._setObject(scriptid, PythonScript(scriptid))
            script = wf.scripts[scriptid]
            script.write(scriptdef['script'])
            for attribute in ('title', '_proxy_roles', '_owner'):
                if scriptdef.has_key(attribute):
                    setattr(script, attribute, scriptdef[attribute])

        for varid, vardef in wfvariables.items():
            wf.variables.addVariable(varid)
            var = wf.variables[varid]
            var.setProperties(**vardef)


    def runExternalUpdater(self, id, title, module, script, method):
        try:
            if not self.portalhas(id):
                __import__(module)
                self.logger.log('Adding %s' % title)
                script = ExternalMethod(id, title, script, method)
                self.portal._setObject(id, script)
            self.logger.log(self.portal[id]())
        except ImportError:
            pass

