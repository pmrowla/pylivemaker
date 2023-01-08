===========
pylivemaker
===========


.. image:: https://img.shields.io/pypi/v/pylivemaker.svg
        :target: https://pypi.python.org/pypi/pylivemaker

.. image:: https://github.com/pmrowla/pylivemaker/actions/workflows/tests.yml/badge.svg?branch=master
        :target: https://github.com/pmrowla/pylivemaker/actions/workflows/tests.yml

.. image:: https://readthedocs.org/projects/pylivemaker/badge/?version=latest
        :target: https://pylivemaker.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status




Python package for manipulating LiveMaker 3 game resources.
Specifically intended to work with LiveNovel VN's, but extraction
should also work for other LiveMaker games.

Based on tinfoil's irl_.

Requires Python 3 (3.8 and later).


* Free software: GNU General Public License v3
* Documentation: https://pylivemaker.readthedocs.io.

.. _irl: https://bitbucket.org/tinfoil/irl


Features
--------

* Extract files from a LiveMaker .exe or .dat file.
* Dump LSB files to human-readable text or XML (similar to LiveMaker's XML .lsc format).
* Extract LiveNovel LNS scripts from LSB files.
* Compile (modified) LNS scripts and insert them into LSB files.
* Patch (modified) LSB files into an existing .exe or .dat file.

License
-------

pylivemaker / irl
^^^^^^^^^^^^^^^^^

Copyright (C) 2020 Peter Rowlands

Copyright (C) 2014 tinfoil

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Python
^^^^^^

Copyright (c) 2001-2019 Python Software Foundation. All rights reserved.

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
