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
from types import StringType
from zLOG import LOG, INFO, DEBUG
from App.Extensions import getPath
from Products.PythonScripts.PythonScript import PythonScript
from Products.CMFCore.utils import getToolByName

SECTIONS_ID = 'sections'
WORKSPACES_ID = 'workspaces'
log_ok_message = '...Already correctly installed'

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
        self.messages = []
        self.portal = context.portal_url.getPortalObject()
        if not hasattr(self.portal, '_v_main_installer'):
            self.portal._v_main_installer = self
        if product_name is not None:
            self.product_name = product_name
        if self.product_name is None:
            raise ValueError('No product name given to installer')

    def isMainInstaller(self):
        if getattr(self.portal, '_v_main_installer', 1) is self:
            return 1
        return 0

    def finalize(self):
        if self.isMainInstaller():
            self._cmf_finalize()

    def _cmf_finalize(self):
        """Does all the things that only needs to be done once"""
        self.reindexCatalog()
        self.resetSkinCache()
        self.reindexSecurity()
        delattr(self.portal, '_v_main_installer')

    #
    # Methods normally called only at the end of an install.
    # Typically reindexing methods and similar.
    #
    def reindexCatalog(self):
        # Reindex portal_catalog
        reindex_catalog = getattr(self.portal, '_v_reindex_catalog', 0)
        changed_indexes = getattr(self.portal, '_v_changed_indexes', [])
        if reindex_catalog or len(changed_indexes) > 1:
            self.log('Reindex Catalog')
            self.portal.portal_catalog.refreshCatalog(clear=1)
        elif changed_indexes:
            ct = self.portal.portal_catalog
            self.log('Reindex Catalog indexes %s' % ', '.join(changed_indexes))
            for name in changed_indexes:
                ct.reindexIndex(name, self.portal.REQUEST)
        setattr(self.portal, '_v_reindex_catalog', 0)
        setattr(self.portal, '_v_changed_indexes', [])

    def resetSkinCache(self):
        # Reset skins cache
        if getattr(self.portal, '_v_reset_skins', 0):
            self.log("Resetting skin cache")
            self.portal._v_skindata = None
            self.portal.setupCurrentSkin()
        setattr(self.portal, '_v_reset_skins', 0)

    def reindexSecurity(self):
        if getattr(self.portal, '_v_reindex_security', 0):
            self.log("Reindexing Security")
            self.portal.reindexObjectSecurity()
        setattr(self.portal, '_v_reindex_security', 0)

    #
    # Logging
    #
    def log(self, message):
        self.messages.append(message)
        LOG(self.product_name, INFO, message)

    def logOK(self):
        self.messages[-1] = self.messages[-1] + log_ok_message
        #self.log(log_ok_message)

    def flush(self):
        log = '\n'.join(self.messages)
        self.messages = []
        return log

    def logResult(self):
        if not self.isMainInstaller():
            return self.flush()
        # Wrap HTML around it if it's the main installer.
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
        for action in self.portal[tool].listActions():
            if action.id == actionid:
                return 1
        return 0

    def verifyAction(self, tool, **kw):
        result = ' Verifying action %s...' % kw['id']
        if self.hasAction(tool, kw['id']):
            result += 'exists.'
        else:
            self.portal[tool].addAction(**kw)
            result += 'added.'
        self.log(result)

    def verifyActions(self, actionslist):
        for a in actionslist:
            self.verifyAction(**a)

    def hideActions(self, hidemap):
        # XXX This breaks the installer rules, as it does not check
        # if it already has been done. A sysadmin may therefore
        # "unhide" an action, only for it to get hidden next time
        # the script is run.
        # An install tool could keep track of whih installs have
        # been run, and this method could check there.
        for tool, actionids in hidemap.items():
            actions = list(self.portal[tool]._actions)
            for ac in actions:
                id = ac.id
                if id in actionids:
                    if ac.visible:
                        ac.visible = 0
                        self.log(" Hiding action %s from %s" % (id, tool))
            self.portal[tool]._actions = actions

    def deleteActions(self, deletemap):
        # XXX This breaks the installer rules. See comment
        # for hideActions().
        for tool, actionids in deletemap.items():
            actions = [ ac for ac in list(self.portal[tool]._actions)\
                                  if ac.id not in actionids ]
            for ac in actionids:
                self.log(" Deleting action %s from %s" % (id, tool))
            self.portal[tool]._actions = tuple(actions)

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
                path = [x for x in path if x not in skins.keys()] # strip all
                if path and path[0] == 'custom':
                    path = path[:1] + [skin for skin in skins.keys()] + path[1:]
                else:
                    path = [skin[0] for skin in skins.keys()] + path
                npath = ', '.join(path)
                self.portal.portal_skins.addSkinSelection(skin_name, npath)
                self.log(" Fixup of skin %s" % skin_name)
            self.flagSkinCacheReset()

    def deleteSkins(self, skinlist):
        self.log('Deleting skins %s' % ', '.join(skinlist))
        for skin in skinlist:
            if skin in self.portal.portal_skins.objectIds():
                self.portal.portal_skins._delObject(skin)
                self.flagSkinCacheReset()

    def flagSkinCacheReset(self):
        self.portal._v_reset_skins = 1

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
        self.flagCatalogForReindex(id)

    def flagCatalogForReindex(self, indexid=None):
        if indexid is None:
            # Reindex all catalog
            self.portal._v_reindex_catalog = 1
            return
        indexes = getattr(self.portal, '_v_changed_indexes', [])
        indexes.append(indexid)
        self.portal._v_changed_indexes = indexes

    #
    # Portal_types management methods
    #
    def allowContentTypes(self, allowed_types, allowed_in):
        """Allow a list of types in a list of types

        makes sure that the types in the list allowed_types will be allowed
        as content types in the types in the list allowed_in
        """
        if isinstance(allowed_types, StringType):
            allowed_types=(allowed_types,)
        if isinstance(allowed_in, StringType):
            allowed_in=(allowed_in,)
        ttool = self.portal.portal_types
        for type in allowed_in:
            workspaceACT = list(ttool[type].allowed_content_types)
            for ptype in allowed_types:
                if ptype not in  workspaceACT:
                    workspaceACT.append(ptype)
            ttool[type].allowed_content_types = workspaceACT

    def verifyContentTypes(self, type_dict):
        """Checks the content_types

        type_dict is:
        {'typeid': {'allowed_content_types': ('type1', 'type2'),
                    'typeinfo_name': 'Product: Typename',
                    'add_meta_type': 'Factory-based Type Information',
                   }
        }
        """
        self.log("Verifying portal types")
        ttool = self.portal.portal_types
        ptypes_installed = ttool.objectIds()

        for ptype, typeinfo in type_dict.items():
            self.log("  Type '%s'" % ptype)
            if ptype in ptypes_installed:
                self.logOK()
                continue

            self.log("  Adding")
            ttool.manage_addTypeInformation(
                id=ptype,
                add_meta_type=typeinfo['add_meta_type'],
                typeinfo_name=typeinfo['typeinfo_name'],
                )
            if typeinfo.has_key('properties'):
                ttool[ptype].manage_changeProperties(
                    **typeinfo['properties'])

            self.allowContentTypes(typeinfo.get('allowed_content_types', ()), ptype)

    #
    # Access control management methods
    #

    def verifyRoles(self, roles):
        already = self.portal.valid_roles()
        for role in roles:
            if role not in already:
                self.portal._addRole(role)
                self.log(" Add role %s" % role)

    def setupPortalPermissions(self, permissions, object=None):
        """Sets up the permissions of an object

        Uses the portal object if no other object is given.

        permissions is a dict:
        {'permission': ['list', 'of', 'roles'],}
        """
        if object is None:
            object = self.portal
        # XXX Once again this does not verify anything, but brutally
        # overrides any earlier changes.
        for perm, roles in permissions.items():
            self.log("  Setting up permission %s" % perm)
            object.manage_permission(perm, roles, 0)
        self.flagReindexSecurity()

    def flagReindexSecurity(self):
        self.portal._v_reindex_security = 1

    #
    # Mixed management methods
    #

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

    def removeCalendarTypes(self, type_ids):
        ctool = getToolByName(self.portal, 'portal_calendar', None)
        if ctool is None:
            return

        current_types = ctool.calendar_types
        for tid in type_ids:
            if tid in current_types:
                self.log(' Calendar type %s removed' % tid)
                current_types.remove(tid)
        ctool.calendar_types = current_types

    def verifyTool(self, toolid, product, meta_type):
        self.log('Verifying tool %s' % toolid)
        if self.portalHas(toolid):
            tool = self.getTool(toolid)
            if tool.meta_type == meta_type:
                self.logOK()
                return
            self.log(' Deleting old %s tool' % tool.meta_type)
            self.portal.manage_delObjects([toolid])
        self.log(' Adding')
        self.portal.manage_addProduct[product].manage_addTool(meta_type)

