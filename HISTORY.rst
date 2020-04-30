=======
History
=======

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
