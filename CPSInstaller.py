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

from CMFInstaller import CMFInstaller

class CPSInstaller(CMFInstaller):

    #
    # Workflow methods:
    #

    # XXX Uh-oh, this is CPS Specific! Should be moved to CPSInstaller.

    def createWorkflow(self, wfdef):
        wftool = self.portal.portal_workflow
        wfid = wfdef['wfid']

        self.log('Installing workflow %s' % wfid)
        if wfid in wftool.objectIds():
            self.logOK()
            return

        # Create and set up workflow
        wftool.manage_addWorkflow(id=wfid,
                                  workflow_type='cps_workflow (Web-configurable workflow for CPS)')

        wf = wftool[wfid]
        if wfdef.has_key('permissions'):
            for p in wfdef['permissions']:
                wf.addManagedPermission(p)

        if wfdef.has_key('state_var'):
            wf.variables.setStateVar(wfdef['state_var'])

        self.log(' Done')
        return wf


    def setupWorkflow(self, wfdef={}, wfstates={}, wftransitions={},
                      wfscripts={}, wfvariables={}):
        # XXX This method consistently breaks the installer rules as
        # it does not check for the existance of the object before
        # creating them.
        self.log(" Setup workflow %s" % wfdef['wfid'])
        wf = self.createWorkflow(wfdef)
        if wf is None:
            self.logOK()
            return

        existing_states = wf.states.objectIds('Workflow State')
        for stateid, statedef in wfstates.items():
            if stateid in existing_states:
                continue
            self.log('  Adding state %s' % stateid)
            wf.states.addState(stateid)
            state = wf.states.get(stateid)
            state.setProperties(title=statedef['title'], transitions=statedef['transitions'])
            for permission in statedef['permissions'].keys():
                state.setPermission(permission, 0, statedef['permissions'][permission])

        existing_transitions = wf.states.objectIds('Workflow Transition')
        for transid, transdef in wftransitions.items():
            if transid in existing_transitions:
                continue
            self.log('  Adding transition %s' % transid)
            wf.transitions.addTransition(transid)
            trans = wf.transitions.get(transid)
            trans.setProperties(**transdef)

        # XXX still breaks...
        for scriptid, scriptdef in wfscripts.items():
            wf.scripts._setObject(scriptid, PythonScript(scriptid))
            script = wf.scripts[scriptid]
            script.write(scriptdef['script'])
            for attribute in ('title', '_proxy_roles', '_owner'):
                if scriptdef.has_key(attribute):
                    setattr(script, attribute, scriptdef[attribute])

        # XXX still breaks...
        for varid, vardef in wfvariables.items():
            wf.variables.addVariable(varid)
            var = wf.variables[varid]
            var.setProperties(**vardef)

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
            langs = []
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


