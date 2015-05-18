#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
module for configuration
'''

from transwarp.tool import SimpleDict

def _to_dict(d):
    D = SimpleDict()
    for k, v in d.iteritems():
        D[k] = _to_dict(v) if isinstance(v, dict) else v
    return D

def _merge(defaults, overrides):
    r = {}
    for k, v in defaults.iteritems():
        if k in overrides:
            if isinstance(v, dict):
                r[k] = _merge(v, overrides[k])
            else:
                r[k] = overrides[k]
        else:
            r[k] = v
    return r

import config_default
configs = config_default.configs

try:
    import config_override
    configs = _merge(configs, config_override.configs)
except ImportError:
    pass

configs = _to_dict(configs)
