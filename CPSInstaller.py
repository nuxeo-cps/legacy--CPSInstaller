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
from types import TupleType, ListType

from App.Extensions import getPath
from Acquisition import aq_base
from zLOG import LOG, INFO, DEBUG
from Products.PythonScripts.PythonScript import PythonScript
from Products.ExternalMethod.ExternalMethod import ExternalMethod

from CMFInstaller import CMFInstaller

class CPSInstaller(CMFInstaller):

    def finalize(self):
        if not self.isMainInstaller():
            return
        self._cps_finalize()
        self._cmf_finalize()

    def _cps_finalize(self):
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
                self.portal.acl_users.userFolderAddRole(role)
                self.log(" Add role %s" % role)

    #
    # Workflow methods:
    #

    def createWorkflow(self, wfdef):
        wftool = self.getTool('portal_workflow')
        wfid = wfdef['wfid']

        self.log(' Creating workflow %s' % wfid)
        if wfid in wftool.objectIds():
            self.logOK()
            return None

        # Create and set up workflow
        wftool.manage_addWorkflow(id=wfid,
                                  workflow_type='cps_workflow (Web-configurable workflow for CPS)')

        wf = wftool[wfid]
        if wfdef.has_key('permissions'):
            for p in wfdef['permissions']:
                wf.addManagedPermission(p)

        if wfdef.has_key('state_var'):
            wf.variables.setStateVar(wfdef['state_var'])

        return wf

    def verifyWfStates(self, workflow, states):
        existing_states = workflow.states.objectIds()
        for stateid, statedef in states.items():
            if stateid in existing_states:
                continue
            self.log(' Adding state %s' % stateid)
            workflow.states.addState(stateid)
            state = workflow.states.get(stateid)
            state.setProperties(title=statedef['title'], transitions=statedef['transitions'])
            for permission in statedef['permissions'].keys():
                state.setPermission(permission, 0, statedef['permissions'][permission])

    def verifyWfTransitions(self, workflow, transitions):
        existing_transitions = workflow.transitions.objectIds()
        for transid, transdef in transitions.items():
            if transid in existing_transitions:
                continue
            self.log(' Adding transition %s' % transid)
            workflow.transitions.addTransition(transid)
            trans = workflow.transitions.get(transid)
            trans.setProperties(**transdef)

    def verifyWfScripts(self, workflow, scripts):
        existing_scripts = workflow.states.objectIds()
        for scriptid, scriptdef in scripts.items():
            if scriptid in existing_scripts:
                continue
            self.log(' Adding script %s' % scriptid)
            workflow.scripts._setObject(scriptid, PythonScript(scriptid))
            script = workflow.scripts[scriptid]
            script.write(scriptdef['script'])
            for attribute in ('title', '_proxy_roles', '_owner'):
                if scriptdef.has_key(attribute):
                    setattr(script, attribute, scriptdef[attribute])

    def verifyWfVariables(self, workflow, variables):
        existing_vars = workflow.variables.objectIds()
        for varid, vardef in variables.items():
            if varid in existing_vars:
                continue
            self.log(' Adding variable %s' % varid)
            workflow.variables.addVariable(varid)
            var = workflow.variables[varid]
            var.setProperties(**vardef)

    def verifyWorkflow(self, wfdef={}, wfstates={}, wftransitions={},
                      wfscripts={}, wfvariables={}):
        self.log("Setup workflow %s" % wfdef['wfid'])
        wf = self.createWorkflow(wfdef)
        if wf is None:
            return

        self.verifyWfStates(wf, wfstates)
        self.verifyWfTransitions(wf, wftransitions)
        self.verifyWfScripts(wf, wfscripts)
        self.verifyWfVariables(wf, wfvariables)
        self.log(' Done')

    def verifyLocalWorkflowChains(self, object, wfchains):
        """Sets up the local workflows on object.

        wfchains = {
            '<Portal Type>': '<workflow_id>',
        }
        """
        self.log('Verifying local workflow for %s' % object.getId())
        if not '.cps_workflow_configuration' in object.objectIds():
            self.log("  Adding workflow configuration to %s" % object.getId())
            object.manage_addProduct['CPSCore'].addCPSWorkflowConfiguration()
        wfc = getattr(object, '.cps_workflow_configuration')
        for portal_type, chain in wfchains.items():
            if not wfc.getPlacefulChainFor(portal_type):
                wfc.manage_addChain(portal_type=portal_type, chain=chain)

    #
    # Flexible Type installation
    #

    def verifyFlexibleTypes(self, type_data):
        ttool = self.getTool('portal_types')
        ptypes_installed = ttool.objectIds()
        display_in_cmf_calendar = []

        for ptype, data in type_data.items():
            self.log(" Adding type '%s'" % ptype)
            if ptype in ptypes_installed:
                if ttool[ptype].meta_type == 'Factory-based Type Information':
                    # Old CMF type that needs to be upgraded.
                    self.ttool.manage_delObjects([ptype])
                    self.log("  Replacing...")
                else:
                    self.logOK()
                    continue

            ti = ttool.addFlexibleTypeInformation(id=ptype)
            if data.get('display_in_cmf_calendar'):
                display_in_cmf_calendar.append(ptype)
                del data['display_in_cmf_calendar']
            ti.manage_changeProperties(**data)
            self.log("  Added")

            if data.has_key('actions'):
                self.log("    Setting actions")
                nb_action = len(ti.listActions())
                ti.deleteActions(selections=range(nb_action))
                for a in data['actions']:
                    ti.addAction(a['id'],
                                 a['name'],
                                 a['action'],
                                 a.get('condition', ''),
                                 a['permissions'][0],
                                 'object',
                                 visible=a.get('visible',1))

        self.addCalendarTypes(display_in_cmf_calendar)


    # This will go away, when registration with dependancies are implemented
    def runExternalUpdater(self, id, title, module, script, method):
        try:
            if not self.portalHas(id):
                __import__('Products.' + module)
                self.log('Adding %s' % title)
                script = ExternalMethod(id, title, '%s.%s' % (module, script), method)
                self.portal._setObject(id, script)
            self.log(self.portal[id]())
        except ImportError:
            self.log('WARNING: Product %s could not be imported!'
                     ' Installer was not called.' % module)
            pass

    #
    # CPSSchemas installation
    #
    def verifySchemas(self, schemas):
        """Adds schemas if they don't exist

        The schemas parameter is a dictionary of schema definitions.
        The schema definition is what you get when you go to the 'Export'
        tab of a schema.
        """
        self.log("Verifiying schemas")
        stool = self.getTool('portal_schemas')
        for id, info in schemas.items():
            self.log(" Adding schema %s" % id)
            if id in stool.objectIds():
                self.logOK()
                continue
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
        wtool = self.portal.portal_widget_types
        for id, info in widgets.items():
            self.log(" Adding widget %s" % id)
            if id in wtool.objectIds():
                self.logOK()
                continue
            widget = wtool.manage_addCPSWidgetType(id, info['type'])
            widget.manage_changeProperties(**info['data'])

    def verifyLayouts(self, layouts):
        """Adds layouts if they don't exist

        The layouts parameter is a dictionary of layout definitions.
        The layout definition is what you get when you go to the 'Export'
        tab of a layout.
        """
        ltool = self.portal.portal_layouts
        for id, info in layouts.items():
            self.log(" Adding layout %s" % id)
            if id in ltool.objectIds():
                self.logOK()
                continue
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
        vtool = self.portal.portal_vocabularies
        for id, info in vocabularies.items():
            self.log(" Adding vocabulary %s" % id)
            if id in vtool.objectIds():
                p = vtool[id]
                self.log(str(p.meta_type) )
                self.log(str(p.getId()) )

                if p.isUserModified():
                    self.log("  Keeping, as it has been modified.")
                    self.log("  Delete it manually if needed.")
                    continue
                else:
                    self.log("  Deleting.")
                    vtool.manage_delObjects([id])
                self.log("  Installing.")
                vtype = info.get('type', 'CPS Vocabulary')
                vtool.manage_addCPSVocabulary(id, vtype, **info['data'])

    #
    # Internationalization support
    #

    def setupTranslations(self, product_name=None, message_catalog='default'):
        """Import .po files into the Localizer/default Message Catalog."""
        if product_name is None:
            product_name = self.product_name
        mcat = self.portal.Localizer[message_catalog]
        self.log(" Checking available languages")
        podir = os.path.join('Products', product_name)
        popath = getPath(podir, 'i18n')
        if popath is None:
            self.log(" !!! Unable to find .po dir")
        else:
            self.log("  Checking installable languages")
            avail_langs = mcat.get_languages()
            self.log("    Available languages: %s" % str(avail_langs))
            for file in os.listdir(popath):
                if file.endswith('.po'):
                    m = match('^.*([a-z][a-z])\.po$', file)
                    if m is None:
                        self.log('    Skipping bad file %s' % file)
                        continue
                    lang = m.group(1)
                    if lang in avail_langs:
                        lang_po_path = os.path.join(popath, file)
                        lang_file = open(lang_po_path)
                        self.log("    Importing %s into '%s' locale" % (file, lang))
                        mcat.manage_import(lang, lang_file)
                    else:
                        self.log('    Skipping not installed locale for file %s' % file)

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
                languages=languages,
            )

        translation_service = self.portal.translation_service
        domains = [info[0] for info in translation_service.getDomainInfo()]
        if not catalog_id in domains:
            self.log('  Adding message domain')
            translation_service.manage_addDomainInfo(catalog_id,
                                          'Localizer/'+catalog_id)

        self.flagCatalogForReindex()

    #
    # Portal_trees
    #

    def verifyTreeCacheTypes(self, treename, type_names=(), meta_types=()):
        self.log('Verifying %s type(s) in %s tree cache' % (str(type_names), treename))
        tree = self.portal.portal_trees[treename]
        old_type_names = list(tree.type_names)
        old_meta_types = list(tree.meta_types)
        tree.manage_changeProperties(
            type_names=old_type_names + list(type_names),
            meta_types=old_meta_types + list(meta_types))
        if old_type_names != tree.type_names or \
           old_meta_types != tree.meta_types:
                self.flagRebuildTreeCache(treename)

    def flagRebuildTreeCache(self, treename):
        trees = getattr(self.portal, '_v_changed_tree_caches', [])
        if treename not in trees:
            trees.append(treename)
            self.portal._v_changed_tree_caches = trees

    #
    # Boxes
    #

    def verifyBoxContainer(self, object=None):
        if object is None:
            object = self.portal
        idbc = self.portal.portal_boxes.getBoxContainerId(object)
        self.log("Verifying box container /%s" % idbc )
        if not hasattr(object,idbc):
            self.log("   Creating")
            object.manage_addProduct['CPSDefault'].addBoxContainer()

    def verifyBoxes(self, boxes, object=None):
        if object is None:
            object = self.portal
        self.verifyBoxContainer(object)
        self.log('Verifying boxes on %s' % object.getId())
        ttool = self.getTool('portal_types')
        idbc = self.portal.portal_boxes.getBoxContainerId(self.portal)
        box_container = object[idbc]
        existing_boxes = box_container.objectIds()
        for box in boxes.keys():
            if box in existing_boxes:
                continue
            self.log("   Creation of box: %s" % box)
            apply(ttool.constructContent,
                (boxes[box]['type'], box_container,
                box, None), {})
            ob = getattr(box_container, box)
            ob.manage_changeProperties(**boxes[box])


    #
    # Misc stuff
    #

    def verifyDirectories(self, directories):
        dirtool = self.portal.portal_directories
        for id, info in directories.items():
            self.log(" Directory %s" % id)
            if id in dirtool.objectIds():
                self.logOK()
                continue
            self.log("  Installing.")
            directory = dirtool.manage_addCPSDirectory(id, info['type'])
            directory.manage_changeProperties(**info['data'])
            for role, expr in info.get('entry_local_roles', ()):
                res = directory.addEntryLocalRole(role, expr)
                if res:
                    raise ValueError(res)

    def verifyEventSubscribers(self, subscribers):
        objs = self.portal.portal_eventservice.objectValues()
        current_subscribers = [obj.subscriber for obj in objs]
        for subscriber in subscribers:
            self.log("Verifying Event service subscriber %s" % subscriber['subscriber'])
            if subscriber['subscriber'] in current_subscribers:
                self.logOK()
                continue
            self.log(" Adding")
            self.portal.portal_eventservice.manage_addSubscriber(**subscriber)
