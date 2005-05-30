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
from re import match
from types import TupleType, ListType
from ConfigParser import ConfigParser, NoOptionError, NoSectionError

from App.Extensions import getPath
from Acquisition import aq_base
from zLOG import LOG, INFO, DEBUG
from Products.PythonScripts.PythonScript import PythonScript
from Products.ExternalMethod.ExternalMethod import ExternalMethod

try:
    from Products.CMFQuickInstallerTool.QuickInstallerTool import \
        addQuickInstallerTool
    _quickinstaller_support = 1
except ImportError:
    _quickinstaller_support = 0

from Products.CMFCore.utils import getToolByName

from CMFInstaller import CMFInstaller

class CPSInstaller(CMFInstaller):

    WORKSPACES_ID = 'workspaces'
    SECTIONS_ID = 'sections'

    def finalize(self):
        if not self.isMainInstaller():
            return
        self._CPSFinalize()
        self._CMFFinalize()

    def _CPSFinalize(self):
        changed_trees = getattr(self.portal, '_v_changed_tree_caches', [])
        if changed_trees:
            self.log('Rebuilding Tree cache')
            trtool = self.portal.portal_trees
            for tree in changed_trees:
                trtool[tree].manage_rebuild()

    #
    # Overrides
    #
    def verifyRoles(self, roles):
        already = self.portal.valid_roles()
        for role in roles:
            if role not in already:
                try:
                    self.portal.acl_users.userFolderAddRole(role)
                except AttributeError:
                    # Use standard CMF method, needed when using CPSUserFolder
                    self.portal._addRole(role)
                self.log(" Add role %s" % role)

    #
    # Workflow methods:
    #
    def createWorkflow(self, wfdef):
        wftool = self.getTool('portal_workflow')
        wfid = wfdef['wfid']

        self.log(' Creating workflow %s' % wfid)
        if wfid not in wftool.objectIds():
            wftool.manage_addWorkflow(id=wfid,
              workflow_type='cps_workflow (Web-configurable workflow for CPS)')

        wf = wftool[wfid]
        if hasattr(wf, 'isUserModified') and wf.isUserModified():
            self.log('WARNING: The workflow permissions are modified and'
                ' will not be changed. Delete manually if needed.')
            return wf

        wf.permissions = ()
        if wfdef.has_key('permissions'):
            for p in wfdef['permissions']:
                wf.addManagedPermission(p)
        return wf

    def verifyWfStates(self, workflow, states):
        existing_states = workflow.states.objectIds()
        for stateid, statedef in states.items():
            if stateid in existing_states:
                ob = workflow.states[stateid]
                if hasattr(ob, 'isUserModified') and ob.isUserModified():
                    self.log('WARNING: The workflow state is modified and will'
                             ' not be changed. Delete manually if needed.')
                    continue
                else:
                    self.log('   Deleting old definition')
                    workflow.states.manage_delObjects([stateid])
            self.log(' Adding state %s' % stateid)
            workflow.states.addState(stateid)
            state = workflow.states.get(stateid)

            # Set state permissions
            for permission in statedef['permissions'].keys():
                state.setPermission(permission, 0,
                                    statedef['permissions'][permission])

            # Set properties
            state.setProperties(
                **statedef)

    def verifyWfTransitions(self, workflow, transitions):
        existing_transitions = workflow.transitions.objectIds()
        for transid, transdef in transitions.items():
            if transid in existing_transitions:
                ob = workflow.transitions[transid]
                if hasattr(ob, 'isUserModified') and ob.isUserModified():
                    self.log('WARNING: The workflow transition is modified and'
                             ' will not be changed. Delete manually if needed.')
                    continue
                else:
                    self.log('   Deleting old definition')
                    workflow.transitions.manage_delObjects([transid])
            self.log(' Adding transition %s' % transid)
            workflow.transitions.addTransition(transid)
            trans = workflow.transitions.get(transid)
            trans.setProperties(**transdef)

    def verifyWfScripts(self, workflow, scripts):
        existing_scripts = workflow.scripts.objectIds()
        for scriptid, scriptdef in scripts.items():
            if scriptid in existing_scripts:
                ob = workflow.scripts[scriptid]
                if hasattr(ob, 'isUserModified') and ob.isUserModified():
                    self.log('WARNING: The workflow script is modified and'
                             ' will not be changed. Delete manually if needed.')
                    continue
                else:
                    self.log('   Deleting old definition')
                    workflow.scripts.manage_delObjects([scriptid])
            self.log(' Adding script %s' % scriptid)
            workflow.scripts._setObject(scriptid, PythonScript(scriptid))
            script = workflow.scripts[scriptid]
            script.write(scriptdef['script'])
            for attribute in ('title', '_proxy_roles', '_owner'):
                if scriptdef.has_key(attribute):
                    setattr(script, attribute, scriptdef[attribute])

    def verifyWfVariables(self, workflow, variables, state_var=None):
        existing_vars = workflow.variables.objectIds()
        for varid, vardef in variables.items():
            if varid in existing_vars:
                ob = workflow.variables[varid]
                if hasattr(ob, 'isUserModified') and ob.isUserModified():
                    self.log('WARNING: The workflow variable is modified and'
                             ' will not be changed. Delete manually if needed.')
                    continue
                else:
                    self.log('   Deleting old definition')
                    workflow.variables.manage_delObjects([varid])
            self.log(' Adding variable %s' % varid)
            workflow.variables.addVariable(varid)
            var = workflow.variables[varid]
            var.setProperties(**vardef)

        if state_var:
            if (hasattr(workflow.variables, 'isUserModified')
                and workflow.variables.isUserModified()):
                self.log('WARNING: The workflow state variable is modified and'
                        ' will not be changed. Change manually if needed.')
            else:
                workflow.variables.setStateVar(state_var)

    def verifyWorkflow(self, wfdef={}, wfstates={}, wftransitions={},
                       wfscripts={}, wfvariables={}):
        self.log("Setup workflow %s" % wfdef['wfid'])
        wf = self.createWorkflow(wfdef)
        if wf is None:
            return

        self.verifyWfVariables(wf, wfvariables,
                               state_var=wfdef.get('state_var'))
        self.verifyWfStates(wf, wfstates)
        self.verifyWfTransitions(wf, wftransitions)
        self.verifyWfScripts(wf, wfscripts)
        self.log(' Done')

    def verifyLocalWorkflowChains(self, object, wfchains, destructive=0,
                                  under_sub_add=None):
        """Sets up the local workflows on object.

        wfchains = {
            '<Portal Type>': '<workflow_id>',
        }

        if under_sub_add is set a Below Workflow Chain is added
        """
        self.log('Verifying local workflow for %s' % object.getId())
        if not '.cps_workflow_configuration' in object.objectIds():
            self.log("  Adding workflow configuration to %s" % object.getId())
            object.manage_addProduct['CPSWorkflow'].addConfiguration()
        wfc = getattr(object, '.cps_workflow_configuration')
        for portal_type, chain in wfchains.items():
            if not wfc.getPlacefulChainFor(portal_type):
                wfc.manage_addChain(portal_type=portal_type, chain=chain,
                                    under_sub_add=under_sub_add)
            else:
                if destructive:
                    try:
                        wfc.delChain(portal_type=portal_type)
                    except KeyError:
                        # Here the chain doesn't exist yet
                        pass
                    wfc.manage_addChain(portal_type=portal_type, chain=chain,
                                        under_sub_add=under_sub_add)

    #
    # Flexible Type installation
    #
    def verifyFlexibleTypes(self, type_data, doc_roots={}):
        ttool = self.getTool('portal_types')
        ptypes_installed = ttool.objectIds()
        display_in_cmf_calendar = []

        for ptype, data in type_data.items():
            self.log(" Adding type '%s'" % ptype)
            if ptype in ptypes_installed:
                ob = ttool[ptype]
                if (ob.meta_type != 'Factory-based Type Information'
                    and hasattr(ob, 'isUserModified') and ob.isUserModified()):
                    self.log('WARNING: The type is modified and will not be '
                             'changed. Delete manually if needed.')
                    continue
                else:
                    self.log('   Deleting old definition')
                    ttool.manage_delObjects([ptype])

            ti = ttool.addFlexibleTypeInformation(id=ptype)

            if data.has_key('actions'):
                self.log("    Setting actions")
                nb_action = len(ti.listActions())
                ti.deleteActions(selections=range(nb_action))
                for a in data['actions']:
                    self.addAction(ti, a)

            if data.has_key('actions_add'):
                self.log("    Adding actions")
                for a in data['actions_add']:
                    self.addAction(ti, a)

            if data.get('display_in_cmf_calendar'):
                display_in_cmf_calendar.append(ptype)
                del data['display_in_cmf_calendar']
            if data.get('use_content_status_history'):
                self.addAction(ti, {
                    'id': 'status_history',
                    'name': 'action_status_history',
                    'action': 'content_status_history',
                    'permission': ('View',),
                    'condition': 'not:portal/portal_membership/isAnonymousUser',
                    'category': 'workflow',
                    })
                del data['use_content_status_history']
            ti.manage_changeProperties(**data)
            self.log("  Added")
        self.addCalendarTypes(display_in_cmf_calendar)
        if doc_roots:
            self.log("Updating workflow associations")
            self.verifyWorkflowAssociations(type_data, doc_roots)

    def verifyWorkflowAssociations(self, type_data, doc_roots):
        '''
        type_data is a structure as the one returned by getDocumentTypes;
        doc_roots represents the document roots in the portal tree and
        it is a structure as the one returned by getDocumentRoots
        '''
        wf_chain = {}
        # init wf_chain's elements
        for root_id in doc_roots.keys():
            wf_chain[root_id] = {}

        for ptype, data in type_data.items():
            self.log("Reading workflow associations for %s type..." % ptype)
            wfs = data.get('workflows') or {}
            for root_id, root_data in doc_roots.items():
                wf = wfs.get(root_id)
                if not wf:
                    wf = data.get(root_data.get('wf_attrname'),
                                  root_data.get('content_default_wf'))
                self.log("    ...%s in %s" % (wf, root_data.get('title', root_id)))
                wf_chain[root_id][ptype] = wf
        for root_id in doc_roots.keys():
            self.verifyLocalWorkflowChains(self.portal[root_id], wf_chain[root_id])

    # Use this simpler API instead of runExternalUpdater() whenever possible
    def setupProduct(self, product):
        id = product.lower() + '_installer'
        title = product + ' Installer'
        module = product
        script = 'install'
        method = 'install'
        try:
            self.runExternalUpdater(id, title, module, script, method)

        # FIXME bare except == bad but I don't know what kind of
        # exception is thrown...
        except:
            script = 'Install'
            self.runExternalUpdater(id, title, module, script, method)

    def setupQuickInstaller(self):
        if not self.portalHas('portal_quickinstaller'):
            addQuickInstallerTool(self.portal)

    # XXX: This will go away, when registration with dependancies are
    # implemented
    def runExternalUpdater(self, id, title, module, script, method):
        # First check if we should use the QuickInstaller:
        if _quickinstaller_support:
            self.setupQuickInstaller()
            qtool = self.getTool('portal_quickinstaller')

            try:
                qtool.getInstallMethod(module)
            except AttributeError:
                # No install method found. Go Try with an external script.
                pass
            else:
                # Install if product is not already installed
                if not qtool.isProductInstalled(module):
                    qtool_res = qtool.installProduct(module)
                    self.log("Product %s: %s"%(module, qtool_res,))
                    return

        # No QuickInstaller product, no install method found, or product is
        # already installed.
        try:
            if not self.portalHas(id):
                __import__('Products.' + module)
                self.log('Adding %s' % title)
                script = ExternalMethod(id, title, '%s.%s' % (module, script),
                                        method)
                self.portal._setObject(id, script)
            script = self.portal[id]
            if script.filepath() is None:
                self.log('WARNING: External script for %s could not be called!'
                     ' Product is probably removed.' % module)
                return
            result = script()
            if result:
                self.log(result)
        except ImportError:
            self.log('WARNING: Product %s could not be imported!'
                     ' Installer was not called.' % module)

    #
    # CPSSchemas installation
    #
    def verifySchemas(self, schemas):
        """Adds schemas if they don't exist

        The schemas parameter is a dictionary of schema definitions.
        The schema definition is what you get when you go to the 'Export'
        tab of a schema.
        """
        self.log("Verifying schemas")
        stool = self.getTool('portal_schemas')
        existing_schemas = stool.objectIds()
        for id, info in schemas.items():
            self.log(" Adding schema %s" % id)
            if id in existing_schemas:
                schema = stool['id']
                if (hasattr(schema, 'isUserModified')
                    and schema.isUserModified()):
                    self.log('WARNING: The schema is modified and will not be '
                             'changed. Delete manually if needed.')
                    continue
                else:
                    self.log('   Deleting old definition')
                    stool.manage_delObjects(id)
            schema = stool.manage_addCPSSchema(id)
            for field_id, fieldinfo in info.items():
                self.log("  Field %s." % field_id)
                schema.manage_addField(field_id, fieldinfo['type'],
                                    **fieldinfo['data'])

    def verifyWidgets(self, widgets):
        """Adds widgets if they don't exist

        The widgets parameter is a dictionary of widget definitions.
        The widget definition is what you get when you go to the 'Export'
        tab of a widget.
        """
        self.log("Verifying widgets")
        wtool = self.portal.portal_widget_types
        existing_widgets = wtool.objectIds()
        for id, info in widgets.items():
            self.log(" Adding widget %s" % id)
            if id in existing_widgets:
                ob = wtool[id]
                if hasattr(ob, 'isUserModified') and ob.isUserModified():
                    self.log('WARNING: The widget is modified and will not be '
                             'changed. Delete manually if needed.')
                    continue
                else:
                    self.log('   Deleting old definition')
                    wtool.manage_delObjects([id])
            widget = wtool.manage_addCPSWidgetType(id, info['type'])
            widget.manage_changeProperties(**info['data'])

    def verifyLayouts(self, layouts):
        """Adds layouts if they don't exist

        The layouts parameter is a dictionary of layout definitions.
        The layout definition is what you get when you go to the 'Export'
        tab of a layout.
        """
        self.log("Verifying layouts")
        ltool = self.portal.portal_layouts
        existing_layouts = ltool.objectIds()
        for id, info in layouts.items():
            self.log(" Adding layout %s" % id)
            if id in existing_layouts:
                ob = ltool[id]
                if hasattr(ob, 'isUserModified') and ob.isUserModified():
                    self.log('WARNING: The layout is modified and will not be '
                             'changed. Delete manually if needed.')
                    continue
                else:
                    self.log('   Deleting old definition')
                    ltool.manage_delObjects([id])
            layout = ltool.manage_addCPSLayout(id)
            for widget_id, widgetinfo in info['widgets'].items():
                self.log("  Widget %s" % widget_id)
                layout.manage_addCPSWidget(widget_id, widgetinfo['type'],
                                                    **widgetinfo['data'])
            layout.setLayoutDefinition(info['layout'])
            layout.manage_changeProperties(**info['layout'])

    def verifyVocabularies(self, vocabularies):
        """Adds vocabularies if they don't exist

        The vocabularies parameter is a dictionary of vocabulary definitions.
        The vocabulary definition is what you get when you go to the 'Export'
        tab of a vocabulary.
        """
        self.log("Verifying vocabularies")
        vtool = self.portal.portal_vocabularies
        existing_vocabularies = vtool.objectIds()
        for id, info in vocabularies.items():
            self.log(" Adding vocabulary %s" % id)
            if id in existing_vocabularies:
                p = vtool[id]
                if p.isUserModified():
                    self.log('WARNING: The vocabulary is modified and will not'
                             ' be changed. Delete manually if needed.')
                    continue
                else:
                    self.log("  Deleting.")
                    vtool.manage_delObjects([id])
            self.log("  Installing.")
            vtype = info.get('type', 'CPS Vocabulary')
            vtool.manage_addCPSVocabulary(id, vtype, **info['data'])

    def setupTranslations(self, product_name=None, message_catalog='default'):
        """Load the .po files of the given product.

        The .po files contain the translation messages which are used for the
        i18n of a product.

        The current mechanism relies on Localizer and by default loads the .po
        files into the Localizer/default Message Catalog.
        """
        self.log("Setting up translations")
        if not self.portalHas('Localizer'):
            # No Localizer, or using PlacelessTranslationService
            self.log(" No setup done, no Localizer")
            return
        if product_name is None:
            product_name = self.product_name
        mcat = self.portal.Localizer[message_catalog]
        self.log(" Checking available languages")
        import Products
        product_file = getattr(Products, product_name).__file__
        product_path = os.path.dirname(product_file)
        po_path = os.path.join(product_path, 'i18n')
        if po_path is None:
            self.log(" WARNING Unable to find .po dir at %s" % po_path)
        else:
            self.log("  Checking installable languages")
            avail_langs = mcat.get_languages()
            self.log("    Available languages: %s" % str(avail_langs))
            for file in os.listdir(po_path):
                if file.endswith('.po'):
                    m = match('^.*([a-z][a-z]|[a-z][a-z]_[A-Z][A-Z])\.po$', file)
                    if m is None:
                        self.log('    Skipping bad file %s' % file)
                        continue
                    lang = m.group(1)
                    if lang in avail_langs:
                        lang_po_path = os.path.join(po_path, file)
                        lang_file = open(lang_po_path)
                        self.log("    Importing %s into '%s' locale" % (file,
                                                                        lang))
                        mcat.manage_import(lang, lang_file)
                    else:
                        self.log('    Skipping not installed locale '
                                 'for file %s' % file)

#     # XXX  Here is an alternative wasy of doing this import
#     # I don't know which is best /regebro
#     #
#     portal = self.portal_url.getPortalObject()
#     Localizer = portal['Localizer']
#     defaultCatalog = Localizer.default
#     languages = Localizer.get_supported_languages()
#
#     # computing po files' system directory
#     CPSDefault_path = sys.modules['Products.CPSDefault'].__path__[0]
#     i18n_path = os.path.join(CPSDefault_path, 'i18n')
#     pr("   po files are searched in %s" % i18n_path)
#     pr("   po files for %s are expected" % str(languages))
#
#     # loading po files
#     for lang in languages:
#         po_filename = lang + '.po'
#         pr("   importing %s file" % po_filename)
#         po_path = os.path.join(i18n_path, po_filename)
#         try:
#             po_file = open(po_path)
#         except (IOError, NameError):
#             pr("    %s file not found" % po_path)
#         else:
#             defaultCatalog.manage_import(lang, po_file)
#             pr("    %s file imported" % po_path)


    def verifyMessageCatalog(self, catalog_id, title):
        """Sets up a spezialized message catalog for your product"""
        self.log('Verifying message domain %s' % catalog_id)
        localizer = self.portal['Localizer']
        # MessageCatalog
        if catalog_id not in localizer.objectIds():
            self.log('  Adding message catalog')
            languages = localizer.get_supported_languages()
            localizer.manage_addProduct['Localizer'].manage_addMessageCatalog(
                id=catalog_id,
                title=title,
                languages=languages)

        if catalog_id.lower() != 'default':
            translation_service = self.portal.translation_service
            domains = [info[0] for info in translation_service.getDomainInfo()]
            if not catalog_id in domains:
                self.log('  Adding message domain')
                translation_service.manage_addDomainInfo(catalog_id,
                    'Localizer/' + catalog_id)

    #
    # Portal_trees
    #
    def verifyTreeCacheTypes(self, treename, type_names=(), meta_types=()):
        self.log('Verifying %s type(s) in %s tree cache'
                 % (str(type_names), treename))
        tree = self.portal.portal_trees[treename]
        old_type_names = list(tree.type_names)
        old_meta_types = list(tree.meta_types)
        tree.manage_changeProperties(
            type_names=old_type_names + list(type_names),
            meta_types=old_meta_types + list(meta_types))
        if (old_type_names != tree.type_names
            or old_meta_types != tree.meta_types):
            self.flagRebuildTreeCache(treename)

    def flagRebuildTreeCache(self, treename):
        trees = getattr(self.portal, '_v_changed_tree_caches', [])
        if treename not in trees:
            trees.append(treename)
            self.portal._v_changed_tree_caches = trees

    #
    # Boxes
    #
    def getBoxContainer(self, object, create=0):
        """Get a box container and create it if not found and asked for."""
        idbc = self.portal.portal_boxes.getBoxContainerId(object)
        if not hasattr(aq_base(object), idbc) and create:
            self.log("   Creating %s/%s" %
                (object.absolute_url(relative=1), idbc))
            object.manage_addProduct['CPSBoxes'].addBoxContainer()
        container = getattr(object, idbc)
        return container

    def verifyBoxContainer(self, object=None):
        """Verify the existence of the box container and create it if not
           found."""
        if object is None:
            object = self.portal
        self.log("Verifying box container for %s" %
            (object.absolute_url(relative=1)))
        self.getBoxContainer(object, create=1)

    def verifyBoxes(self, boxes, object=None):
        """Verify the existence of given boxes in the object's box container.
        If not found, a box is instantied. Existing boxes are not affected.

        boxes is a dictionary with keys begins the box ids, and values being
        the dictionary given by the export tab.
        The default object is the portal itself."""
        if object is None:
            object = self.portal
        self.log('Verifying boxes on %s' % object.absolute_url(relative=1))
        box_container = self.getBoxContainer(object, create=1)
        existing_boxes = box_container.objectIds()
        ttool = self.getTool('portal_types')
        for box in boxes.keys():
            if box in existing_boxes:
                if hasattr(box, 'isUserModified') and box.isUserModified():
                    self.log('WARNING: The Box is modified and will not be '
                             'changed. Delete manually if needed.')
                else:
                    self.log("   Deletion of box: %s" % box)
                    box_container._delObject(box)

            self.log("   Creation of box: %s" % box)

            try:
                apply(ttool.constructContent,
                      (boxes[box]['type'], box_container,
                       box, None), {})
            except:
                raise str(box)

            ob = getattr(box_container, box)
            ob.manage_changeProperties(**boxes[box])
            ob.setGuardProperties(props=boxes[box].get('guard_props', {}))

    def deleteBoxes(self, boxes_id, object=None):
        """Delete boxes with the id listed in boxes_id that are located in
           box_container."""
        if object is None:
            object = self.portal
        box_container = self.getBoxContainer(object)
        existing_boxes = box_container.objectIds()

        if type(boxes_id) not in (TupleType, ListType):
            boxes_id = (boxes_id,)

        for box in boxes_id:
            if box in existing_boxes:
                box_container._delObject(box)

    #
    # Portlets
    #

    def getPortletContainer(self, object=None, create=0):
        """Get a portlets container and create it if not found and asked for.
        """
        if object is None:
            object = self.portal
        idpc = self.portal.portal_cpsportlets.getPortletContainerId()
        if not hasattr(aq_base(object), idpc) and create:
            self.log("   Creating %s/%s" %
                (object.absolute_url(relative=1), idpc))
            object.manage_addProduct['CPSPortlets'].addPortletsContainer()
        container = getattr(object, idpc, None)
        return container

    def verifyPortletContainer(self, object=None):
        """Verify the existence of the portlet container and create it if not
           found."""
        if object is None:
            object = self.portal
        self.log("Verifying portlet container for %s" %
            (object.absolute_url(relative=1)))
        return self.getPortletContainer(object, create=1)

    def verifyPortlets(self, portlets=(), object=None):
        """Verify the existence of given portet in the object's portlet
        container. If not found, a portlet is instantiated.
        Existing portlets are not affected.

        'portlets' is a tuple with the dictionaries given by the export tab
        as entries.
        The default object is the portal itself.

        return the list a new portlet ids.
        """

        if object is None:
            object = self.portal

        self.log('Verifying portlets on %s' % object.absolute_url(relative=1))

        portlet_container = self.getPortletContainer(object, create=1)

        ttool = self.getTool('portal_types')

        returned = []
        for new_portlet in portlets:
            existing_portlets = portlet_container.listPortlets()
            updated = 0

            # Check if the portlet needs an update
            identifier = new_portlet.get('identifier')
            if identifier:
                for portlet in existing_portlets:
                    if identifier == portlet.identifier:
                        self.log(" Update of portlet: %s" % portlet)
                        portlet.edit(**new_portlet)
                        portlet_id = portlet.getId()
                        updated = 1
                        continue
            if not updated:
                self.log("   Creation of portlet: %s" % new_portlet)
                portlet_id = self.portal.portal_cpsportlets.createPortlet(
                    ptype_id=new_portlet['type'],
                    context=object,
                    **new_portlet)
            if portlet_id not in returned:
                returned.append(portlet_id)
        return returned

    #
    # Misc stuff
    #

    def verifyDirectories(self, directories):
        dirtool = self.portal.portal_directories
        for id, info in directories.items():
            self.log(" Directory %s" % id)
            if id in dirtool.objectIds():
                dir = dirtool[id]
                if hasattr(dir, 'isUserModified') and dir.isUserModified():
                    self.log('WARNING: The directory is modified and will not '
                             'be changed. Delete manually if needed.')
                else:
                    self.log('   Deleting old definition')
                    dirtool.manage_delObjects([id])
            if id not in dirtool.objectIds():
                dir = dirtool.manage_addCPSDirectory(id, info['type'])
                for role, expr in info.get('entry_local_roles', ()):
                    res = dir.addEntryLocalRole(role, expr)
                    if res:
                        raise ValueError(res)
            if info.has_key('dataFromConfigFile'):
                # you can use dataFromConfigFile to set ldap pwd ex:
                # in your getCustomDirectories:
                #   'dataFromConfigFile': {
                #       'filename': 'ldap.conf',
                #       'section': 'default',
                #       },
                # in your zope instance/etc/ldap.conf
                # [default]
                # ldap_server=dev2
                # ldap_port=10389
                # ldap_bind_dn=cn=Manager,o=gouv,c=fr
                # ldap_bind_password=foobar
                confdata = self.loadConfigurationFile(
                    **info['dataFromConfigFile'])
                info['data'].update(confdata)
            # Adding construction of backing_dir_infos for MetaDirectories
            if info['data'].has_key('backing_dir_infos'):
                bdi = info['data'].get('backing_dir_infos')
                dir.setBackingDirectories(bdi)
                del info['data']['backing_dir_infos']
            dir.manage_changeProperties(**info['data'])

    def verifyEventSubscribers(self, subscribers):
        objs = self.portal.portal_eventservice.objectValues()
        current_subscribers = [obj.subscriber for obj in objs]
        for subscriber in subscribers:
            self.log("Verifying Event service subscriber %s"
                     % subscriber['subscriber'])
            if subscriber['subscriber'] in current_subscribers:
                self.logOK()
                continue
            self.log(" Adding")
            if subscriber.get('activated') is None:
                subscriber['activated'] = True
            self.portal.portal_eventservice.manage_addSubscriber(**subscriber)

    def _getSubscriberObject(self, subscriber_name):
        evtool = getToolByName(self.portal, 'portal_eventservice')
        return evtool.getSubscriberByName(subscriber_name)

    def disableEventSubscriber(self, subscriber_name):
        """Disable an event subscriber by name

        subscriber_name -> portal_trees for instance
        """
        evtool = getToolByName(self.portal, 'portal_eventservice', None)
        if evtool is None:
            return 1
        sub = evtool.getSubscriberByName(subscriber_name)
        if sub is not None:
            sub.disable()
            return 0

    def enableEventSubscriber(self, subscriber_name):
        """Enable an event subscriber by name

        subscriber_name -> portal_trees for instance
        """
        evtool = getToolByName(self.portal, 'portal_eventservice', None)
        if evtool is None:
            return 1
        sub = evtool.getSubscriberByName(subscriber_name)
        if sub is not None:
            sub.enable()
            return 0

    def loadConfigurationFile(self, filename, section='default', default={}):
        # load a configuration file in INSTANCE_HOME/etc
        filename = os.path.join(INSTANCE_HOME, 'etc/' + filename)
        self.log('     loadConfigurationFile: %s' % filename)
        try:
            fh = open(filename, 'r')
        except IOError:
            self.log('loadConfigurationFile: ERROR file %s not found' %
                     filename)
            return default
        parser = ConfigParser()
        parser.readfp(fh)
        fh.close()
        try:
            options = parser.options(section)
        except NoSectionError:
            self.log("loadConfigurationFile: ERROR file %s "
                     "don't have [%s] section" % (filename, section))
            return default
        kw = {}
        for option in options:
            kw[option] = parser.get(section, option)
        return kw
