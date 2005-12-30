============
CPSInstaller
============

:Revision: $Id$

.. sectnum::    :depth: 4
.. contents::   :depth: 4


About CPSInstaller
==================

CPSInstaller provides CMF products authors with an extensible
framework to help them writing *installers*: scripts that set up
products for use in the CMF, including boring tasks such as
registering or configuring skins, portal types, actions, catalog
indexes, permissions, schemas, widgets, layouts, vocabularies,
translations, events... 

CPSInstaller will be the standard way to install products in CPS
3.1, and extends and supersedes the old CPS 3.0 installer which
was located in the CPSDefault product (CPSDefault.Installer). By
removing the dependency on CPSDefault, we expect that it will make
it easier to install CPS products (CPSDocument, CPSSchemas,
CPSDirectory...) on CMF sites (including Plone sites) that don't
include CPSDefault, and to write non-CPS products installers that
will make them easy to install on CPS sites.


How it works
============

CPSInstaller and CMFInstaller are two base classes that is
intended to vastly simplify the creation of install scripts for
CMF and CPS products.

It is basically a class full of methods for tasks that are
commonly done when installing products, such as setting up skins,
creating workflows, adding types, creating tools and such.
CPSInstaller extends CMFInstaller with CPS-specific support
methods. It is simple to do the same for other CMF based systems,
like Plone.
  

Writing install scripts.
========================

There are five tasks you want an installer to support. Installing,
Uninstalling, Verifying, Upgrading and "Resetting".

Uninstalling is best delegated to automatic functionality that
keeps track of what is being created, and removed this when
running the uninstall. CPSInstall does not support this today, the
idea is to use and/or integrate with CMFQuickInstaller for this.

Resetting, that is turning back the installation to it's known
default state, can be done by uninstalling and installing again.

Verifying, that is making sure all necessary parts exist, is
similar to installing. In fact, running a verification on a clean
system should have the exact same result as installing.

Upgrading is also similar to verifying, as an upgrade should only
be done if it isn't done already, so these tasks are really the
same.

Therefore, install scripts should be written as verification
scripts, only making changes if needed. These are the basic
guidelines to follow:

1. Do not create anything that exists. If a tool exists, don't
   delete it and recreate it in the install. If you do this, any
   configuration changes will be lost.

2. Do not change anything unless you are doing an upgrade. An
   installation should only change what it knows must be changed.
   Everything else should be kept as is, to make it possible for
   the manager to change the configuration.

3. Remember to do a thorough check. Checking that the portal_types
   tool exists is not enough. You need to check that all the types
   you want are created. But don't forget point 1, don't recreate
   or change the types if they exist, only add them if they don't.

4. Make upgrades testable, and test for previous upgrades. When
   doing an upgrade, the best thing is to check that the change
   isn't already done before doing it. However, do the test in a
   way that can not be unintentionally unmade by later
   configuration changes, because then again, the site manager
   will be frustrated by his configuration changes magically being
   reset.

One of the features of CPSInstaller is that these principles are 
automatically supported. If you use a CPSInstaller method to
install a skin or a portal type or similar, it will make the tests
it should. (This is not 100% true at this moment, but it will be
soon, I hope.)


.. Emacs
.. Local Variables:
.. mode: rst
.. End:
.. Vim
.. vim: set filetype=rst:

