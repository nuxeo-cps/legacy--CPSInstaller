# (C) Copyright 2003-2005 Nuxeo SARL <http://nuxeo.com>
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
from types import StringType
from zLOG import LOG, INFO, DEBUG
from AccessControl import getSecurityManager, Unauthorized
from Products.CMFCore.utils import getToolByName, _marker
from Products.CMFCore.DirectoryView import createDirectoryView
from Products.ZCTextIndex.ZCTextIndex import manage_addLexicon, ZCTextIndex

SECTIONS_ID = 'sections'
WORKSPACES_ID = 'workspaces'
log_ok_message = "...Already correctly installed"

class CMFInstaller:
    """Base class for product-specific installers"""
    product_name = None

    def __init__(self, context, product_name=None):
        """CMFInstaller initialization

        product_name should be set as a class attribute when subclassing,
        but must be passed if you are not subclassing the installer.

        is_main_installer should be se to 0 if this installer is called
        from another installer to prevent multiple reindexing of catalogs
        and similar actions that only needs to be done once.
        """
        if not getSecurityManager().getUser().has_role('Manager'):
            raise Unauthorized

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
            self._CMFFinalize()

    def _CMFFinalize(self):
        """Does all the things that only needs to be done once"""
        self.reindexCatalog()
        self.resetSkinCache()
        self.reindexSecurity()
        if hasattr(self.portal, '_v_main_installer'):
            delattr(self.portal, '_v_main_installer')


    def _reindexIndexes(self, indexes, REQUEST):
        # this is same as portal_catalog.reindexIndex
        # except that we update many indexes at the same time
        ct = self.portal.portal_catalog
        paths = ct._catalog.uids.keys()
        for p in paths:
            obj = ct.resolve_path(p)
            if not obj:
                obj = ct.resolve_url(p, REQUEST)
            if obj is not None:
                try:
                    ct.catalog_object(obj, p, idxs=indexes,
                                        update_metadata=0)
                except TypeError:
                    # Fall back to Zope 2.6.2 interface. This is necessary for
                    # products like CMF 1.4.2 and earlier that subclass from
                    # ZCatalog and don't support the update_metadata argument.
                    # May be removed some day.
                    ct.catalog_object(obj, p, idxs=indexes)

    #
    # Methods normally called only at the end of an install.
    # Typically reindexing methods and similar.
    #
    def reindexCatalog(self):
        # Reindex portal_catalog
        reindex_catalog = getattr(self.portal, '_v_reindex_catalog', 0)
        if not reindex_catalog:
            # the only way to update metadata is to refresh the wall catalog :/
            reindex_catalog = getattr(self.portal,
                                      '_v_reindex_catalog_metadata', 0)
        changed_indexes = getattr(self.portal, '_v_changed_indexes', [])
        ct = self.portal.portal_catalog
        if reindex_catalog:
            self.log('Rebuild all catalog indexes')
            ct.refreshCatalog(clear=1)
            if getattr(self.portal, '_v_reindex_security', 0):
                # no need to reindex security index allowedRolesAndUsers
                # as we just reindex the wall catalog
                setattr(self.portal, '_v_reindex_security', 0)
        elif changed_indexes:
            self.log('Rebuild catalog indexes: %s' %
                     ' '.join(changed_indexes))
            self._reindexIndexes(changed_indexes,
                                 self.portal.REQUEST)
        setattr(self.portal, '_v_reindex_catalog', 0)
        setattr(self.portal, '_v_changed_indexes', [])
        setattr(self.portal, '_v_reindex_catalog_metadata', 0)

    def resetSkinCache(self):
        # Reset skins cache
        if getattr(self.portal, '_v_reset_skins', 0):
            self.log("Resetting skin cache")
            self.portal.clearCurrentSkin()
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

    def getTool(self, id, default=_marker):
        """Gets the tool by id

        If No default is given, it will raise an error.
        """
        return getToolByName(self.portal, id, default)
    #
    # Methods to setup and manage actions
    #
    def verifyActionProvider(self, action_provider):
        self.log('Verifying action provider %s' % action_provider)
        atool = self.getTool('portal_actions')
        if action_provider in atool.listActionProviders():
            self.log(' Already correctly installed')
        else:
            atool.addActionProvider(action_provider)
            self.log(' Installed')

    def hasAction(self, tool, actionid):
        for action in self.portal[tool].listActions():
            if action.id == actionid:
                return 1
        return 0

    def getActionIndex(self, action_id, action_provider):
        """Return the action index owned by an action provider or -1 is the
        action doesn't exist.
        """
        action_index = 0
        for action in action_provider.listActions():
            if action.id == action_id:
                return action_index
            action_index += 1
        return -1

    def addAction(self, object, properties):
        """Adds an action to an object

        Fixes up some properties first.
        """

        # ActionInformation.__init__() uses 'permissions' as a
        # parameter, but addAction() uses 'permission'. We will
        # allow both.
        if properties.has_key('permissions'):
            properties['permission'] = properties['permissions']
            del properties['permissions']
        # For backward compatibility, visible should default to 1:
        if not properties.has_key('visible'):
            properties['visible'] = 1
        # And category to 'object':
        if not properties.has_key('category'):
            properties['category'] = 'object'
        # Condition must be present, even empty
        if not properties.has_key('condition'):
            properties['condition'] = ''
        # Ensure action is TALES
        action = properties.get('action')
        if action is not None and ':' not in action:
            properties['action'] = 'string:${object_url}/'+action

        object.addAction(**properties)

    def verifyAction(self, tool, **kw):
        result = ' Verifying action %s...' % kw['id']
        if self.hasAction(tool, kw['id']):
            result += 'exists.'
        else:
            self.addAction(self.portal[tool], kw)
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
                self.log(" Deleting action %s from %s" % (ac, tool))
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
                # Hack to Fix CMF 1.5 incompatibility
                if path.startswith("Products/"):
                    path = path[len("Products/"):]
                createDirectoryView(self.portal.portal_skins, path, skin)
                self.log("  Creating skin")

        if skin_installed:
            all_skins = self.portal.portal_skins.getSkinPaths()
            for skin_name, skin_path in all_skins:
                # Plone skin names are needed to install
                # CPSIO skins on a Plone site when exporting a Plone site.
                if skin_name not in  ['Basic',
                                      'CPSSkins',
                                      'Plone Default',
                                      'Plone Tableless']:
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
    def addZCTextIndexLexicon(self, id, title=''):
        """Add a ZCTextIndex Lexicon."""
        self.log(' Adding a ZCTextIndex Lexicon %s' % id)
        ct = self.portal.portal_catalog
        if id in ct.objectIds():
            self.logOK()
            return
        class Struct:
            def __init__(self, **kw):
                for k, v in kw.items():
                    setattr(self, k, v)
        elems = (Struct(group='Case Normalizer',
                        name='Case Normalizer',
                        ),
                 Struct(group='Stop Words',
                        name=" Don't remove stop words"
                        #name="Remove listed and single char words"
                        #name="Remove listed stop words only"
                        ),
                 Struct(group='Word Splitter',
                        name='Whitespace splitter',
                        ))
        manage_addLexicon(ct, id, title, elems)
        self.log(' Added')

    def addPortalCatalogIndex(self, id, type, extra=None):
        """Adds an index on portal_catalog."""
        self.log(' Portal_catalog verify index %s: %s' % (type, id))
        ct = self.portal.portal_catalog
        if id in ct.indexes():
            current_index_type = ct._catalog.getIndex(id).meta_type
            if current_index_type == type:
                self.logOK()
                return
            elif type == 'ZCTextIndex' and current_index_type != 'TextIndex':
                # we only turn TextIndex into ZCTextIndex keeping NG
                self.log('  keeping index of type %s.' % current_index_type)
                return
            self.log('  Deleting old index')
            ct.delIndex(id)
        self.log('  Adding index')
        if type == 'ZCTextIndex':
            index = ZCTextIndex(id, extra=extra, caller=ct)
            ct._catalog.addIndex(id, index)
        else:
            ct.addIndex(id, type, extra)
        if type == 'TopicIndex' and extra:
            index = ct._catalog.getIndex(id)
            for filter in extra:
                index.addFilteredSet(filter.id,
                                     'PythonFilteredSet',
                                     filter.expr)
                self.log('   Adding filterSet %s for TopicIndex %s' %
                         (filter.id, id))
        self.flagCatalogForReindex(id)

    def addPortalCatalogMetadata(self, id, default_value=None):
        """Adds a metadata in the portal_catalog."""
        self.log(' Portal_catalog verify Metadata: %s, default value: %s'
                 % (id, default_value))
        ct = self.portal.portal_catalog
        if not ct._catalog.schema.has_key(id):
            self.log('  Adding metadata')
            ct.addColumn(id, default_value)
            self.flagCatalogForReindexMetadata(id)

    def flagCatalogForReindex(self, indexid=None):
        if indexid is None:
            # Reindex all catalog
            self.portal._v_reindex_catalog = 1
            return
        indexes = getattr(self.portal, '_v_changed_indexes', [])
        indexes.append(indexid)
        self.portal._v_changed_indexes = indexes

    def flagCatalogForReindexMetadata(self, metadataid=None):
        # we need to rebuild all metadata
        self.portal._v_reindex_catalog_metadata = 1

    #
    # Portal_types management methods
    #
    def allowContentTypes(self, allowed_types, allowed_in):
        """Allow a list of types in a list of types

        makes sure that the types in the list allowed_types will be allowed
        as content types in the types in the list allowed_in
        """
        if isinstance(allowed_types, StringType):
            allowed_types = (allowed_types,)
        if isinstance(allowed_in, StringType):
            allowed_in = (allowed_in,)
        ttool = self.portal.portal_types
        for type in allowed_in:
            workspaceACT = list(ttool[type].allowed_content_types)
            for ptype in allowed_types:
                if ptype not in  workspaceACT:
                    workspaceACT.append(ptype)
            ttool[type].allowed_content_types = workspaceACT

    def verifyContentTypes(self, type_dict, destructive=0):
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
                if destructive:
                    self.log(" Deleting %s"  %ptype)
                    ttool.manage_delObjects([ptype])
                else:
                    self.logOK()
                    continue

            self.log("  Adding")
            ttool.manage_addTypeInformation(
                id=ptype,
                add_meta_type=typeinfo['add_meta_type'],
                typeinfo_name=typeinfo['typeinfo_name'])
            if typeinfo.has_key('properties'):
                ttool[ptype].manage_changeProperties(
                    **typeinfo['properties'])

            self.allowContentTypes(
                typeinfo.get('allowed_content_types', ()), ptype)

    def cleanupPortalTypes(self, types_to_keep=[], types_to_delete=[]):
        """Delete unneeded portal types"""
        ptypes = self.portal.portal_types
        current_types = ptypes.objectIds()
        if types_to_keep:
            types_to_delete = [ t for t in current_types
                                  if not t in types_to_keep]
        else:
            types_to_delete = [ t for t in current_types
                                  if t in types_to_delete]
        ptypes.manage_delObjects(types_to_delete)


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
        ctool = self.getTool('portal_calendar', None)
        if ctool is None:
            return

        current_types = tuple(ctool.calendar_types)
        for tid in type_ids:
            if tid not in current_types:
                self.log(" Calendar type %s added" % tid)
                current_types += (tid,)
        ctool.calendar_types = current_types

    def removeCalendarTypes(self, type_ids):
        ctool = self.getTool('portal_calendar', None)
        if ctool is None:
            return

        current_types = list(ctool.calendar_types)
        for tid in type_ids:
            if tid in current_types:
                self.log(" Calendar type %s removed" % tid)
                current_types.remove(tid)
        ctool.calendar_types = tuple(current_types)

    def verifyTool(self, toolid, product, meta_type, ttype=None):
        """Verify is there is a tool on the portal from the given product with
        the given meta_type and the (optional) given type.

        If there isn't any such tool, it creates one, in place of another tool
        if needed.
        """
        self.log('Verifying tool %s' % toolid)
        if self.portalHas(toolid):
            tool = self.getTool(toolid)
            if (ttype is not None
                and tool.meta_type == meta_type and type(tool) == ttype
                or tool.meta_type == meta_type):
                self.logOK()
                return
            self.log(" Deleting old %s tool" % tool.meta_type)
            self.portal.manage_delObjects([toolid])
        self.log(" Adding")
        self.portal.manage_addProduct[product].manage_addTool(meta_type)

    def verifyVHM(self):
        """Verify that a Virtual Host Monster exist at root of Zope.

        That's not necessary, but admin friendly.
        """
        root = self.portal.getPhysicalRoot()
        if root.objectValues('Virtual Host Monster') == []:
            root.manage_addProduct['SiteAccess'].manage_addVirtualHostMonster(id='VirtualHostMonster')
            self.log("Virtual Host Monster created")
        else:
            self.log("Virtual Host Monster found ")
