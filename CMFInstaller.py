# (C) Copyright 2003 Nuxeo SARL <http://nuxeo.com>
# Author: Lennart Regebro <regebro@nuxeo.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
#
# $Id$

import os
from re import match
from zLOG import LOG, INFO, DEBUG
from App.Extensions import getPath
from Products.PythonScripts.PythonScript import PythonScript
from Products.CMFCore.utils import getToolByName

SECTIONS_ID = 'sections'
WORKSPACES_ID = 'workspaces'
log_ok_message = '   Already correctly installed'

class CMFInstaller:
    """Base class for product-specific installers"""
    product_name = None

    def __init__(self, context, product_name=None, is_main_installer=1):
        """CMFInstaller initialization

        product_name should be set as a class attribute when subclassing,
        but must be passed if you are not subclassing the installer.

        is_main_installer should be se to 0 if this installer is called
        from another installer to prevent multiple reindexing of catalogs
        and similar actions that only needs to be done once.
        """
        self.context = context
        self.portal = context.portal_url.getPortalObject()
        self.messages = []
        self.is_main_installer = is_main_installer
        if product_name is not None:
            self.product_name = product_name
        if self.product_name is None:
            raise ValueError('No product name given to installer')

    def finalize(self):
        """Does all the things that only needs to be done once"""
        if not self.is_main_installer:
            return
        ct = self.portal.portal_catalog
        changed_indexes = getattr(self.portal, '_v_changed_indexes', [])
        if changed_indexes:
            self.log('Reindex Catalog')
            for name in changed_indexes:
                ct.reindexIndex(name, self.portal.REQUEST)

    #
    # Logging
    #
    def log(self, message):
        self.messages.append(message)
        LOG(self.product_name, INFO, message)

    def logOK(self):
        self.log(log_ok_message)

    def flush(self):
        log = '\n'.join(self.messages)
        self.messages = []
        return log

    def logResult(self):
        return '''<html><head><title>%s</title></head>
            <body><pre>%s</pre></body></html>''' % (
            self.product_name, self.flush() )

    #
    # Other support methods
    #
    def portalHas(self, id):
        return id in self.portal.objectIds()

    def getTool(self, id):
        return getToolByName(self.portal, id, None)

    #
    # Methods to setup and manage actions
    #
    def hasAction(self, tool, actionid):
        actions = [action.id for action in self.portal[tool].listActions()]
        for actionid in actions:
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
        self.log(result)

    def verifyActions(self, actionslist):
        for a in actionslist:
            self.addAction(**a)

    def hideActions(self, actions):
        # XXX This breaks the installer rules, as it does not check
        # if it already has been done. A sysadmin may therefore
        # "unhide" an action, only for it to get hidden next time
        # the script is run.
        # An install tool could keep track of whih installs have
        # been run, and this method could check there.
        for tool, actionids in actions.items():
            actions = list(self.portal[tool]._actions)
            for ac in actions:
                id = ac.id
                if id in actionids:
                    if ac.visible:
                        ac.visible = 0
                        self.log(" Hiding action %s from %s" % (id, tool))
            self.portal[tool]._actions = actions

    def deleteActions(self, actions):
        # XXX This breaks the installer rules. See comment
        # for hideActions().
        for tool, actionids in actions.items():
            actions = list(self.portal[tool]._actions)
            for ac in actions:
                id = ac.id
                if id in actionids:
                    if ac.visible:
                        ac.visible = 0
                        self.log(" Deleting action %s from %s" % (id, tool))
            self.portal[tool]._actions = actions

    #
    # Methods to setup and manage skins
    #

    def verifySkins(self, skins):
        """Install or update skins.

        <skins> parameter is a dictionary of {<skin_name>: <skin_path>),}"""

        self.log("Verifying skins")
        skin_installed = 0
        for skin, path in skins.items():
            path = path.replace('/', os.sep)
            self.log(" FS Directory View '%s'" % skin)
            if skin in self.portal.portal_skins.objectIds():
                dv = self.portal.portal_skins[skin]
                oldpath = dv.getDirPath()
                if oldpath == path:
                    self.logOK()
                else:
                    self.log("  Incorrectly installed, correcting path")
                    dv.manage_properties(dirpath=path)
            else:
                skin_installed = 1
                self.portal.portal_skins.manage_addProduct['CMFCore'].manage_addDirectoryView(filepath=path, id=skin)
                self.log("  Creating skin")

        if skin_installed:
            all_skins = self.portal.portal_skins.getSkinPaths()
            for skin_name, skin_path in all_skins:
                if skin_name != 'Basic':
                    continue
                path = [x.strip() for x in skin_path.split(',')]
                path = [x for x in path if x not in skins] # strip all
                if path and path[0] == 'custom':
                    path = path[:1] + [skin[0] for skin in skins] + path[1:]
                else:
                    path = [skin[0] for skin in skins] + path
                npath = ', '.join(path)
                self.portal.portal_skins.addSkinSelection(skin_name, npath)
                self.log(" Fixup of skin %s" % skin_name)
            self.log(" Resetting skin cache")
            self.portal._v_skindata = None
            self.portal.setupCurrentSkin()

    #
    # Portal_catalog management methods
    #
    def addPortalCatalogIndex(self, id, type):
        """Adds an index on portal_catalog"""
        self.log(' Portal_catalog indexes: Adding %s %s' % (type, id))
        ct = self.portal.portal_catalog
        if id in ct.indexes():
            if ct._catalog.getIndex(id).meta_type == type:
                self.logOK()
                return
            else:
                self.log('  Deleting old index')
                ct.delIndex('uid')
        ct.addIndex('uid', 'FieldIndex')
        self.flagIndexForReindex(id)

    def flagIndexForReindex(self, indexid):
        indexes = getattr(self.portal, '_v_changed_indexes', [])
        indexes.append(indexid)
        self.portal._v_changed_indexes = indexes

    #
    # Mixed management methods
    #

    def addRoles(self, roles):
        already = self.portal.valid_roles()
        for role in roles:
            if role not in already:
                self.portal._addRole(role)
                self.log(" Add role %s" % role)

    def addCalendarTypes(self, type_ids):
        ctool = getToolByName(self.portal, 'portal_calendar', None)
        if ctool is None:
            return

        current_types = ctool.calendar_types
        for tid in type_ids:
            if tid not in current_types:
                self.log(' Calendar type %s added' % tid)
                current_types.append(tid)
        ctool.calendar_types = current_types

    def addTool(self, toolid, product, meta_type):
        self.log('Creating %s' % toolid)
        if self.portalhas(toolid):
            self.logOK()
        else:
            self.portal.manage_addProduct[product].manage_addTool(meta_type)


