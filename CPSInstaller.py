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
        if not self.is_main_installer:
            return
        self._cmf_finalize()
        self._cps_finalize()

    def _cps_finalize(self):
        changed_trees = getattr(self.portal, '_v_changed_tree_caches', [])
        if changed_trees:
            self.log('Rebuilding Tree cache')
            trtool = self.portal.portal_trees
            for tree in changed_trees:
                trtool[tree].manage_rebuild()

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

    def setupWfStates(self, workflow, states):
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

    def setupWfTransitions(self, workflow, transitions):
        existing_transitions = workflow.transitions.objectIds()
        for transid, transdef in transitions.items():
            if transid in existing_transitions:
                continue
            self.log(' Adding transition %s' % transid)
            workflow.transitions.addTransition(transid)
            trans = workflow.transitions.get(transid)
            trans.setProperties(**transdef)

    def setupWfScripts(self, workflow, scripts):
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

    def setupWfVariables(self, workflow, variables):
        existing_vars = workflow.variables.objectIds()
        for varid, vardef in variables.items():
            if varid in existing_vars:
                continue
            self.log(' Adding variable %s' % varid)
            workflow.variables.addVariable(varid)
            var = workflow.variables[varid]
            var.setProperties(**vardef)

    def setupWorkflow(self, wfdef={}, wfstates={}, wftransitions={},
                      wfscripts={}, wfvariables={}):
        self.log("Setup workflow %s" % wfdef['wfid'])
        wf = self.createWorkflow(wfdef)
        if wf is None:
            return

        self.setupWfStates(wf, wfstates)
        self.setupWfTransitions(wf, wftransitions)
        self.setupWfScripts(wf, wfscripts)
        self.setupWfVariables(wf, wfvariables)
        self.log(' Done')

    def setupLocalWorkflowChains(self, object, wfchains):
        wfc = getattr(object, '.cps_workflow_configuration')
        for portal_type, chain in wfchains.items():
          wfc.manage_addChain(portal_type=portal_type, chain=chain)

    #
    # Flexible Type installation
    #

    def addFlexibleTypes(self, type_data):
        ttool = self.getTool('portal_types')
        ptypes_installed = ttool.objectIds()
        display_in_cmf_calendar = []

        for ptype, data in type_data.items():
            self.log(" Adding type '%s'" % ptype)
            if ptype in ptypes_installed:
                self.logOK()
                continue
            ti = ttool.addFlexibleTypeInformation(id=ptype)
            if data.get('display_in_cmf_calendar'):
                display_in_cmf_calendar.append(ptype)
                del data['display_in_cmf_calendar']
            ti.manage_changeProperties(**data)

        self.addCalendarTypes(display_in_cmf_calendar)


    # This will go away, when registration with dependancies are implemented
    def runExternalUpdater(self, id, title, module, script, method):
        try:
            if not self.portalhas(id):
                __import__(module)
                self.log('Adding %s' % title)
                script = ExternalMethod(id, title, script, method)
                self.portal._setObject(id, script)
            self.log(self.portal[id]())
        except ImportError:
            pass

    #
    # CPSSchemas installation
    #
    def addSchemas(self, schemas):
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

    def addWidgets(self, widgets):
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

    def addLayouts(self, layouts):
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

    def addVocabularies(self, vocabularies):
        """Adds vocabularies if they don't exist

        The vocabularies parameter is a dictionary of vocabulary definitions.
        The vocabulary definition is what you get when you go to the 'Export'
        tab of a vocabulary.
        """
        vtool = self.portal.portal_vocabularies
        for id, info in vocabularies.items():
            self.log(" Adding vocabulary %s" % id)
            if id in vtool.objectIds():
                if getattr(vtool, id).isUserModified():
                    self.log("  Keeping, as it has been modified.")
                    self.log("  Delete it manually if needed.")
                    continue
                else:
                    self.log("  Deleting.")
                    vtool.manage_delObjects([id])
                self.log("  Installing.")
                type = info.get('type', 'CPS Vocabulary')
                vtool.manage_addCPSVocabulary(id, type, **info['data'])

    #
    # Internationalization support
    #

    def setupTranslations(self, product_name):
        """Import .po files into the Localizer/default Message Catalog."""
        mcat = self.portal.Localizer.default
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

    def verifyMessageCatalog(self, catalog_id, title):
        """Sets up a spezialized message catalog for your product"""
        self.log('Verifying message catalog %s' % catalog_id)
        localizer = self.portal['Localizer']
        # MessageCatalog
        if catalog_id in localizer.objectIds():
            self.logOK()
            return

        languages = localizer.get_supported_languages()
        localizer.manage_addProduct['Localizer'].manage_addMessageCatalog(
            id=catalog_id,
            title=title,
            languages=languages,
        )
        self.log('    Created')

    #
    # Portal_trees
    #

    def addTreeCacheType(self, treename, type_name, meta_type):
        self.log('Verifying %s type in %s tree cache' % (type_name, treename))
        trtool = self.portal.portal_trees
        WTN = list(trtool[treename].type_names)
        if type_name not in WTN:
            WTN.append(type_name)
            trtool[treename].type_names = WTN
            self.flagRebuildTreeCache(treename)
        WMT = list(trtool[treename].meta_types)
        if meta_type not in WMT:
            WMT.append(type_name)
            trtool[treename].meta_types = WMT
            self.flagRebuildTreeCache(treename)

    def flagRebuildTreeCache(self, treename):
        trees = getattr(self.portal, '_v_changed_tree_caches', [])
        if treename not in trees:
            trees.append(treename)
            self.portal._v_changed_tree_caches = trees

