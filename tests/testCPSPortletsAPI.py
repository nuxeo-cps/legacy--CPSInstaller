# (c) 2003 Nuxeo SARL <http://nuxeo.com>
# $Id$

import os, sys

from zExceptions import BadRequest

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Testing import ZopeTestCase

from Products.CPSDefault.tests import CPSDefaultTestCase
from Products.ExternalMethod.ExternalMethod import ExternalMethod


from Products.CPSInstaller.CPSInstaller import CPSInstaller
from Products.CPSInstaller.CMFInstaller import log_ok_message

ZopeTestCase.installProduct('CPSPortlets', quiet=1)

class TestCPSPortletsAPI(CPSDefaultTestCase.CPSDefaultTestCase):
    """Tests the methods to support CPSPortlets installations

    It's not going to do anything if CPSPortlets is not present.
    """


    login_id = 'root'

    def afterSetUp(self):
        if self.login_id:
            self.login(self.login_id)
            self.portal.portal_membership.createMemberArea()

        self.portal.REQUEST.SESSION = {}

        portlets_product = None
        try:
            portlets_product = self.portal.manage_addProduct['CPSPortlets']
            # Install the CPSPortlets product
            if 'cpsportlets_installer' not in self.portal.objectIds():
                cpsportlets_installer = ExternalMethod('cpsportlets_installer',
                                                       '',
                                                       'CPSPortlets.install',
                                                       'install')
                self.portal._setObject('cpsportlets_installer',
                                       cpsportlets_installer)
            self.portal.cpsportlets_installer()

            try:
                portlets_product.manage_addTool('CPS Portlets Tool')
            except BadRequest:
                pass
        except AttributeError:
            pass

        if portlets_product is not None:
            self.installer = CPSInstaller(self.portal, 'Installer test')
        else:
            self.installer = None

    def test_getPortletContainer(self):

        # If CPSPortlets is present
        if self.installer is not None:
            # Check there's no container
            self.assertEqual(self.installer.getPortletContainer(), None)
            # Check there's one now
            self.assertNotEqual(self.installer.getPortletContainer(create=1),
                                None)

    def test_verifyPortletContainer(self):

        # If CPSPortlets is present
        if self.installer is not None:
            # Check there's no container
            self.assertEqual(self.installer.getPortletContainer(), None)
            # Create one container
            self.assertNotEqual(self.installer.verifyPortletContainer(), None)
            # Check it's ok
            self.assertNotEqual(self.installer.getPortletContainer(), None)

    def test_verifyPortlets(self):

        # Example of portlets declaration
        portlets = ({'type'  : 'Dummy Portlet',
                     'identifier' : 'dummy1',
                     'Title' : 'Fake Portlet',
                     'slot'  : 'left',
                     'order' : 0},
                    {'type'  : 'Dummy Portlet',
                     'identifier' : 'dummy2',
                     'Title' : 'Fake Portlet 2',
                     'slot'  : 'right',
                     'order' : 2},
                    {'type'  : 'Dummy Portlet',
                     'identifier' : 'dummy2',
                     'Title' : 'Fake Portlet 2',
                     'slot'  : 'left',
                     'order' : 3},
                    )

        if self.installer is not None:
            # Test creation of portlets at the root of the portal
            # Only 2 in results since we provided twice the identifier
            returned = self.installer.verifyPortlets(portlets)
            self.assertEqual(len(returned), 2)

            new_portlets = ({'type'  : 'Dummy Portlet',
                             'identifier' : 'dummy1',
                             'Title' : 'Fake Portlet',
                             'slot'  : 'left',},
                             )
            returned = self.installer.verifyPortlets(new_portlets)
            self.assertEqual(len(returned), 1)
            returned = self.installer.verifyPortlets(())
            self.assertEqual(len(returned), 0)

if __name__ == '__main__':
    framework()
else:
    from unittest import TestSuite, makeSuite
    def test_suite():
        suite = TestSuite()
        suite.addTest(makeSuite(TestCPSPortletsAPI))
        return suite
