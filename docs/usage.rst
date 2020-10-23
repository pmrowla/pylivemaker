Usage
=====

API Examples
------------

Look at the `livemaker.cli` and `livemaker.patch` modules for usage examples.

Patching Example
----------------

To try and patch something:

1. Extract game files. ::

    $ mkdir game_files
    $ lmar x game.exe -o game_files

2. Dump some lsb files.
   I suggest starting with ``ゲームメイン.lsb`` (``gamemain.lsb``), and then looking for the first user script to be called (generally ``00000001.lsb``) and continue from there.
   If you are familiar with LiveNovel, ``ゲームメイン.lsb`` is the root game start chart node. ::

    $ cd game_files
    $ lmlsb dump ゲームメイン.lsb > gamemain.txt
    $ lmlsb dump 00000001.lsb > 00000001.lsb.txt

3. Once you've found an LSB with a script you want to edit, scenario text lines from an LSB can be extracted into a CSV file. ::

    $ lmlsb extractcsv --encoding=utf-8-sig 00000001.lsb 00000001.csv

.. note:: It is also possible to extract, translate and insert multiple LSB files
   using a single CSV file. For details refer to this discussion:
   https://github.com/pmrowla/pylivemaker/issues/58#issuecomment-626787758

4. Edit the CSV using your preferred spreadsheet tool. To translate a text block,
   simply add your translation in the "Translated text" column.

.. image:: https://user-images.githubusercontent.com/651988/80898950-d770ae00-8d44-11ea-8772-99e49f3b8482.png
   :width: 500

.. note:: For text blocks spanning multiple lines, newlines in the translated
   text cell will be preserved in-game as line breaks.

5. Patch the translated CSV back into the lsb. ::

   $ lmlsb insertcsv --encoding=utf-8-sig 00000001.lsb 00000001.csv

.. note:: The recommended way to translate scripts in pylivemaker 1.0
   is via the CSV tools. ``extractmenu`` and ``insertmenu`` can be used
   to translate in-game text menus via CSV files as well. For more details
   on the CSV tools, refer to this (and related) github discussions:
   https://github.com/pmrowla/pylivemaker/pull/37

6. Patch the exe (for now the .lsb file must be in the same directory as the exe, since there is no command line option to set the correct archive entry path). ::

    $ lmpatch some.exe 00000001.lsb

Patching with LNS scripts
^^^^^^^^^^^^^^^^^^^^^^^^^

LNS scripts can be extracted and edited as well, in the event that you
need support for more advanced script tags which are not supported by
the CSV translation API.

Example (replaces steps 3 through 5 from above):

3. Once you've found an lsb with a script you want to edit, extract it. ::

    $ mkdir orig_scripts
    $ lmlsb extract 00000001.lsb -o orig_scripts

4. Edit the script. ::

    $ mkdir translated_scripts
    $ cp orig_scripts/*.lns translated_scripts
    <run your favorite text editor on whatever script you want to translate>

5. Patch the new script back into the lsb. ::

    $ lmlsb insert 00000001.lsb scripts_dir/<translated_script>.lns 1234

   (where 1234 is the appropriate TextIns command line number).

Notes for Translation Patches
-----------------------------

Latin Character Display
^^^^^^^^^^^^^^^^^^^^^^^

By default, LiveMaker games will display text using full-width latin characters, which causes text translated into any Western language to look very bad in-game.
For LiveMaker 3 based games, this behavior can be modified, but for LiveMaker 2 games, I am unaware of any solution for this issue.

To force LiveMaker 3 games to display text using half-width latin characters, the ``PR_FONTCHANGEABLED`` parameter must be set to ``0`` for the given message box type.
This can be handled by using the ``lmlsb edit`` pylivemaker command.

The default settings for each LiveMaker message box type are set via ``MesNew`` commands, in the system ``メッセージボックス作成.lsb`` (create_message_box.lsb) file.
For the standard in-game text, users will want to modify the command corresponding to the ``メッセージボックス`` (message_box) box type (box type is the first parameter to ``MesNew``).
In most cases, this should be command number 36 in ``メッセージボックス作成.lsb``.

Example::

    $ lmlsb edit メッセージボックス作成.lsb 36
    36: MesNew "メッセージボックス" "メッセージボックス土台" 10 10 GetProp("メッセージボックス土台", 5) - 10 - 10 GetProp("メッセージボックス土台", 6) - 10 - 10
    1100   "ＭＳ ゴシック" 16 6 16777215 16711680 0 16776960 1  0 "ノベルシステム\メッセージボックス\再生中.lsc" "ノベルシステム\メッセージボックス\イベント.lsc"
        "ノベルシステム\メッセージボックス\右クリック時.lsc"    "ノベルシステム\メッセージボックス\終了.lsc" "ノベルシステム\メッセージボックス\リンク.lsc" 1 4 0
      "ノベルシステム\メッセージボックス\再生開始.lsc"  "ノベルシステム\メッセージボックス\アイドル時.lsc"     0 0 0    0    1 0

    Enter new value for each field (or keep existing value)
    Name ["メッセージボックス"]: <skipping uneditable field>
    PR_PARENT ["メッセージボックス土台"]: <skipping uneditable field>
    PR_LEFT [10]:
    PR_TOP [10]:
    PR_WIDTH [GetProp("メッセージボックス土台", 5) - 10 - 10]: <skipping uneditable field>
    PR_HEIGHT [GetProp("メッセージボックス土台", 6) - 10 - 10]: <skipping uneditable field>
    PR_ALPHA []: <skipping uneditable field>
    PR_PRIORITY [1100]:
    ...
    PR_TAG []: <skipping uneditable field>
    PR_CAPTURELINK [1]:
    PR_FONTCHANGEABLED [1]: 0
    PR_PADDINGLEFT []: <skipping uneditable field>
    PR_PADDING_RIGHT []: <skipping uneditable field>
    Backing up original LSB.
    Wrote new LSB.

In the above example, ``lmlsb edit`` is used to modify command #36 within ``メッセージボックス作成.lsb``.
The existing values (shown in ``[]`` brackets) are kept for every field except for ``PR_FONTCHANGEABLED``.
By changing that value to ``0``, the standard in-game text box should now be displayed using half-width latin characters.

For more details refer to the thread in `issue #9 <https://github.com/pmrowla/pylivemaker/issues/9#issuecomment-506694249>`_.

.. note:: There are multiple possible LiveMaker message box types (including menus/history/etc), so users generating a full translation patch may need to modify multiple ``MesBox`` commands to have their translated text displayed properly everywhere in-game.

Translating System Menus
^^^^^^^^^^^^^^^^^^^^^^^^

To translate the main LiveMaker system menus, ``lmlsb edit`` can be used to translate strings in the system menu LSB files (such as ``ノベルシステム/システムメニュー/オプション選択時.lsb``/``novel_system/system_menu/on_option_selection.lsb``).

For more details refer to the thread in `issue #19 <https://github.com/pmrowla/pylivemaker/issues/19>`_.

pylivemaker-tools
^^^^^^^^^^^^^^^^^

Github user @Stefan311 has provided a collection of scripts which may be useful to translators.
See: https://github.com/Stefan311/pylivemaker-tools.

In particular, ``extractstrings.py`` and ``insertstrings.py`` can be used to translate strings inside LSB commands which are not supported by pylivemaker's ``lmlsb edit`` tool.
