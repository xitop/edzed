============
Installation
============

Prerequisites
=============

Edzed was developed, tested and deployed on Linux systems only.
We hope it runs also on Windows, but we don't know. If you can install
it on Windows and run the unit tests, please report the result.

Edzed needs Python 3.7 or 3.8. No third party libraries are required.

Unit tests require ``pytest`` with the ``pytest-asyncio`` plugin.


Installing from github
======================

Install with::

  pip3 install --upgrade --user git+https://github.com/xitop/edzed.git

Omit the ``--user`` option in an activated virtual environment
or for a system-wide installation.
