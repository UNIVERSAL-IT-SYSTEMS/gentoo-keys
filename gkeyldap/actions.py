#
#-*- coding:utf-8 -*-

"""
    Gentoo-keys - gkeyldap/actions.py

    Primary api interface module

    @copyright: 2012 by Brian Dolbec <dol-sen@gentoo.org>
    @license: GNU GPL2, see COPYING for details.
"""

import os
import re

from gkeys.config import GKEY, KEYID, LONGKEYID, FINGERPRINT
from gkeys.seed import Seeds
from gkeyldap.search import (LdapSearch, UID, gkey2ldap_map, gkey2SEARCH)


# set some defaults
KEY_LEN = {
    'keyid': 8,
    'longkeyid': 16,
}


Avialable_Actions = ['ldapsearch', 'updateseeds']


def get_key_ids(key, info):
    '''Small utility function to return only keyid (short)
    or longkeyid's

    @param key: string, the key length desired
    @param info: list of keysid's to process
    @return list of the desired key length id's
    '''
    result = []
    for x in info:
        if x.startswith('0x'):
            mylen = KEY_LEN[key] + 2
        else:
            mylen = KEY_LEN[key]
        if len(x) == mylen:
            result.append(x)
    return result


class Actions(object):


    def __init__(self, config, output=None, logger=None):
        self.config = config
        self.output = output
        self.logger = logger
        self.seeds = None
        self.fingerprint_re = re.compile('[0-9A-Fa-f]{40}')


    def ldapsearch(self, args):
        l = LdapSearch()
        self.logger.info("Search...establishing connection")
        self.output("Search...establishing connection")
        if not l.connect():
            self.logger.info("Aborting Search...Connection failed")
            self.output("Aborting Search...Connection failed")
            return False
        self.logger.debug("MAIN: _action_ldapsearch; args = %s" % str(args))
        x, target, search_field = self.get_args(args)
        results = l.search(target, search_field)
        devs = l.result2dict(results, gkey2ldap_map[x])
        for dev in sorted(devs):
            self.output(dev, devs[dev])
        self.output("============================================")
        self.output("Total number of devs in results:", len(devs))
        self.logger.info("============================================")
        self.logger.info("Total number of devs in results: %d" % len(devs))
        return True


    def updateseeds(self, args):
        self.logger.info("Beginning ldap search...")
        self.output("Beginning ldap search...")
        l = LdapSearch()
        if not l.connect():
            self.output("Aborting Update...Connection failed")
            self.logger.info("Aborting Update...Connection failed")
            return False
        results = l.search('*', UID)
        info = l.result2dict(results, 'uid')
        self.logger.debug(
            "MAIN: _action_updateseeds; got results :) converted to info")
        if not self.create_seedfile(info):
            self.logger.error("Dev seed file update failure: "
                "Original seed file is intact & untouched.")
        filename = self.config['dev-seedfile']
        old = filename + '.old'
        try:
            self.output("Backing up existing file...")
            self.logger.info("Backing up existing file...")
            if os.path.exists(old):
                self.logger.debug(
                    "MAIN: _action_updateseeds; Removing 'old' seed file: %s"
                    % old)
                os.unlink(old)
            if os.path.exists(filename):
                self.logger.debug(
                    "MAIN: _action_updateseeds; Renaming current seed file to: "
                    "%s" % old)
                os.rename(filename, old)
            self.logger.debug(
                "MAIN: _action_updateseeds; Renaming '.new' seed file to: %s"
                % filename)
            os.rename(filename + '.new', filename)
        except IOError:
            raise
        self.output("Developer Seed file updated")
        return True


    def create_seedfile(self, devs):
        self.output("Creating seeds from ldap data...")
        filename = self.config['dev-seedfile'] + '.new'
        self.seeds = Seeds(filename)
        count = 0
        error_count = 0
        for dev in sorted(devs):
            if devs[dev]['gentooStatus'][0] not in ['active']:
                continue
            #self.logger.debug("create_seedfile, dev = "
            #   "%s, %s" % (str(dev), str(devs[dev])))
            keyinfo = self.build_gkeylist(devs[dev])
            if keyinfo:
                new_gkey = GKEY._make(keyinfo)
                self.seeds.add(new_gkey)
                count += 1
            else:
                error_count += 1
        self.output("Total number of seeds created:", count)
        self.output("Seeds created...saving file: %s" % filename)
        self.output("Total number of Dev's with gpg errors:", error_count)
        self.logger.info("Total number of seeds created: %d" % count)
        self.logger.info("Seeds created...saving file: %s" % filename)
        self.logger.info("Total number of Dev's with gpg errors: %d" % error_count)
        return self.seeds.save()


    @staticmethod
    def get_args(args):
        for x in ['nick', 'name', 'gpgkey', 'fingerprint', 'status']:
            if x:
                target = getattr(args, x)
                search_field = gkey2SEARCH[x]
                break
        return (x, target, search_field)



    def build_gkeydict(self, info):
        keyinfo = {}
        for x in GKEY._fields:
            field = gkey2ldap_map[x]
            if not field:
                continue
            try:
                # strip errant line feeds
                values = [y.strip('\n') for y in info[field]]
                if values and values in ['uid', 'cn' ]:
                    value = values[0]
                # separate out short/long key id's
                elif values and x in ['keyid', 'longkeyid']:
                    value = get_key_ids(x, values)
                else:
                    value = values
                if 'undefined' in values:
                    self.logger.error('%s = "undefined" for %s, %s'
                        %(field, info['uid'][0], info['cn'][0]))
                if value:
                    keyinfo[x] = value
            except KeyError:
                pass
        return keyinfo


    def build_gkeylist(self, info):
        keyinfo = []
        keyid_found = False
        keyid_missing = False
        # assume it's good until found an error is found
        is_good = True
        #self.logger.debug("MAIN: build_gkeylist; info = %s" % str(info))
        for x in GKEY._fields:
            field = gkey2ldap_map[x]
            if not field:
                keyinfo.append(None)
                continue
            try:
                # strip errant line feeds
                values = [y.strip('\n') for y in info[field]]
                if values and field in ['uid', 'cn' ]:
                    value = values[0]
                # separate out short/long key id's
                elif values and x in ['keyid', 'longkeyid']:
                    value = get_key_ids(x, values)
                    if len(value):
                        keyid_found = True
                elif values and x in ['fingerprint']:
                    value = [v.replace(' ', '') for v in values]
                else:
                    value = values
                if 'undefined' in values:
                    self.logger.error('ERROR in ldap info for: %s, %s'
                        %(info['uid'][0],info['cn'][0]))
                    self.logger.error('  %s = "undefined"' %(field))
                    is_good = False
                keyinfo.append(value)
            except KeyError:
                self.logger.debug('Ldap info for: %s, %s'
                    %(info['uid'][0],info['cn'][0]))
                self.logger.debug('  MISSING or EMPTY ldap field ' +
                    '[%s] GPGKey field [%s]' %(field, x))
                if x in ['keyid', 'longkeyid']:
                    keyid_missing = True
                else:
                    is_good = False
                keyinfo.append(None)
        if not keyid_found and keyid_missing:
            fingerprint = None
            try:
                fingerprint = info[gkey2ldap_map['fingerprint']]
                self.logger.debug('  Generate gpgkey, Found ldap fingerprint field')
            except KeyError:
                gpgkey = 'Missing fingerprint from ldap info'
                self.logger.debug('  Generate gpgkey, ldap fingerprint KeyError')
            if fingerprint:
                values = [y.strip('\n') for y in fingerprint]
                value = [v.replace(' ', '') for v in values]
                # assign it to gpgkey to prevent a possible
                # "gpgkey" undefined error
                gpgkey = ['0x' + x[-KEY_LEN['longkeyid']:] for x in value]
                keyinfo[LONGKEYID] = gpgkey
                self.logger.debug('  Generate gpgkey, NEW keyinfo[LONGKEYID] = %s'
                    % str(keyinfo[LONGKEYID]))
            else:
                gpgkey = 'Missing or Bad fingerprint from ldap info'
                is_good = False
            if not keyinfo[LONGKEYID]:
                self.logger.error('ERROR in ldap info for: %s, %s'
                    %(info['uid'][0],info['cn'][0]))
                self.logger.error('  A valid keyid, longkeyid or fingerprint '
                    'was not found for %s : gpgkey = %s' %(info['cn'][0], gpgkey))
                is_good = False
        if is_good:
            if keyinfo[FINGERPRINT]: # fingerprints exist check
                is_ok = self._check_fingerprint_integrity(info, keyinfo)
                is_match = self._check_id_fingerprint_match(info, keyinfo)
                if not is_ok or not is_match:
                    is_good = False
        if is_good:
            return keyinfo
        return None


    def _check_id_fingerprint_match(self, info, keyinfo):
        # assume it's good until found an error is found
        is_good = True
        for x in [KEYID, LONGKEYID]:
            # skip blank id field
            if not keyinfo[x]:
                continue
            for y in keyinfo[x]:
                index = len(y.lstrip('0x'))
                if y.lstrip('0x').upper() not in \
                        [x[-index:].upper() for x in keyinfo[FINGERPRINT]]:
                    self.logger.error('ERROR in ldap info for: %s, %s'
                        %(info['uid'][0],info['cn'][0]))
                    self.logger.error('  ' + str(keyinfo))
                    self.logger.error('  GPGKey id %s not found in the '
                        % y.lstrip('0x') + 'listed fingerprint(s)')
                    is_good = False
        return is_good


    def _check_fingerprint_integrity(self, info, keyinfo):
        # assume it's good until found an error is found
        is_good = True
        for x in keyinfo[FINGERPRINT]:
            # check fingerprint integrity
            if len(x) != 40:
                self.logger.error('ERROR in ldap info for: %s, %s'
                    %(info['uid'][0],info['cn'][0]))
                self.logger.error('  GPGKey incorrect fingerprint ' +
                    'length (%s) for fingerprint: %s' %(len(x), x))
                is_good = False
                continue
            if not self.fingerprint_re.match(x):
                self.logger.error('ERROR in ldap info for: %s, %s'
                    %(info['uid'][0],info['cn'][0]))
                self.logger.error('  GPGKey: Non hexadecimal digits in ' +
                    'fingerprint for fingerprint: ' + x)
                is_good = False
        return is_good
