# (c) 2003 Nuxeo SARL <http://nuxeo.com>
# $Id$

import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Testing import ZopeTestCase

from Products.CMFDefault.Portal import manage_addCMFSite
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

from Products.CPSInstaller.CPSInstaller import CPSInstaller

portal_name = 'test_portal'
ZopeTestCase.installProduct('CMFCore')
ZopeTestCase.installProduct('CMFDefault')
ZopeTestCase.installProduct('MailHost')
ZopeTestCase.installProduct('CPSCore')

class TestCPSInstaller(ZopeTestCase.PortalTestCase):
    """Tests the methods to support CMF installations"""

    def getPortal(self):
        if not hasattr(self.app, portal_name):
            manage_addCMFSite(self.app, portal_name)
        return self.app[portal_name]

    def testCreateWF(self):
        wfdef = {'wfid': 'test_workflow', }

        wfstates = {'work': {
                     'title': 'Work',
                     'transitions':('create_content', 'cut_copy_paste'),
                     'permissions': {},
                    },
                }

        wftransitions = {'create': {
                         'title': 'Initial creation',
                         'new_state_id': 'work',
                         'transition_behavior': (TRANSITION_INITIAL_CREATE, ),
                         'actbox_name': '',
                         'actbox_category': 'workflow',
                         'actbox_url': '',
                         'props': {'guard_permissions':'',
                                   'guard_roles':'Manager; WorkspaceManager; WorkspaceMember; ',
                                   'guard_expr':''},
                        },
                      'create_content': {
                         'title': 'Create content',
                         'new_state_id': 'work',
                         'transition_behavior': (TRANSITION_ALLOWSUB_CREATE,
                                                 TRANSITION_ALLOWSUB_CHECKOUT),
                         'trigger_type': TRIGGER_USER_ACTION,
                         'actbox_name': 'New',
                         'actbox_category': '',
                         'actbox_url': '',
                         'props': {'guard_permissions':'',
                                   'guard_roles':'Manager; WorkspaceManager; WorkspaceMember; ',
                                   'guard_expr':''},
                         },
                    # create_folder is transition which does nothing?
                      'create_folder': {
                         'title': '',
                         'new_state_id': '',
                         'transition_behavior': (),
                         'trigger_type': TRIGGER_USER_ACTION,
                         'actbox_name': '',
                         'actbox_category': '',
                         'actbox_url': '',
                         'props': {'guard_permissions':'',
                                   'guard_roles':'',
                                   'guard_expr':''},
                         },
                     # For the cut/copy/paste feature
                     'cut_copy_paste': {
                         'title': 'Cut/Copy/Paste',
                         'new_state_id': 'work',
                         'transition_behavior': (TRANSITION_ALLOWSUB_DELETE,
                                                 TRANSITION_ALLOWSUB_MOVE,
                                                 TRANSITION_ALLOWSUB_COPY),
                         'clone_allowed_transitions': None,
                         'trigger_type': TRIGGER_USER_ACTION,
                         'actbox_name': 'New',
                         'actbox_category': '',
                         'actbox_url': '',
                         'props': {'guard_permissions':'',
                                   'guard_roles':'Manager; WorkspaceManager; WorkspaceMember; ',
                                   'guard_expr':''},
                     },
                 }


        installer = CPSInstaller(self.portal, 'Installer test')
        installer.setupWorkflow(wfdef, wfstates, wftransitions)
        # Check that the workflow was created
        self.assert_(wfdef['wfid'] in self.portal.portal_workflow.objectIds())

        installer.flush() # Remove the old logs
        installer.setupWorkflow(wfdef, wfstates, wftransitions)
        # Check that the workflow was NOT created
        self.assert_(installer.messages[-1] == ' Already correctly installed')

if __name__ == '__main__':
    framework()
else:
    from unittest import TestSuite, makeSuite
    def test_suite():
        suite = TestSuite()
        suite.addTest(makeSuite(TestCPSInstaller))
        return suite

