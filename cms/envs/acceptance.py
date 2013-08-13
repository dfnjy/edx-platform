"""
This config file extends the test environment configuration
so that we can run the lettuce acceptance tests.
"""

# We intentionally define lots of variables that aren't used, and
# want to import all variables from base settings files
# pylint: disable=W0401, W0614

from .test import *
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

# You need to start the server in debug mode,
# otherwise the browser will not render the pages correctly
DEBUG = True

# Disable warnings for acceptance tests, to make the logs readable
import logging
logging.disable(logging.ERROR)
import os
from random import choice
PORTS = [80, 443, 888, 2000, 2001, 2020, 2109, 2222, 2310, 3000, 3001,
        3030, 3210, 3333, 4000, 4001, 4040, 4321, 4502, 4503, 5000, 5001,
        5050, 5555, 5432, 6000, 6001, 6060, 6666, 6543, 7000, 7070, 7774,
        7777, 8000, 8001, 8003, 8031, 8080, 8081, 8765, 8888, 9000, 9001,
        9080, 9090, 9876, 9999, 49221, 55001]


def seed():
    return os.getppid()

MODULESTORE_OPTIONS = {
    'default_class': 'xmodule.raw_module.RawDescriptor',
    'host': 'localhost',
    'db': 'acceptance_xmodule',
    'collection': 'acceptance_modulestore_%s' % seed(),
    'fs_root': TEST_ROOT / "data",
    'render_template': 'mitxmako.shortcuts.render_to_string',
}

MODULESTORE = {
    'default': {
        'ENGINE': 'xmodule.modulestore.draft.DraftModuleStore',
        'OPTIONS': MODULESTORE_OPTIONS
    },
    'direct': {
        'ENGINE': 'xmodule.modulestore.mongo.MongoModuleStore',
        'OPTIONS': MODULESTORE_OPTIONS
    },
    'draft': {
        'ENGINE': 'xmodule.modulestore.draft.DraftModuleStore',
        'OPTIONS': MODULESTORE_OPTIONS
    }
}

CONTENTSTORE = {
    'ENGINE': 'xmodule.contentstore.mongo.MongoContentStore',
    'OPTIONS': {
        'host': 'localhost',
        'db': 'acceptance_xcontent_%s' % seed(),
    },
    # allow for additional options that can be keyed on a name, e.g. 'trashcan'
    'ADDITIONAL_OPTIONS': {
        'trashcan': {
            'bucket': 'trash_fs'
        }
    }
}

# Set this up so that rake lms[acceptance] and running the
# harvest command both use the same (test) database
# which they can flush without messing up your dev db
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': TEST_ROOT / "db" / "test_mitx_%s.db" % seed(),
        'TEST_NAME': TEST_ROOT / "db" / "test_mitx_%s.db" % seed(),
    }
}

# Use the auto_auth workflow for creating users and logging them in
MITX_FEATURES['AUTOMATIC_AUTH_FOR_TESTING'] = True


# Information needed to utilize Sauce Labs.
MITX_FEATURES['SAUCE'] = {
    'USE' : False,
    'USERNAME' : '<USERNAME>',
    'ACCESS_ID' : '<ACCESS_ID>',
    'BROWSER' : DesiredCapabilities.CHROME,
    'PLATFORM' : 'Linux',
    'VERSION' : '',
    'DEVICE' : '',
    'SESSION' : 'Lettuce Tests',
    'BUILD' : 'CMS TESTS',
    'CUSTOM_TAGS' : {}
}


# Include the lettuce app for acceptance testing, including the 'harvest' django-admin command
INSTALLED_APPS += ('lettuce.django',)
LETTUCE_APPS = ('contentstore',)
LETTUCE_SERVER_PORT = choice(PORTS)
LETTUCE_BROWSER = 'chrome'
