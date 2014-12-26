#
#-*- coding:utf-8 -*-

from __future__ import print_function


import sys


from gkeys.base import CliBase
from gkeys.config import GKeysConfig
from gkeyldap.actions import (Actions, Available_Actions, Action_Options,
    Action_Map)


class Main(CliBase):
    '''Main command line interface class'''


    def __init__(self, root=None, config=None, print_results=True):
        """ Main class init function.

        @param root: string, root path to use
        @param config: optional GKeysConfig instance, For API use
        @param print_results: optional boolean, for API use
        """
        self.root = root or "/"
        self.config = config or GKeysConfig(root=root)
        self.config.options['print_results'] = print_results
        self.args = None
        self.seeds = None
        self.cli_config = {
            'Actions': Actions,
            'Available_Actions': Available_Actions,
            'Action_Options': Action_Options,
            'Action_Map': Action_Map,
            'prog': 'gkey-ldap',
            'description': 'Gentoo-keys LDAP interface and seed file generator program',
            'epilog': '''CAUTION: adding UNTRUSTED keys can be HAZARDOUS to your system!'''
        }


    def __call__(self, args=None):
        """Main class call function

        @param args: Optional list of argumanets to parse and action to run
                     Defaults to sys.argv[1:]
        """
        if args:
            return self.run(self.parse_args(args))
        else:
            return self.run(self.parse_args(sys.argv[1:]))

