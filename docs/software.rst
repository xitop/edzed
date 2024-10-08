============
Installation
============

Prerequisites
=============

Edzed was developed, tested and deployed on Linux systems only.
We hope it runs also on Windows, but we don't know. If you can install
it on Windows and run the unit tests, please report the result.

Edzed needs Python 3.9 or newer. No third party libraries are required.

Unit tests require ``pytest`` with the ``pytest-asyncio``
and ``pytest-forked`` plugins.


Installing
==========

We recommend using a virtual environment. If you don't want a virtual
environment, consider an installation to user's local directory with
the ``--user`` option.

Install from PyPi with::

  python3 -m pip install --upgrade edzed

Alternatively install from github with::

  python3 -m pip install --upgrade git+https://github.com/xitop/edzed.git

Releases containing only negligible code changes are sometimes
not uploaded to PyPi.
