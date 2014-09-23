GitLab Hook for YouTrack
========================

This project provides a small HTTP endpoint to process the payload of a webhook
sent by GitLab.

It creates a comment in each referenced issue mentioning the author, the commit
message, and a link to the commit page in GitLab.


Documentation
-------------

See the [project's wiki](https://github.com/gini/youtrack-githook/wiki).


Development Environment
-----------------------

This project is using Flask and the YouTrack REST Python Library, both of which
still depend on Python 2.x.

The easiest way to start developing is using virtualenv:

    virtualenv -p python2 VENV
    . VENV/bin/activate
    pip install -r requirements.txt


Support
-------

Please log tickets and issues at our [project site](https://github.com/gini/youtrack-githook/issues).


License
-------

Copyright (c) 2013 smarchive GmbH, Gini GmbH
Copyright (c) 2014 Gini GmbH

This script is licensed under the Apache License, Version 2.0.

See http://www.apache.org/licenses/LICENSE-2.0.html for the full license text.
