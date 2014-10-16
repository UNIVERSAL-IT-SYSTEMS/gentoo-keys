#
#-*- coding:utf-8 -*-

"""
    Gentoo-keys - seedhandler.py

    Seed handling interface module

    @copyright: 2012 by Brian Dolbec <dol-sen@gentoo.org>
    @license: GNU GPL2, see COPYING for details.
"""

import os
import re
from json import load

from gkeys.config import GKEY, MAPSEEDS
from gkeys.seed import Seeds
from sslfetch.connections import Connector


class SeedHandler(object):

    def __init__(self, logger, config):
        self.config = config
        self.logger = logger
        self.fingerprint_re = re.compile('[0-9A-Fa-f]{40}')
        self.finerprint_re2 = re.compile('[0-9A-Fa-f]{4}( [0-9A-Fa-f]{4}){9}')


    def new(self, args, checkgkey=False):
        newgkey = self.build_gkeydict(args)
        if checkgkey:
            newgkey = self.check_gkey(newgkey)
            newgkey = GKEY(**newgkey)
            self.logger.debug("SeedHandler: new; new gkey: %s" % str(newgkey))
        else:
            self.logger.debug("SeedHandler: new; FAILED to get parts from: %s"
                % str(args))
            return None
        return newgkey

    @staticmethod
    def build_gkeydict(args):
        keyinfo = {}
        for attr in GKEY._fields:
            try:
                value = getattr(args, attr)
                if attr == 'name' and value:
                    value = " ".join(value)
                if value:
                    keyinfo[attr] = value
            except AttributeError:
                pass
        return keyinfo

    def load_seeds(self, seeds=None, seedfile=None):
        if not seeds and not seedfile:
            self.logger.error("SeedHandler: load_seeds; no filename to load: "
            "setting = %s.  Please use the -s option to indicate: which seed "
            "file to use." % seedfile)
            return False
        if seeds:
            filepath = self.config.get_key(seeds + "-seedfile")
        elif seedfile:
            filepath = os.path.join(self.config.get_key('seedsdir'),
                                    '%s.seeds' % seedfile)
        self.logger.debug("SeedHandler: load_seeds; seeds filepath to load: "
            "%s" % filepath)
        seeds = Seeds(config=self.config)
        seeds.load(filepath)
        return seeds

    def load_category(self, category, nicks=None):
        '''Loads the designated key directories

        @param category: string
        @param nicks: list of string nick ids to load
        @return Seeds class object
        '''
        seeds = Seeds(config=self.config)
        if category:
            catdir = self.config.get_key(category + "-category")
        else:
            self.logger.debug("SeedHandler: load_category; Error invalid category: %s." % (str(category)))
            return seeds
        self.logger.debug("SeedHandler: load_category; catdir = %s" % catdir)
        try:
            if not nicks:
                nicks = os.listdir(catdir)
            for nick in nicks:
                seed_path = os.path.join(catdir, nick)
                gkey_path = os.path.join(seed_path, 'gkey.seeds')
                try:
                    with open(gkey_path, 'r') as fileseed:
                        seed = load(fileseed)
                except IOError as error:
                    self.logger.debug("SeedHandler: load_category; IOError loading seed file %s." % gkey_path)
                    self.logger.debug("Error was: %s" % str(error))
                seeds.add(nick, GKEY(**seed.values()[0]))
        except OSError as error:
            self.logger.debug("SeedHandler: load_category; OSError for %s" % catdir)
            self.logger.debug("Error was: %s" % str(error))
        return seeds

    def fetch_seeds(self, seeds):
        '''Fetch new seed files'''
        # setup the ssl-fetch ouptut map
        connector_output = {
            'info': self.logger.info,
            'error': self.logger.error,
            'kwargs-info': {},
            'kwargs-error': {},
        }
        http_check = re.compile(r'^(http|https)://')
        urls = []
        messages = []
        try:
            for seed in [seeds]:
                seedurl = self.config.get_key(MAPSEEDS[seed])
                if http_check.match(seedurl):
                    urls.extend([seedurl])
                else:
                    self.logger.info("Wrong seed file URLs... Switching to default URLs.")
                    urls.extend([self.config['seedurls'][MAPSEEDS[seed]]])
        except KeyError:
            for key, value in MAPSEEDS.items():
                urls.extend([self.config['seedurls'][value]])
        fetcher = Connector(connector_output, None, "Gentoo Keys")
        for url in urls:
            seed = url.rsplit('/', 1)[1]
            timestamp_prefix = seed[:3]
            timestamp_path = self.config['%s-timestamp' % timestamp_prefix]
            filename = self.config['%s-seedfile' % timestamp_prefix]
            file_exists = os.path.exists(filename)
            success, seeds, timestamp = fetcher.fetch_content(url, timestamp_path)
            if not timestamp and file_exists:
                messages.append("%s is already up to date." % seed)
            elif success:
                self.logger.debug("SeedHandler: fetch_seed; got results.")
                filename = filename + '.new'
                with open(filename, 'w') as seedfile:
                    seedfile.write(seeds)
                filename = self.config['%s-seedfile' % timestamp_prefix]
                old = filename + '.old'
                try:
                    self.logger.info("Backing up existing file...")
                    if os.path.exists(old):
                        self.logger.debug(
                            "SeedHandler: fetch_seeds; Removing 'old' seed file: %s"
                            % old)
                        os.unlink(old)
                    if os.path.exists(filename):
                        self.logger.debug(
                            "SeedHandler: fetch_seeds; Renaming current seed file to: "
                            "%s" % old)
                        os.rename(filename, old)
                    self.logger.debug("SeedHandler: fetch_seeds; Renaming '.new' seed file to %s"
                                      % filename)
                    os.rename(filename + '.new', filename)
                    with open(timestamp_path, 'w+') as timestampfile:
                        timestampfile.write(str(timestamp) + '\n')
                    messages.append("Successfully fetched %s." % seed)
                except IOError:
                    raise
            else:
                messages.append("Failed to fetch %s." % seed)
        return messages

    def check_gkey(self, args):
        # assume it's good until an error is found
        is_good = True
        try:
            args['keydir'] = args.get('keydir', args['nick'])
            if args['fingerprint']:
                if not self._check_fingerprint_integrity(args):
                    is_good = False
                    self.logger.error('Bad fingerprint from command line args.')
        except KeyError:
            self.logger.error('GPG fingerprint not found.')
            is_good = False
        for key, value in args.items():
            if key == 'fingerprint':
                args[key] = value.split()
            else:
                args[key] = value
        if not is_good:
            self.logger.error('A valid fingerprint '
                  'was not found for %s' % args['name'])
        return args

    def _check_fingerprint_integrity(self, gkey):
        # assume it's good unti an error is found
        is_good = True
        fingerprint = gkey['fingerprint']
        # check fingerprint integrity
        if len(fingerprint) != 40:
            self.logger.error('  GPGKey incorrect fingerprint ' +
                    'length (%s) for fingerprint: %s' % (len(fingerprint), fingerprint))
            is_good = False
        if not self.fingerprint_re.match(fingerprint):
            self.logger.error('  GPGKey: Non hexadecimal digits in ' + 'fingerprint for fingerprint: ' + fingerprint)
            is_good = False
        return is_good
