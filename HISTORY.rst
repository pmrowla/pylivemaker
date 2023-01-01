=======
History
=======

1.0.4 (2023-01-01)
------------------

This will be the final release which supports Python <3.8.

* Fix issue parsing ``TXSPD`` tags

1.0.3 (2022-12-26)
------------------

* Fix issue with ``click.get_terminal_size`` deprecation

1.0.2 (2021-05-03)
------------------

* Fix issue where text padding could be parsed into None-type

1.0.1 (2020-10-25)
------------------

* Fix menu support for certain LM engine versions
* Add experimental ruby/furigana support (supported in LNS scripts only)

1.0.0 (2020-07-01)
------------------

* Added ``lmlpb`` tool for editing LPB project parameters
* Added ``livemaker.lsb.translate`` API
* Added menu translation API, text and LPM (image) menus are now supported
* Standardized CSV format for translatable text
* All CSV commands now support the ``--encoding`` parameter
* Fixed old logging bugs
* Added experimental ``lmgraph lsb`` command for generating LSB file execution graphs
* Added ``lmbmp`` helper utility for generating ``BmpToGale`` compatible image + mask pairs

Known issues:

* CSV scenario script translation does not currently support formatting tags.
  If you need advanced tag support, you will need to use the LNS script
  translation method.

Deprecated:

* ``--mode=lines`` for scenario text CSV commands
* Old CSV format (CSV files generated in 0.3.x are not compatible with 1.0)

0.3.2 (2020-05-04)
------------------

This will be the final release before v1.0.0 (which will break backwards compatibility with this release).

* Added ``extractcsv`` command for extracting scenario text to a CSV file
* Added ``insertcsv`` command for replacing scenario text from a CSV file
* Added ``lmlpb`` CLI tool for manipulating LPB project settings files.

Known issues:

* `extractmenu` and `insertmenu` commands only support using system locale/encoding when reading and writing CSV files.

Deprecated:

* Python 3.5 support.
  Future releases of pylivemaker will require Python 3.6 and later.
* Existing CSV CLI tool is deprecated.
  Future releases of pylivemaker will use a different CSV format which will not be compatible with CSV files generated in this release.

0.3.0 (2020-04-30)
------------------

* Added `extractmenu` command for extracting in-game menus to a CSV file
* Added `insertmenu` command for replacing in-game menus from a CSV file
* `lmpatch` now supports batch/recursive patching

0.2.1 (2020-03-13)
------------------

* Added `lmgraph` command for generating LSB script call graphs
* Refactored CLI tools (each tool moved to its own source file)

0.2.0 (2020-02-16)
------------------

* Added support for reading LM Pro scrambled (encrypted) archives
* ``HAlignEnum`` and ``VAlignEnum`` in ``livemaker/lsb/novel.py`` have been removed and replaced with ``AlignEnum``

0.1.2 (2020-02-05)
------------------

* Added support for split VFF archives
* Added ``lmlsb edit`` command
* Added ``lmlsb batchinsert`` command
* Added support for reading GAL images, and ``galconvert`` CLI tool

0.1.0 (2019-03-07)
------------------

* First release on PyPI.
