#
#-*- coding:utf-8 -*-

"""
    Gentoo-Keys - gkeygen/checks.py

    Primary key checks module
    @copyright: 2014 by Brian Dolbec <dolsen@gentoo.org>
    @license: GNU GPL2, see COPYING for details
"""


from gkeys.config import GKEY_CHECK


ALGORITHM_CODES = {
    '1': 'RSA',
    '2': 'RSA',      # (encrypt only)
    '3': 'RSA',      # (sign only)
    '16': 'ElGamal', # (encrypt only)
    '17': 'DSA',     #(sometimes called DH, sign only)
    '18': 'ECDH',
    '19': 'ECDSA',
    '20': 'ElGamal'  # (sign and encrypt)
}

# Default glep 63 minimum gpg key specification
TEST_SPEC = {
    'bits': {
        'DSA': 2048,
        'RSA': 2048,
        },
    'expire': 36,      # in months
    'subkeys': {        # warning/error mode
        'encrypt': {
            'mode': 'notice',
            'expire': -1,  # -1 is the primary key expirery
            },
        'sign': {
            'mode': 'error',
            'expire': 12,
            },
        },
    'type': ['DSA', 'RSA', '1', '2', '3', '17'],
    'version': 4,
}


class KeyChecks(object):
    '''Primary gpg key validation and glep spec checks class'''

    def __init__(self, logger, spec=TEST_SPEC):
        '''@param spec: optional gpg specification to test against
                        Defaults to TEST_SPEC

        '''
        self.logger = logger
        self.spec = spec


    def validity_checks(self, keydir, keyid, result):
        '''Check the specified result based on the seed type

        @param keydir: the keydir to list the keys for
        @param keyid: the keyid to check
        @param result: pyGPG.output.GPGResult object
        @returns: GKEY_CHECK instance
        '''
        revoked = expired = invalid = sign = False
        for data in result.status.data:
            if data.name ==  "PUB":
                if data.long_keyid == keyid[2:]:
                    # check if revoked
                    if 'r' in data.validity:
                        revoked = True
                        self.logger.debug("ERROR in key %s : revoked" % data.long_keyid)
                        break
                    # if primary key expired, all subkeys expire
                    if 'e' in data.validity:
                        expired = True
                        self.logger.debug("ERROR in key %s : expired" % data.long_keyid)
                        break
                    # check if invalid
                    if 'i' in data.validity:
                        invalid = True
                        self.logger.debug("ERROR in key %s : invalid" % data.long_keyid)
                        break
                    if 's' in data.key_capabilities:
                        sign = True
                        self.logger.debug("INFO primary key %s : key signing capabilities" % data.long_keyid)
            if data.name == "SUB":
                # check if invalid
                if 'i' in data.validity:
                    self.logger.debug("WARNING in subkey %s : invalid" % data.long_keyid)
                    continue
                # check if expired
                if 'e' in data.validity:
                    self.logger.debug("WARNING in subkey %s : expired" % data.long_keyid)
                    continue
                # check if revoked
                if 'r' in data.validity:
                    self.logger.debug("WARNING in subkey %s : revoked" % data.long_keyid)
                    continue
                # check if subkey has signing capabilities
                if 's' in data.key_capabilities:
                    sign = True
                    self.logger.debug("INFO subkey %s : subkey signing capabilities" % data.long_keyid)
        return GKEY_CHECK(keyid, revoked, expired, invalid, sign)


    def glep_check(self, keydir, keyid, result):
        '''Performs the minimum specifications checks on the key'''
        pass


