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
from Products.CPSInstaller.CMFInstaller import log_ok_message

portal_name = 'test_portal'
ZopeTestCase.installProduct('CMFCore')
ZopeTestCase.installProduct('CMFDefault')
ZopeTestCase.installProduct('CMFCalendar')
ZopeTestCase.installProduct('MailHost')
ZopeTestCase.installProduct('CPSCore')
ZopeTestCase.installProduct('CPSDocument')

class TestCPSInstaller(ZopeTestCase.PortalTestCase):
    """Tests the methods to support CPS installations"""

    def getPortal(self):
        if not hasattr(self.app, portal_name):
            manage_addCMFSite(self.app, portal_name)
        return self.app[portal_name]

    def testCreateWF(self):
        wfdef = {'wfid': 'test_workflow', }

        wfstates = {'state1': {
                     'title': 'State1',
                     'transitions':('trans1', 'trans3'),
                     'permissions': {},
                    },
                    'state2': {
                     'title': 'Work',
                     'transitions':('trans2',),
                     'permissions': {},
                    },
                }

        wftransitions = {'trans1': {
                         'title': 'Test transition 1',
                         'new_state_id': 'state1',
                         'transition_behavior': (TRANSITION_INITIAL_CREATE, ),
                         'actbox_name': '',
                         'actbox_category': 'workflow',
                         'actbox_url': '',
                         'props': {'guard_permissions':'',
                                   'guard_roles':'Manager; WorkspaceManager; '
                                                 'WorkspaceMember; ',
                                   'guard_expr':''},
                        },
                        'trans2': {
                         'title': 'Test transition 2',
                         'new_state_id': 'state2',
                         'transition_behavior': (TRANSITION_ALLOWSUB_CREATE,
                                                 TRANSITION_ALLOWSUB_CHECKOUT),
                         'trigger_type': TRIGGER_USER_ACTION,
                         'actbox_name': 'To State2',
                         'actbox_category': '',
                         'actbox_url': '',
                         'props': {'guard_permissions':'',
                                   'guard_roles':'Manager; WorkspaceManager; '
                                                 'WorkspaceMember; ',
                                   'guard_expr':''},
                         },
                        'trans3': {
                         'title': 'Test transition 2',
                         'new_state_id': 'trans1',
                         'transition_behavior': (TRANSITION_ALLOWSUB_DELETE,
                                                 TRANSITION_ALLOWSUB_MOVE,
                                                 TRANSITION_ALLOWSUB_COPY),
                         'clone_allowed_transitions': None,
                         'trigger_type': TRIGGER_USER_ACTION,
                         'actbox_name': 'New',
                         'actbox_category': '',
                         'actbox_url': '',
                         'props': {'guard_permissions':'',
                                   'guard_roles':'Manager; WorkspaceManager; '
                                                 'WorkspaceMember; ',
                                   'guard_expr':''},
                     },
                 }

        wfscripts = {'test_sccripts': {
                        '_owner': None,
                        'script': """\
##parameters=state_change
return "This is a test script"
"""
                        },
                    }

        wfvariables = { 'var1': {
                            'description': 'Variable 1',
                            'default_expr': 'transition/getId|nothing',
                            'for_status': 1,
                            'update_always': 1,
                            },
                        'var2': {
                            'description': 'Variable 2',
                           'default_expr': 'user/getId',
                           'for_status': 1,
                           'update_always': 1
                           },
                        'var3': {
                            'description': 'Variable 3',
                            'default_expr': "python:state_change.kwargs."
                                            "get('comment', '')",
                            'for_status': 1,
                            'update_always': 1
                            },
                        }

        installer = CPSInstaller(self.portal, 'Installer test')
        installer.verifyWorkflow(wfdef, wfstates, wftransitions,
            wfscripts, wfvariables)
        # Check that the workflow was created
        wftool = self.portal.portal_workflow
        self.assert_(wfdef['wfid'] in wftool.objectIds())
        wf = wftool[wfdef['wfid']]
        # Check that all the subobjects were created
        states = wf.states.objectIds()
        for state in wfstates.keys():
            self.assert_(state in states)
        transitions = wf.transitions.objectIds()
        for transistion in wftransitions.keys():
            self.assert_(transistion in transitions)
        scripts = wf.scripts.objectIds()
        for script in wfscripts.keys():
            self.assert_(script in scripts)
        variables = wf.variables.objectIds()
        for variable in wfvariables.keys():
            self.assert_(variable in variables)

        installer.verifyWorkflow(wfdef, wfstates, wftransitions,
            wfscripts, wfvariables)
        # Check that the workflow was NOT created
        self.assert_(installer.messages[-1].count(log_ok_message) > 0)

    def testFlexTypes(self):
        types = {
            'FlexibleType': {
                'title': 'portal_type_Flexible_title',
                'description': 'portal_type_Flexible_description',
                'content_icon': 'flexible_icon.gif',
                'content_meta_type': 'CPS Document',
                'product': 'CPSDocument',
                'factory': 'addCPSDocument',
                'immediate_view': 'cpsdocument_edit_form',
                'global_allow': 1,
                'filter_content_types': 1,
                'allowed_content_types': (),
                'allow_discussion': 0,
                'cps_is_searchable': 1,
                'cps_proxy_type': 'document',
                'schemas': ['metadata', 'common', 'flexible_content'],
                'layouts': ['common', 'flexible_content'],
                'flexible_layouts': ['flexible_content:flexible_content'],
                'storage_methods': [],
            },
            'IsInCalendarType': {
                'title': 'portal_type_Event_title',
                'description': 'portal_type_Event_description',
                'content_icon': 'event_icon.gif',
                'content_meta_type': 'CPS Document',
                'product': 'CPSDocument',
                'factory': 'addCPSDocument',
                'immediate_view': 'cpsdocument_view',
                'global_allow': 1,
                'filter_content_types': 1,
                'allowed_content_types': (),
                'allow_discussion': 0,
                'cps_is_searchable': 1,
                'cps_proxy_type': 'document',
                'schemas': ['metadata', 'common', 'event'],
                'layouts': ['common', 'event'],
                'flexible_layouts': [],
                'storage_methods': [],
                'display_in_cmf_calendar': 1,
            }
        }

        # Try to create a portal_calendar tool.
        # ProductDispatcher does not implement get() or has_key(),
        # therefor we just try to install and catch the error if
        # CMFCalendar is not installed.
        calendar_product = None
        try:
            calendar_product = self.portal.manage_addProduct['CMFCalendar']
            calendar_product.manage_addTool('CMF Calendar Tool')
        except AttributeError:
            pass
        installer = CPSInstaller(self.portal, 'Installer test')
        installer.verifyFlexibleTypes(types)
        self.assert_(hasattr(self.portal.portal_types, 'FlexibleType'))
        self.assert_(hasattr(self.portal.portal_types, 'IsInCalendarType'))
        if calendar_product:
            # Make sure the calendar type got registered.
            self.assert_('IsInCalendarType' in \
                self.portal.portal_calendar.calendar_types)


if __name__ == '__main__':
    framework()
else:
    from unittest import TestSuite, makeSuite
    def test_suite():
        suite = TestSuite()
        suite.addTest(makeSuite(TestCPSInstaller))
        return suite

