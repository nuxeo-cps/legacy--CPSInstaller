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
from Products.CMFCore.utils import getToolByName

from CMFInstaller import CMFInstaller

class CPSInstaller(CMFInstaller):

    #
    # Workflow methods:
    #

    def createWorkflow(self, wfdef):
        wftool = self.portal.portal_workflow
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

    #
    # Flexible Type installation
    #

    def addFlexibleTypes(self, type_data):
        ttool = getToolByName(self.portal, 'portal_types')
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

    #
    # Internationalization support
    #

    def setupTranslations(self):
        """Import .po files into the Localizer/default Message Catalog."""
        # Is this CMF or CPS? Hummm...
        mcat = self.portal.Localizer.default
        self.log(" Checking available languages")
        podir = os.path.join('Products', self.product_name)
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


