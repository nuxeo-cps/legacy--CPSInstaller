#
# Runs all tests in the current directory
#
# Execute like:
#   python runalltests.py
#
# Alternatively use the testrunner:
#   python /path/to/Zope/utilities/testrunner.py -qa
#

import os, sys

if not 'SOFTWARE_HOME' in os.environ.keys():
    # Find the root of the Zope install.
    curdir = os.getcwd()
    zope_home = None
    look_foor_file = 'z2.py' # This may change in Zope2.7
    while not zope_home:
        if look_foor_file in os.listdir(curdir):
            zope_home = curdir
            continue
        if curdir == os.path.split(curdir)[0]:
            break
        curdir, ignore = os.path.split(curdir)

if zope_home:
    zope_home = os.path.join(zope_home, 'lib', 'python')
    print "Setting SOFTWARE_HOME to", zope_home
    os.environ['SOFTWARE_HOME'] = zope_home
else:
    print "SOFTWARE_HOME not set, and can not be found."
    sys.exit(-1)

if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

import unittest
TestRunner = unittest.TextTestRunner
suite = unittest.TestSuite()

tests = os.listdir(os.curdir)
tests = [n[:-3] for n in tests if n.startswith('test') and n.endswith('.py')]

for test in tests:
    m = __import__(test)
    if hasattr(m, 'test_suite'):
        suite.addTest(m.test_suite())

if __name__ == '__main__':
    TestRunner().run(suite)

