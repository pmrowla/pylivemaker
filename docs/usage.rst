=====
Usage
=====

API Examples
------------

Look at the `livemaker.cli` and `livemaker.patch` modules for usage examples.

Command-line tools
------------------

lmar
^^^^

Use ``lmar`` to work with LiveMaker archives and executables::

    $ lmar --help
    Usage: lmar [OPTIONS] COMMAND [ARGS]...

      Command-line tool for manipulating LiveMaker archives and EXEs.

    Options:
      --version  Show the version and exit.
      --help     Show this message and exit.

    Commands:
      l      List the contents of the specified archive.
      strip  Copy the specified LiveMaker EXE but remove the LiveMaker archive.
      x      Extract the specified archive.

lmlsb
^^^^^

Use ``lmlsb`` to work with LSB (compiled LiveMaker chart) files::

    $ lmlsb --help
    Usage: lmlsb [OPTIONS] COMMAND [ARGS]...

      Command-line tool for manipulating LSB scripts.

    Options:
      --version  Show the version and exit.
      --help     Show this message and exit.

    Commands:
      dump      Dump the contents of the specified LSB file(s) to stdout in a...
      extract   Extract decompiled LiveNovel scripts from the specified input...
      insert    Compile specified LNS script and insert it into the specified...
      probe     Output information about the specified LSB file in...
      validate  Verify that the specified LSB file(s) can be processed.

lmpatch
^^^^^^^

Use ``lmpatch`` to replace individual LSB files in an existing LiveMaker archive or executable::

    $ lmpatch --help
    Usage: lmpatch [OPTIONS] EXE_FILE PATCHED_LSB

      Patch a LiveMaker game.

      Any existing version of patched_lsb will be replaced in the specified
      LiveMaker executable. If a file with the same name as patched_lsb does not
      already exist, this will do nothing.

      A backup copy of the old exe will also be created.

    Options:
      --help  Show this message and exit.

Example
-------

To try and patch something:

1. Extract game files.::

    $ mkdir game_files
    $ lmar x game.exe -o game_files

2. Dump some lsb files.
   I suggest starting with ``ゲームメイン.lsb`` (``gamemain.lsb``), and then looking for the first user script to be called (generally ``00000001.lsb``) and continue from there.
   If you are familiar with LiveNovel, ``ゲームメイン.lsb`` is the root game start chart node.::

    $ cd game_files
    $ lmlsb dump ゲームメイン.lsb > gamemain.txt
    $ lmlsb dump 00000001.lsb > 00000001.lsb.txt

3. Once you've found an lsb with a script you want to edit, extract it.::

    $ mkdir orig_scripts
    $ lmlsb extract 00000001.lsb -o orig_scripts

4. Edit the script.::

    $ mkdir translated_scripts
    $ cp orig_scripts/*.lns translated_scripts
    <run your favorite text editor on whatever script you want to translate>

5. Patch the new script back into the lsb.::

    $ lmlsb insert 00000001.lsb scripts_dir/<translated_script>.lns 1234

   (where 1234 is the appropriate TextIns command line number).

6. Patch the exe (for now the .lsb file must be in the same directory as the exe, since there is no command line option to set the correct archive entry path).::

    $ lmpatch some.exe 00000001.lsb
