#
#-*- coding:utf-8 -*-

from __future__ import print_function


import sys
import os
import argparse

from gkeys import log
from gkeys.log import log_levels, set_logger

from gkeys import config
from gkeys import seed

from gkeys.config import GKeysConfig, GKEY
from gkeys.seed import Seeds
from gkeyldap import search
from gkeyldap.search import (LdapSearch, UID, gkey2ldap_map, gkey2SEARCH)

logger = log.logger

# set some defaults
KEY_LEN = {
    'keyid': 8,
    'longkeyid': 16,
}


def get_key_ids(key, info):
    '''Small utility function to return only keyid (short)
    or longkeyid's

    @param key: string, the key lenght desired
    @param info: list of keysid's to process
    @return list of the desired key lengh id's
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


class Main(object):
    '''Main command line interface class'''


    def __init__(self, root=None, config=None, print_results=True):
        """ Main class init function.

        @param root: string, root path to use
        """
        self.root = root or "/"
        self.config = config or GKeysConfig(root=root)
        self.print_results = print_results
        self.args = None
        self.seeds = None


    def __call__(self, args=None):
        if args:
            self.run(self.parse_args(args))
        else:
            self.run(self.parse_args(sys.argv[1:]))


    def parse_args(self, args):
        '''Parse a list of aruments

        @param args: list
        @returns argparse.Namespace object
        '''
        #logger.debug('MAIN: parse_args; args: %s' % args)
        actions = ['ldapsearch', 'updateseeds']
        parser = argparse.ArgumentParser(
            prog='gkeys',
            description='Gentoo-keys manager program',
            epilog='''Caution: adding untrusted keys to these keyrings can
                be hazardous to your system!''')
        # actions
        parser.add_argument('action', choices=actions, nargs='?',
            default='ldapsearch', help='Search ldap or update the seed file')
        # options
        parser.add_argument('-c', '--config', dest='config', default=None,
            help='The path to an alternate config file')
        parser.add_argument('-d', '--dest', dest='destination', default=None,
            help='The destination db file path')
        parser.add_argument('-N', '--name', dest='name', default=None,
            help='The name to search for')
        parser.add_argument('-n', '--nick', dest='nick', default=None,
            help='The nick or user id (uid) to search for')
        parser.add_argument('-m', '--mail', dest='mail', default=None,
            help='The email address to search for')
        parser.add_argument('-k', '--keyid', dest='keyid', default=None,
            help='The gpg keyid to search for')
        parser.add_argument('-f', '--fingerprint', dest='fingerprint', default=None,
            help='The gpg fingerprint to search for')
        parser.add_argument('-S', '--status', default=False,
            help='The seedfile path to use')
        parser.add_argument('-D', '--debug', default='DEBUG',
            choices=list(log_levels),
            help='The logging level to set for the logfile')

        return parser.parse_args(args)


    def run(self, args):
        '''Run the args passed in

        @param args: list or argparse.Namespace object
        '''
        global logger
        message = None
        if not args:
            message = "Main: run; invalid args argument passed in"
        if isinstance(args, list):
            args = self.parse_args(args)
        if args.config:
            self.config.defaults['config'] = args.config
        # now make it load the config file
        self.config.read_config()

        # establish our logger and update it in the imported files
        logger = set_logger('gkeyldap', self.config['logdir'], args.debug)
        config.logger = logger
        seed.logger = logger
        search.logger = logger

        if message:
            logger.error(message)

        # now that we have a logger, record the alternate config setting
        if args.config:
            logger.debug("Main: run; Found alternate config request: %s"
                % args.config)

        logger.info("Begin running action: %s" % args.action)

        func = getattr(self, '_action_%s' % args.action)
        logger.debug('Main: run; Found action: %s' % args.action)
        results = func(args)
        return results


    def _action_ldapsearch(self, args):
        l = LdapSearch()
        logger.info("Search...establishing connection")
        print("Search...establishing connection")
        if not l.connect():
            logger.info("Aborting Search...Connection failed")
            print("Aborting Search...Connection failed")
            return False
        logger.debug("MAIN: _action_ldapsearch; args = %s" % str(args))
        x, target, search_field = self.get_args(args)
        results = l.search(target, search_field)
        devs = l.result2dict(results, gkey2ldap_map[x])
        for dev in sorted(devs):
            print(dev, devs[dev])
        print("============================================")
        print("Total number of devs in results:", len(devs))
        return True


    def _action_updateseeds(self, args):
        logger.info("Beginning ldap search...")
        print("Beginning ldap search...")
        l = LdapSearch()
        if not l.connect():
            print("Aborting Update...Connection failed")
            return False
        results = l.search('*', UID)
        info = l.result2dict(results, 'uid')
        logger.debug(
            "MAIN: _action_updateseeds; got results :) converted to info")
        if not self.create_seedfile(info):
            logger.error("Dev seed file update failure: "
                "Original seed file is intact & untouched.")
        old = self.config['dev-seedfile'] + '.old'
        try:
            print("Backing up existing file...")
            if os.path.exists(old):
                logger.debug(
                    "MAIN: _action_updateseeds; Removing 'old' seed file: %s"
                    % old)
                os.unlink(old)
            if os.path.exists(self.config['dev-seedfile']):
                logger.debug(
                    "MAIN: _action_updateseeds; Renaming current seed file to: "
                    "%s" % old)
                os.rename(self.config['dev-seedfile'], old)
            logger.debug(
                "MAIN: _action_updateseeds; Renaming '.new' seed file to: %s"
                % self.config['dev-seedfile'])
            os.rename(self.config['dev-seedfile'] + '.new',
                self.config['dev-seedfile'])
        except IOError:
            raise
        print("Developer Seed file updated")
        return True


    def create_seedfile(self, devs):
        print("Creating seeds from ldap data...")
        filename = self.config['dev-seedfile'] + '.new'
        self.seeds = Seeds(filename)
        count = 0
        for dev in sorted(devs):
            if devs[dev]['gentooStatus'][0] not in ['active']:
                continue
            #logger.debug("create_seedfile, dev = "
            #   "%s, %s" % (str(dev), str(devs[dev])))
            new_gkey = GKEY._make(self.build_gkeylist(devs[dev]))
            self.seeds.add(new_gkey)
            count += 1
        print("Total number of seeds created:", count)
        print("Seeds created...saving file: %s" % filename)
        return self.seeds.save()


    @staticmethod
    def get_args(args):
        for x in ['nick', 'name', 'gpgkey', 'fingerprint', 'status']:
            if x:
                target = getattr(args, x)
                search_field = gkey2SEARCH[x]
                break
        return (x, target, search_field)


    @staticmethod
    def build_gkeydict(info):
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
                    logger.error('%s = "undefined" for %s, %s'
                        %(field, info['uid'][0], info['cn'][0]))
                if value:
                    keyinfo[x] = value
            except KeyError:
                pass
        return keyinfo


    @staticmethod
    def build_gkeylist(info):
        keyinfo = []
        keyid_found = False
        keyid_missing = False
        #logger.debug("MAIN: build_gkeylist; info = %s" % str(info))
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
                    logger.error('%s = "undefined" for %s, %s'
                        %(field, info['uid'][0], info['cn'][0]))
                keyinfo.append(value)
            except KeyError:
                logger.error("Missing %s (%s) for %s, %s"
                    %(field, x, info['uid'][0], info['cn'][0]))
                if x in ['keyid', 'longkeyid']:
                    keyid_missing = True
                keyinfo.append(None)
        if not keyid_found and not keyid_missing:
            try:
                gpgkey = info[gkey2ldap_map['longkeyid']]
            except KeyError:
                gpgkey = 'Missing from ldap info'
            logger.error("A valid keyid or longkeyid was not found for")
            logger.error("developer: %s, %s : gpgkey = %s"
                %(info['uid'][0], info['cn'][0], gpgkey))
        return keyinfo

