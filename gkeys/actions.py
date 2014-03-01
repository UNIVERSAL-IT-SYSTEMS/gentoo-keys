#
#-*- coding:utf-8 -*-

"""
    Gentoo-keys - actions.py

    Primary api interface module

    @copyright: 2012 by Brian Dolbec <dol-sen@gentoo.org>
    @license: GNU GPL2, see COPYING for details.
"""

from __future__ import print_function

import os


from gkeys.seedhandler import SeedHandler
from gkeys.lib import GkeysGPG
from gkeys.seed import Seeds


Available_Actions = ['listseed', 'addseed', 'removeseed', 'moveseed',
            'listseedfiles', 'listkey', 'addkey', 'removekey', 'movekey',
            'installed']


class Actions(object):
    '''Primary api actions'''

    def __init__(self, config, output=None, logger=None):
        self.config = config
        self.output = output
        self.logger = logger
        self.seeds = None


    def load_seeds(self, seeds=None ,seedfile=None):
        if not seeds and not seedfile:
            self.logger.error("ACTIONS: load_seeds; no filename to load: "
            "setting = %s.  Please use the -s option to indicate: which seed "
            "file to use." % filename)
            return None
        if seeds:
            filepath = self.config.get_key(filename + "-seedfile")
        elif seedfile:
            filepath = os.path.join(self.config.get_key('seedsdir'),
                                    '%s.seeds' % seedfile)
        self.logger.debug("ACTIONS: load_seeds; seeds filepath to load: "
            "%s" % filepath)
        seeds = Seeds()
        seeds.load(filepath)
        return seeds


    def listseed(self, args):
        '''Action listseed method'''
        handler = SeedHandler(self.logger)
        kwargs = handler.build_gkeydict(args)
        self.logger.debug("ACTIONS: listseed; kwargs: %s" % str(kwargs))
        if not self.seeds:
            self.seeds = self.load_seeds(args.seeds, args.seedfile)
        if self.seeds:
            results = self.seeds.list(**kwargs)
            return results
        return None


    def addseed(self, args):
        '''Action addseed method'''
        handler = SeedHandler(self.logger)
        gkey = handler.new(args)
        gkeys = self.listseed(args)
        if len(gkeys) == 0:
            self.logger.debug("ACTIONS: addkey; now adding gkey: %s" % str(gkey))
            success = self.seeds.add(gkey)
            if success:
                success = self.seeds.save()
                return ["Successfully Added new seed: %s" % str(success), gkey]
        else:
            messages = ["Matching seeds found in seeds file",
                "Aborting... \nMatching seeds:"]
            messages.extend(gkeys)
            return messages


    def removeseed(self, args):
        '''Action removeseed method'''
        handler = SeedHandler(self.logger)
        searchkey = handler.new(args, needkeyid=False, checkintegrity=False)
        self.logger.debug("ACTIONS: removeseed; gkey: %s" % str(searchkey))
        gkeys = self.listseed(args)
        if not gkeys:
            return ["Failed to Removed seed: No gkeys returned from listseed()",
                None]
        if len(gkeys) == 1:
            self.logger.debug("ACTIONS: removeseed; now deleting gkey: %s" % str(gkeys[0]))
            success = self.seeds.delete(gkeys[0])
            if success:
                success = self.seeds.save()
            return ["Successfully Removed seed: %s" % str(success),
                gkeys[0]]
        elif len(gkeys):
            messages = ["Too many seeds found to remove"]
            messages.extend(gkeys)
            return messages
        return ["Failed to Remove seed:", searchkey,
            "No matching seed found"]


    def moveseed(self, args):
        '''Action moveseed method'''
        handler = SeedHandler(self.logger)
        searchkey = handler.new(args, needkeyid=False, checkintegrity=False)
        self.logger.debug("ACTIONS: moveseed; gkey: %s" % str(searchkey))
        if not self.seeds:
            self.seeds = self.load_seeds(args.seeds)
        kwargs = handler.build_gkeydict(args)
        sourcekeys = self.seeds.list(**kwargs)
        dest = self.load_seeds(args.destination)
        destkeys = dest.list(**kwargs)
        messages = []
        if len(sourcekeys) == 1 and destkeys == []:
            self.logger.debug("ACTIONS: moveseed; now adding destination gkey: %s"
                % str(sourcekeys[0]))
            success = dest.add(sourcekeys[0])
            self.logger.debug("ACTIONS: moveseed; success: %s" %str(success))
            self.logger.debug("ACTIONS: moveseed; now deleting sourcekey: %s" % str(sourcekeys[0]))
            success = self.seeds.delete(sourcekeys[0])
            if success:
                success = dest.save()
                self.logger.debug("ACTIONS: moveseed; destination saved... %s" %str(success))
                success = self.seeds.save()
            messages.extend(["Successfully Moved %s seed: %s"
                % (args.seeds, str(success)), sourcekeys[0]])
            return messages
        elif len(sourcekeys):
            messages = ["Too many seeds found to move"]
            messages.extend(sourcekeys)
            return messages
        messages.append("Failed to Move seed:")
        messages.append(searchkey)
        messages.append('\n')
        messages.append("Source seeds found...")
        messages.extend(sourcekeys or ["None\n"])
        messages.append("Destination seeds found...")
        messages.extend(destkeys or ["None\n"])
        return messages


    def listkey(self, args):
        '''Action listskey method'''
        self.seeds = self.load_seeds(args.seeds)
        if self.seeds:
            handler = SeedHandler(self.logger)
            kwargs = handler.build_gkeydict(args)
            # get the desired seed
            keyresults = self.seeds.list(**kwargs)
            if keyresults and not args.nick == '*' and self.output:
                self.output(keyresults, "\n Found GKEY seeds:")
            elif keyresults and self.output:
                self.output(['all'], "\n Installed seeds:")
            else:
                self.logger.info("ACTIONS: listkey; "
                    "Matching seed entry not found")
                if args.nick:
                    return {"Search failed for: %s" % args.nick: False}
                elif args.name:
                    return {"Search failed for: %s" % args.name: False}
                else:
                    return {"Search failed for search term": False}
            # get confirmation
            # fill in code here
            keydir = self.config.get_key(args.seeds + "-keydir")
            self.logger.debug("ACTIONS: listkey; keysdir = %s" % keydir)
            self.gpg = GkeysGPG(self.config, keydir)
            results = {}
            #failed = []
            print(" GPG output:")
            for key in keyresults:
                if not key.keydir and not args.nick == '*':
                    self.logger.debug("ACTIONS: listkey; NO keydir... Ignoring")
                    return {"Failed: No keyid's found for %s" % key.name : ''}
                self.logger.debug("ACTIONS: listkey; listing keydir:"
                    + str(key.keydir))
                results[key.name] = self.gpg.list_keys(key.keydir)
                if self.config.options['print_results']:
                    print(results[key.name].output)
                    self.logger.debug("data output:\n" +
                        str(results[key.name].output))
                    #for result in results[key.name].status.data:
                        #print("key desired:", key.name, ", keydir listed:",
                            #result)
                        #self.logger.debug("data record: " + str(result))
                else:
                    return results
            return {'done': True}
        else:
            return {"No keydirs to list": False}


    def addkey(self, args):
        '''Action addkey method'''
        handler = SeedHandler(self.logger)
        kwargs = handler.build_gkeydict(args)
        self.logger.debug("ACTIONS: listseed; kwargs: %s" % str(kwargs))
        self.seeds = self.load_seeds(args.seeds)
        if self.seeds:
            # get the desired seed
            keyresults = self.seeds.list(**kwargs)
            if keyresults and not args.nick == '*' and self.output:
                self.output(keyresults, "\n Found GKEY seeds:")
            elif keyresults and self.output:
                self.output(['all'], "\n Installing seeds:")
            else:
                self.logger.info("ACTIONS: addkey; "
                    "Matching seed entry not found")
                if args.nick:
                    return {"Search failed for: %s" % args.nick: False}
                elif args.name:
                    return {"Search failed for: %s" % args.name: False}
                else:
                    return {"Search failed for search term": False}
            # get confirmation
            # fill in code here
            keydir = self.config.get_key(args.seeds + "-keydir")
            self.logger.debug("ACTIONS: addkey; keysdir = %s" % keydir)
            self.gpg = GkeysGPG(self.config, keydir)
            results = {}
            failed = []
            for key in keyresults:
                if not key.keyid and not key.longkeyid and not args.nick == '*':
                    self.logger.debug("ACTIONS: addkey; NO key id's to add... Ignoring")
                    return {"Failed: No keyid's found for %s" % key.name : ''}
                elif not key.keyid and not key.longkeyid:
                    print("No keyid's found for:", key.nick, key.name, "Skipping...")
                    failed.append(key)
                    continue
                self.logger.debug("ACTIONS: addkey; adding key:")
                self.logger.debug("ACTIONS: " + str(key))
                results[key.name] = self.gpg.add_key(key)
                for result in results[key.name]:
                    self.logger.debug("ACTIONS: addkey; result.failed = " +
                        str(result.failed))
                if self.config.options['print_results']:
                    for result in results[key.name]:
                        print("key desired:", key.name, ", key added:",
                            result.username, ", succeeded:",
                            not result.failed, ", keyid:", result.keyid,
                            ", fingerprint:", result.fingerprint)
                        self.logger.debug("stderr_out: " + str(result.stderr_out))
                        if result.failed:
                            failed.append(key)
            if failed and self.output:
                self.output(failed, "\n Failed to install:")
            return {'Completed': True}
        return {"No seeds to search or install": False}


    def removekey(self, args):
        '''Action removekey method'''
        pass


    def movekey(self, args):
        '''Action movekey method'''
        pass


    def installed(self, args):
        '''Action installed method.
        lists the installed key directories'''
        pass


    def user_confirm(self, message):
        '''Get input from the user to confirm to proceed
        with the desired action

        @param message: string, user promt message to display
        @return boolean: confirmation to proceed or abort
        '''
        pass


    def listseedfiles(self, args):
        seedsdir = self.config.get_key('seedsdir')
        files = os.listdir(seedsdir)
        return {"Seed files found at path: %s\n   %s"
            % (seedsdir, "\n   ".join(files)): True}
