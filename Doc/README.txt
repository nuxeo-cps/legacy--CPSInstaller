CPSInstaller

  CPSInstaller and CMFInstaller are two base classes that is intended to
  vastly simplify the creation of install scripts for CMF and CPS products.
  
  It is basically a class full with methods that things that is common to
  do when installing products, such as setting up skins, creating workflows,
  adding types, creating tools and such. CPSInstaller extends CMFInstaller
  with CPSSpecific support methods. It is simple to do the same for other
  CMF based systems, like Plone.
  
  How to use
  
    To use CMFInstaller with your product, create a python script called 
    Install.py in a directory called Extensions in your product directory.
    
    To start using the CMFInstaller, create an Extensions directory in your
    product directory, copy the <hjhjhj>.py file to this directory and
    rename it Install.py.

    Strictly speaking, it can be called anything, but calling it Install.py 
    and install respectively is the standardized way of doing it. This is 
    also compatible with CMFQuickInstaller.

  Writing install scripts.

    There are four tasks you want an installer to support. Installing,
    Uninstalling, Verifying, Upgrading and "Resetting".

    Uninstalling is best delegated to automatic functionality that keeps
    track of what is being created, and removed this when running the
    uninstall. CPSInstaller does not support this today, the idea is to
    use and/or integrate with CMFQuickInstaller for this.

    Resetting, that is turning back the installation to it's known
    default state, can be done by uninstalling and installing again.

    Verifying, that is making sure all necessary parts exist, is similar
    to installing. In fact, running a verification on a clean system should
    have the exact same result as installing.

    Upgrading is also similar to verifying, as an upgrade should only be
    done if it isn't done already.

    Therefore, install scripts should be written as verification scripts,
    only making changes if needed. These are the basic guidelines to follow:

      1. Do not create anything that exists. If a tool exist, don't delete
         it and recreate it in the install. If you do this, any configuration
         changes will be lost.

      2. Do not change anything unless you are doing an upgrade. An
         installation should only change what it knows must be changed.
         Everything else should be kept as is, to make it possible for the
         manager to change the configuration.

      3. Remember to do a thorough check. Checking that the portal_types
         tool exists is not enough. You need to check that all the types
         you want are created. But don't forget point 1, don't recreate
         or change the types if they exist, only add them if they don't.

      4. Make upgrades testable, and test for previous upgrades. When doing
         an upgrade, the best thing is to check that the change isn't
         already done before doing it. However, do the test in a way that
         can not be unintentionally unmade by later configuration changes,
         because then again, the site manager will be frustrated by his
         configuration changes magically being reset.


