Command-line Tools
==================

.. note:: The ``--help`` parameter can be used to see a list of commands available to each CLI tool.
    To see usage information for a specific subcommand, ``--help`` should be specified after the command.

    Ex: ``$ lmar x --help``

.. note:: Windows users running the pylivemaker CLI tools in CMD Prompt or PowerShell should ensure that your terminal font supports Japanese characters, otherwise the pylivemaker console output may be unreadable.
    The default terminal font in Windows 10 (Consolas) does not support Japanese characters, and needs to be changed to some font which includes Japanese characters (such as MS Gothic).
    Running pylivemaker CLI tools should not require changing your entire Windows system locale to Japanese.

lmar
----

Use ``lmar`` to work with LiveMaker archives and executables.
When handling split VFF archives, lmar commands should be passed the path to the ``.ext`` index file (if it exists).
For split archives without separate index files, the path to the first ``.dat`` file in the archive (usually ``game.dat``) should be used. ::

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

l (list)
^^^^^^^^

List the contents of a LiveMaker archive or executable. ::

    $ lmar l --help
    Usage: lmar l [OPTIONS] INPUT_FILE

      List the contents of the specified archive.

    Options:
      --help  Show this message and exit.

strip
^^^^^

``lmar strip`` copies only the Windows executable portion of a LiveMaker game .exe, and strips the game archive data from the output file.
This command should generally only be used by interested in reverse engineering the LiveMaker engine/interpreter. ::

    $ lmar strip --help
    Usage: lmar strip [OPTIONS] INPUT_FILE OUTPUT_FILE

      Copy the specified LiveMaker EXE but remove the LiveMaker archive.

      The resulting program cannot be run, but may be useful for reverse
      engineering or patching reasons.

    Options:
      --help  Show this message and exit.

x (extract)
^^^^^^^^^^^

Extract the contents of a LiveMaker archive or executable.

Image format modes:

gal (default)
    LiveMaker GAL (.gal) images will be extracted in their original format.
png
    Images will be converted to PNG before extraction.
both
    Both the original GAL image and a converted PNG version will be extracted.

.. note:: Refer to the documentation for ``galconvert`` for details on image conversion.

::

    $ lmar x --help
    Usage: lmar x [OPTIONS] file

      Extract the specified archive.

    Options:
      -n, --dry-run          Show what would be done without extracting any files.
      -i, --image-format [gal|png|both]
                                  Format for extracted images, defaults to GAL
                                  (original) format. If set to png, images
                                  will be converted before extraction. If set
                                  to both, both the original GAL and converted
                                  PNG images will be extracted
      -o, --output-dir TEXT  Output directory, defaults to current working
                             directory.
      -v, --verbose
      --help                 Show this message and exit.

lmgraph
-------

Generate a graphviz DOT syntax graph of branches between LiveNovel script files.

The output .dot file can be used with graphviz (or online tools like http://viz-js.com/)
to create a visual (PNG/PDF/etc) approximation of the original LiveMaker/LiveNovel
scenario flowchart. The output graph will include menu choice/route branch conditions
(as edge labels) if possible.

.. note:: The script currently uses a very naive implementation for following branch
    conditions, so the output labels may not always be 100% accurate. Conditions based
    on route flag variables may not be labeled properly, depending on the complexity
    of the original script logic.

::

    $ lmgraph --help
    Usage: lmgraph [OPTIONS] LSB_FILE [OUT_FILE]

      Generate a DOT syntax graph for a LiveNovel game.

      lsb_file should be a path to the root script node - this should always be
      ゲームメイン.lsb (game_main.lsb) for LiveMaker games. If output file is not
      specified, it defaults to <lsb_file>.dot

      The output graph will start with game_main as the root node and follow
      branches to all scenario scripts, which should give a general
      approximation of the original LiveMaker scenario chart.

    Options:
      --version  Show the version and exit.
      --help     Show this message and exit.

lmlpb
-----

Use ``lmlpb`` to work with LPB (LiveMaker project settings) files. ::

    $ lmlpb --help
    Usage: lmlpb [OPTIONS] COMMAND [ARGS]...

      Command-line tool for manipulating LPB project settings.

    Options:
      --version  Show the version and exit.
      --help     Show this message and exit.

    Commands:
      edit   Edit the specified LPB file.
      probe  Output information about the specified LPB file in human-readable...

probe
^^^^^

Output general information about an LPB file. ::

    Usage: lmlpb probe [OPTIONS] file

      Output information about the specified LPB file in human-readable form.

    Options:
      --help  Show this message and exit.

edit
^^^^

Edit project settings within an LPB file.

``lmlpb edit`` provides an interactive prompt that can be used to modify project settings in an LPB file.

For users generating translation patches, this command may be useful for modifying the application name, certain message prompts, and the default text display and audio settings.

.. warning:: This command should only be used by advanced users.
    Do not edit an LPB setting unless you are absolutely sure of what that setting does.
    Improper use of this command may cause undefined behavior (or a complete crash) in the LiveMaker engine during runtime.

::

    $ lmlpb edit --help
    Usage: lmlpb edit [OPTIONS] LPB_FILE

      Edit the specified LPB file.

      Only specific settings can be edited.

      The original LPB file will be backed up to <lpb_file>.bak

      Note: Setting empty fields to improper data types may cause undefined
      behavior in the LiveMaker engine. When editing a field, the data type of
      the new value is assumed to be the same as the original data type.

    Options:
      --help  Show this message and exit.

lmlsb
-----

Use ``lmlsb`` to work with LSB (compiled LiveMaker chart) files. ::

    $ lmlsb --help
    Usage: lmlsb [OPTIONS] COMMAND [ARGS]...

      Command-line tool for manipulating LSB scripts.

    Options:
      --version  Show the version and exit.
      --help     Show this message and exit.

    Commands:
      batchinsert  Compile specified LNS script directory and insert it into
                   the...

      dump         Dump the contents of the specified LSB file(s) to stdout in
                   a...

      edit         Edit the specified command within an LSB file.
      extract      Extract decompiled LiveNovel scripts from the specified
                   input...

      extractcsv   Extract text from the given LSB file to a CSV file.
      extractmenu  Extract menu choices from the given LSB file to a CSV file.
      insert       Compile specified LNS script and insert it into the
                   specified...

      insertcsv    Apply translated text lines from the given CSV file to given...
      insertmenu   Apply translated menu choices from the given CSV file to...
      probe        Output information about the specified LSB file in...
      validate     Verify that the specified LSB file(s) can be processed.

batchinsert
^^^^^^^^^^^

Insert multiple LNS scripts into an LSB file.
The ``SCRIPT_DIR`` argument should be a path to a directory generated by ``lmlsb extract`` (as ``batchinsert`` relies on the ``.lsbref`` file generated by ``extract``). ::

    $ lmlsb batchinsert --help
    Usage: lmlsb batchinsert [OPTIONS] LSB_FILE SCRIPT_DIR

      Compile specified LNS script directory and insert it into the specified
      LSB file according to the Reference file.

      The Reference file must be inside script_dir.

      script_dir should be an LNS script directory which was initially generated
      by lmlsb extract.

      The original LSB file will be backed up to <lsb_file>.bak unless the --no-
      backup option is specified.

    Options:
      -e, --encoding [cp932|utf-8]  The text encoding of script_file (defaults to
                                    utf-8).
      --no-backup                   Do not generate backup of original archive
                                    file(s).
      --help                        Show this message and exit.

dump
^^^^

Dump the contents of one or more LSB file(s) in a human-readable format.

Output format modes:

text (default)
    Plaintext that resembles LiveMaker's text ``.lsc`` format (but is not a 1 to 1 match with LiveMaker's format).
xml
    XML that resembles LiveMaker's XML ``.lsc`` format (but is not a 1 to 1 match with LiveMaker's format).
lines
    Only plaintext LNS script lines will be dumped. No LSB command data and no LNS script tag formatting will be included in the output.
    (This may be useful for generating a more traditional "script" to be used by translators.)

::

    $ lmlsb dump --help
    Usage: lmlsb dump [OPTIONS] INPUT_FILE...

      Dump the contents of the specified LSB file(s) to stdout in a human-
      readable format.

      For text mode, the full LSB will be output as human-readable text.

      For xml mode, the full LSB file will be output as an XML document.

      For lines mode, only text lines will be output.

    Options:
      -m, --mode [text|xml|lines]   Output mode (defaults to text)
      -e, --encoding [cp932|utf-8]  Output text encoding (defaults to utf-8).
      -o, --output-file FILE        Output file. If unspecified, output will be
                                    dumped to stdout.
      --help                        Show this message and exit.

edit
^^^^

Edit a specific command within an LSB file.

``lmlsb edit`` provides an interactive prompt that can be used to modify an LSB command.
This is command is mainly only provided as a (slightly) more user-friendly way of editing specific byte fields within an LSB file.

For users generating translation patches, this command may be useful for modifying text display parameters, and for modifying in-game "choice menu" text.

For more specific usage/implementation details refer to the thread in `issue #9 <https://github.com/pmrowla/pylivemaker/issues/9#issuecomment-506694249>`_.

.. note:: Only a specific subset of command types (and a specific set of parameters for each editable command type) can be modified via ``lmlsb edit``.

.. warning:: This command should only be used by advanced users.
    Do not edit an LSB command parameter unless you are absolutely sure of what that parameter does.
    Improper use of this command may cause undefined behavior (or a complete crash) in the LiveMaker engine during runtime.

::

    $ lmlsb edit --help
    Usage: lmlsb edit [OPTIONS] LSB_FILE LINE_NUMBER

      Edit the specified command within an LSB file.

      Only specific command types and specific fields can be edited.

      The original LSB file will be backed up to <lsb_file>.bak

      WARNING: This command should only be used by advanced users familiar with
      the LiveMaker engine. Improper use of this command may cause undefined
      behavior (or a complete crash) in the LiveMaker engine during runtime.

      Note: Setting empty fields to improper data types may cause undefined
      behavior in the LiveMaker engine. When editing a field, the data type of
      the new value is assumed to be the same as the original data type.

    Options:
      --help  Show this message and exit.

extract
^^^^^^^

Extract (decompiled) LiveNovel scenario scripts from an LSB file.

.. note:: The LNS format generated by pylivemaker is not an exact 1 to 1 match with LiveMaker's original LiveNovel script format.
    When modifying a script extracted via this command, users should be aware that all of LiveMaker's "pseudo-HTML" LiveNovel script tags are not supported by pylivemaker.
    For a detailed list of supported tags and how they are used by pylivemaker, please refer to the ``livemaker/lsb/novel.py`` source code.

::

    $ lmlsb extract --help
    Usage: lmlsb extract [OPTIONS] INPUT_FILE...

      Extract decompiled LiveNovel scripts from the specified input file(s).

      By default, extracted scripts will be encoded as utf-8, but if you intend
      to patch a script back into an LSB, you will still be limited to cp932
      characters only.

      Output files will be named <LSB name>-<scenario name>.lns

    Options:
      -e, --encoding [cp932|utf-8]  Output text encoding (defaults to utf-8).
      -o, --output-dir DIRECTORY    Output directory. Defaults to the current
                                    working directory if not specified. If
                                    directory does not exist it will be created.
      --help                        Show this message and exit.

insert
^^^^^^

Insert a single LNS script into an LSB file.

Users generating translation patches may be more interested in ``batchinsert``. ::

    lmlsb insert --help
    Usage: lmlsb insert [OPTIONS] LSB_FILE SCRIPT_FILE LINE_NUMBER

      Compile specified LNS script and insert it into the specified LSB file.

      The LSB command at line_number must be a TextIns command. The existing
      text block of the specified TextIns command will be replaced with the new
      one from script_file.

      script_file should be an LNS script which was initially generated by lmlsb
      extract.

      The original LSB file will be backed up to <lsb_file>.bak unless the --no-
      backup option is specified.

    Options:
      -e, --encoding [cp932|utf-8]  The text encoding of script_file (defaults to
                                    utf-8).
      --no-backup                   Do not generate backup of original archive
                                    file(s).
      --help                        Show this message and exit.

extractcsv
^^^^^^^^^^

Extract LiveNovel scenario text lines from an LSB file to a CSV file.

.. note:: Only text lines are extracted, so some formatting information may be lost.
   For translating games which make heavy use of formatting tags, you may need to consider using
   ``lmlsb extract`` and ``lmlsb insert`` to translate fully decompiled scripts instead of using
   the CSV commands.

::

    lmlsb extractcsv --help
    Usage: lmlsb extractcsv [OPTIONS] LSB_FILE CSV_FILE

      Extract text lines from the given LSB file to a CSV file.

      You can open this csv file for translation in most table calc programs
      (Excel, open/libre office calc, ...). Just remember to choose comma as
      delimiter and " as quotechar.

      You can use the --append option to add the text data from this lsb file to
      a existing csv. With the --overwrite option an existing csv will be
      overwritten without warning.

      NOTE: Formatting tags will be lost when using this command in conjunction
      with insertcsv. For translating games which use formatting tags, you may
      need to work directly with LNS scripts using the extract and
      insert/batchinsert commands.

    Options:
      --overwrite  Overwrite existing csv file.
      --append     Append text data to existing csv file.
      --help       Show this message and exit.

insertcsv
^^^^^^^^^

Insert (translated) LiveNovel scenario text lines from a CSV file into an LSB file. ::

    lmlsb insertcsv --help
    Usage: lmlsb insertcsv [OPTIONS] LSB_FILE CSV_FILE

      Apply translated text lines from the given CSV file to given LSB file.

      CSV_FILE should be a file previously created by the extractcsv command,
      with added translations. The original LSB file will be backed up to
      <lsb_file>.bak unless the --no-backup option is specified.

    Options:
      --no-backup  Do not generate backup of original lsb file.
      --help       Show this message and exit.

probe
^^^^^

Output general information about an LSB file.

Most of the information generated by ``lmlsb probe`` is only useful to developers, but users generating translation patches may be interested in the script character/line counts. ::

    lmlsb probe --help
    Usage: lmlsb probe [OPTIONS] file

      Output information about the specified LSB file in human-readable form.

      Novel script scenario character and line count are estimates. Depending on
      how a script was originally created, actual char/line counts may vary.

    Options:
      --help  Show this message and exit.

validate
^^^^^^^^

Validate that LSB file(s) can be processed by pylivemaker.

This command is probably only useful for pylivemaker developers. ::

    $ lmlsb validate --help
    Usage: lmlsb validate [OPTIONS] file

      Verify that the specified LSB file(s) can be processed.

      Validation is done by disassembling an input file, reassembling it, and
      then comparing the SHA256 digests of the original and reassembled versions
      of the file.

      If a file contains text scenarios, a test will also be done to verify that
      the scenarios can be decompiled, recompiled, and then reinserted into the
      lsb file.

    Options:
      --help  Show this message and exit.

lmpatch
-------

Use ``lmpatch`` to replace individual LSB files in an existing LiveMaker archive or executable. ::

    $ lmpatch --help
    Usage: lmpatch [OPTIONS] EXE_FILE PATCHED_LSB

      Patch a LiveMaker game.

      Any existing version of patched_lsb will be replaced in the specified
      LiveMaker executable. If a file with the same name as patched_lsb does not
      already exist, this will do nothing.

      A backup copy of the old exe will also be created.

    Options:
      --help  Show this message and exit.

galconvert
----------

``galconvert`` can be used to convert from LiveMaker's Gale/GaleX (GAL) image format into any format supported by
PIL/Pillow.

.. note:: It is recommended to convert to image formats which support transparency (alpha channel) such as PNG.
    If a GAL image contains multiple frames, only the first frame will be used when converting to a format which
    does not support multiple frames.

    Direct conversion to GAL format is not currently supported. If you need to generate GAL images,
    it is recommended to use LiveMaker's ``BmpToGale`` program in conjunction with ``lmbmp``.

::

    galconvert --help
    Usage: galconvert [OPTIONS] INPUT_FILE OUTPUT_FILE

      Convert the image to another format.

      GAL(X) images can only be read (for conversion to JPEG/PNG/etc) at this
      time.

      Output format will be determined based on file extension.

    Options:
      -f, --force  Overwrite output file if it exists.
      --help       Show this message and exit.

lmbmp
-----

``lmbmp`` can be used to convert an image to a set of bitmap files which can then be used with LiveMaker's
``BmpToGale`` tool. ::

    $ lmbmp --help
    Usage: lmbmp [OPTIONS] INPUT_FILE

      Convert image to BMP(s) which can be used with bmp2gale.

      If the input file contains an alpha layer, a mask bitmap will be
      generated. Output files will be named <input_name>.bmp and
      <input_name>-m.bmp.

    Options:
      --version    Show the version and exit.
      -f, --force  Overwrite output file if it exists.
      --help       Show this message and exit.
