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
                self.logger.log('Adding %s' % title)
                script = ExternalMethod(id, title, script, method)
                self.portal._setObject(id, script)
            self.logger.log(self.portal[id]())
        except ImportError:
            pass


