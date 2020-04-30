LiveNovel Basic Information
===========================

Screen layout
-------------

How to use the chart window
---------------------------

How to use the scenario window
------------------------------

Chart list
----------

Charts can be organized into folders.
You can change folder order and chart order with the up and down arrow buttons on the left.
Right-click to bring up a pop-up menu.

.. image:: /_static/LiveNovel/ln_turorial64.png
    :alt: Chart list window

フォルダ作成 (Create folder)
    Create a new subfolder inside the selected folder.

追加 (Add)
    Create a new chart.

複製 (Duplicate)
    Duplicate the selected chart.

開く (Open)
    Open the selected chart.

新規ウィンドウで開く (Open in new window)
    Open the selected chart selected in a new window.

削除 (Delete)
    Delete the selected chart.

プロパティ (Properties)
    Display the properties for the selected chart.

Variable list
-------------

.. image:: /_static/LiveNovel/ln_var02.gif
    :alt: Variable list window

Variables set in ``変数リスト`` (Variable list) are global.
They can be accessed (both read/write) from all charts and nodes (as opposed to chart and compute node variables, which have limited scope).

.. list-table::
    :header-rows: 1

    * - Item
      - Description
    * - 名前 (Name)
      - Must be unique (cannot overlap with a chart or calculation variable).
    * - タイプ (Type)
      - 整数 (Integer)
            Signed integer number.

        実数 (Real)
            Signed decimal number.

        フラグ (Flag)
            Boolean flag, either ``TRUE`` or ``FALSE``.

        文字列 (String)
            Variable length (CP932 encoded) string.
    * - 初期値 (Default value)
      - Initial value stored in the variable.
    * - 動作タイプ (Operation type)
      - 通常 (Normal)
            Initialized at game start-up and reset at the following:

            - Player returns to title screen via system menu.
            - Game enters Scene Recollection mode
            - Title screen is displayed after a game over

        起動時のみ初期化 (Start-up only initialization)
            Only initialized at game start-up.

        ステータス (Status)
            Only initialized when game is started for the very first time after installation.
            Value is saved when the game is exited, and restored when the game is relaunched.

Node type
---------

Properties
----------

Scenario script
---------------

HTML-like scenario script file syntax.

* Attributes with a default value are optional.
    All other attributes are required.
* Tags are not case-sensitive.
* Lines starting with a semicolon (``;``) are treated as comments.
    If you need to begin an actual line with a semicolon, escape it with ``\;``.
* When using special characters (``{``, ``}``, ``<``, ``>``, ``\``) escape them with a preceding backslash (``\``).

Sample script: :ref:`First scenario from "GTE·SP"</_static/LiveNovel/スクリプト例.txt>`

.. note:: pylivemaker attempts to approximate this script syntax when extracting scenario scripts, but the syntax used by pylivemaker is not a one-to-one match with LiveMaker's syntax.

    A majority of these tags are compiled into one or more LM system events when generating a binary LSB, and as a result, the original tags cannot be recovered/decompiled by pylivemaker.

.. list-table::
    :header-rows: 1

    * - Tag
      - Description
    * - <BR>
      -
    * - <PG>
      -
    * - <CLR>
      -
    * - <WAIT TIME=n CLICKABORT=[ON/OFF] SKIPENABLED=[ON/OFF]>
      -
    * - <WAITFOR NAME=s CLICKABORT=[ON/OFF]>
      -
    * - <FLIP NAME=s EFFECT=s TIME=n REVERSE=[ON/OFF] PARAM1=n PARAM2=n SOURCE=s DEFAULT=[ON/OFF]>
      -
    * - <IMAGE NAME=s SOURCE=s X=[L/C/R/n] Y=[T/C/B/n] FLIPH=[ON/OFF] FLIPV=[ON/OFF] ALPHA=n PRIORITY=s FLIP=s MODE=[N/R/W/F] CLIPFILE=s>
      -
    * - <CHGIMG NAME=s SOURCE=s FLIPH=[ON/OFF] FLIPV=[ON/OFF] FLIP=s MODE=[N/R/W/F]>
      -
    * - <DELIMG NAME=s,s... FLIP=s>
      -
    * - <CGCHAR SET=s NAME=s PARENT=s X=[L/C/R/n] Y=[T/C/B/n] ALIGN=[L/C/R] LINESPACE=n PRIORITY=s TEXT=s CALC=[ON/OFF]>
      -
    * - <CHGCGCHAR NAME=s TEXT=s CALC=[ON/OFF]>
      -
    * - <LOCKIMG SOURCE=s,s...>
      -
    * - <UNLOCKIMG>
      -
    * - <WALLPAPER SOURCE=s POSITION=[C/T/S]>
      -
    * - <VAR NAME=s>
      -
    * - <MESBOX TIME=n>
      -
    * - <DELMESBOX TIME=n>
      -
    * - <CHGMESBOX NAME=s>
      -
    * - <SOUND SOURCE=s TRACK=[B/V/S/B2/V2/S2] MODE=[N/R/W] VOLUME=n REPEATPOS=n CANREPLAY=n>
      -
    * - <BGM SOURCE=s CANREPLAY=n>
      -
    * - <VOICE SOURCE=s CANREPLAY=n>
      -
    * - <SE SOURCE=s CANREPLAY=n>
      -
    * - <STOPSND TRACK=[B/V/S/B2/V2/S2] TIME=n WAIT=[ON/OFF]>
      -
    * - <CHGVOL TRACK=[B/V/S/B2/V2/S2] VOLUME=n TIME=n WAIT=[ON/OFF]>
      -
    * - <MOVIE SOURCE=s ZOOM=n X=[L/C/R/n] Y=[T/C/B/n] MODE=[N/R/W/F]>
      -
    * - <STOPMOV>
      -
    * - <TEXTSPD TIME=n ABSOLUTE=[ON/OFF]>
      -
    * - <TXSPN>
      -
    * - <TXSPN>
      -
    * - <TXSPS>
      -
    * - <SYSMENUON>
      -
    * - <SYSMENUOFF>
      -
    * - <SAVELOADON>
      -
    * - <SAVELOADOFF>
      -
    * - <INCLUDE SOURCE=s>
      -
    * - <B>～</B>
      -
    * - <B>～</B>
      -
    * - <U>～</U>
      -
    * - <S>～</S>
      -
    * - <NOBR>～</NOBR>
      -
    * - <FONT SIZE=n COLOR=#RRGGBB BCOLOR=#RRGGBB SCOLOR=#RRGGBB BORDER=n SHADOW=n>～</FONT>
      -
    * - <RUBY VALUE=s>～</RUBY>
      -
    * - <A HREF=s>～</A>
      -
    * - <SETSTYLE NAME=s SIZE=n COLOR=#RRGGBB BCOLOR=#RRGGBB SCOLOR=#RRGGBB BORDER=n SHADOW=n B=[ON/OFF] I=[ON/OFF] U=[ON/OFF] S=[ON/OFF] NOBR=[ON/OFF] RUBY=s>
      -
    * - <STYLE NAME=s>～</STYLE>
      -
    * - <MACRO NAME=s>～</MACRO>
      -
    * - <IMGCHAR SOURCE=s ALIGN=[T/C/B]>
      -
    * - <OPENURL URL=s>
      -
    * - <QUAKE NAME=s TYPE=[Q/W/B] RANDOM=[ON/OFF] X=n Y=n TIME=n CYCLE=n>
      -
    * - <QUAKE NAME=s TYPE=[Q/W/B] RANDOM=[ON/OFF] X=n Y=n TIME=n CYCLE=n>
      -
    * - <MOTION NAME=s TARGET=s PROP=s VALUE=n TIME=n TYPE=[N/I/D] WAIT=[ON/OFF]>
      -

Chart and calculation variables
-------------------------------

Jump
----

Conditionals
------------

Text string choice selection
----------------------------

Image choice selection
----------------------

Character string input
----------------------

Project options
---------------

Variable / value
----------------

System variables
----------------

Several special system variables exist.
System variables begin with ``@`` and can be used to get or set system status.

.. list-table:: Standard system variables
    :header-rows: 1

    * - Variable name
      - Type
      - Description
      - Read/Write
    * - ``@Year``
      - Integer
      - Year for current date.
      - Read-only
    * - ``@Month``
      - Integer
      - Month for current date.
      - Read-only
    * - ``@Day``
      - Integer
      - Day for current date.
      - Read-only
    * - ``@Week``
      - Integer
      - Weekday from ``1`` (Sun) to ``7`` (Sat) for current date.
      - Read-only
    * - ``@Hour``
      - Integer
      - Hour for current time.
      - Read-only
    * - ``@Min``
      - Integer
      - Minute for current time.
      - Read-only
    * - ``@Sec``
      - Integer
      - Second for current time.
      - Read-only
    * - ``@1Hour``
      - Real
      -
      - Read-only
    * - ``@1Min``
      - Real
      -
      - Read-only
    * - ``@1Sec``
      - Real
      -
      - Read-only
    * - ``@MouseX``
      - Integer
      - Current mouse cursor X-coordinate.
      - Read/Write
    * - ``@MouseY``
      - Integer
      - Current mouse cursor Y-coordinate.
      - Read/Write
    * - ``@LClick``
      - Flag
      - ``TRUE`` when left mouse button is clicked.
      - Read-only
    * - ``@RClick``
      - Flag
      - ``TRUE`` when right mouse button is clicked.
      - Read-only
    * - ``@LPush``
      - Flag
      - ``TRUE`` if left mouse button is pressed.
      - Read-only
    * - ``@RPush``
      - Flag
      - ``TRUE`` if right mouse button is pressed.
      - Read-only
    * - ``@KeyClick[KEY_CONST]``
      - Flag
      - ``TRUE`` when the specified key is clicked.
      - Read-only
    * - ``@KeyPush[KEY_CONST]``
      - Flag
      - ``TRUE`` if the specified key is pressed.
      - Read-only
    * - ``@KeyRepeat[KEY_CONST]``
      - Flag
      - ``TRUE`` if the specified key is being pressed at regular intervals.
      - Read-only
    * - ``@Pi``
      - Real
      - Value of Pi.
      - Read-only
    * - ``@TickCount``
      - Integer
      - Time since the program was started in milliseconds.
      - Read-only
    * - ``@PCTickCount``
      - Integer
      - Time since Windows was started in milliseconds.
      - Read-only
    * - ``@Title``
      - String
      - Software title.
      - Read-only
    * - ``@FullScr``
      - Flag
      - ``TRUE`` if program is in full-screen mode.
      - Read/Write
    * - ``@ScrHeight``
      - Integer
      - Screen height in pixels
      - Read-only
    * - ``@ScrWidth``
      - Integer
      - Screen width in pixels
      - Read-only
    * - ``@SelIndex``
      - Integer
      - 0-indexed value of the player's last text or image selection choice.
        For image selection, it will contain the same value displayed in ``LivePreviewMenu``.

        * Value will be set to ``-1`` if selection prompt was closed by right-clicking.
      - Read/Write
    * - ``@SelStr``
      - Integer
      - Text string value of the player's last text or image selection choice.
        For image selection, it will contain the name given in ``LivePreviewMenu``.
      - Read/Write

.. list-table:: LiveMaker Pro system variables
    :header-rows: 1

    * - Variable name
      - Type
      - Description
      - Read/Write
    * - ``@ActiveCompo``
      - String
      - Name of the active component for receiving keyboard input.
      - Read/Write
    * - ``@CGDither``
      - Flag
      - If TRUE, perform full color image dithering.
      - Read/Write
    * - ``@Cursor``
      - String
      - Default mouse cursor filename.
        If a component cursor is set, it takes precedence over this one.
      - Read/Write
    * - ``@DisplayModeCount``
      - Integer
      - Number of available full-screen display modes.
      - Read-only
    * - ``@DisplayModeIndex``
      - Integer
      - Index of the current full-screen display mode.
        Setting this value will immediately enable full-screen mode.
      - Read/Write
    * - ``@FixedFonts``
      - String
      - List of fixed-width TrueType fonts available on this system, separated by newlines.
      - Read-only
    * - ``@Fonts``
      - String
      - List of TrueType fonts available on this system, separated by newlines.
      - Read-only
    * - ``@HistoryCount``
      - Integer
      - When history format is registered
            Text history height (in pixels)

        When history format is not registered
            Number of available text histories
      - Read-only
    * - ``@HistoryMaxCount``
      - Integer
      - Maximum number of text history pages that can be stored.

        When history format is registered
            Maximum number of history message box pages

        When history format is not registered
            Number of pages for text insertion
      - Read/Write
    * - ``@IsDebug``
      - Flag
      - ``TRUE`` when running in debug mode.
      - Read-only
    * - ``@ParamStr``
      - String
      - Parameter argument array.
        Available range is ``@ParamStr[0] ~ @ParamStr[@ParamCount - 1]``.
      - Read-only
    * - ``@Result``
      - -
      - Value to be returned to the caller.
      - Read/Write
    * - ``@Sender``
      - String
      - Name of the invoked component.
      - Read-only
    * - ``@SoundON``
      - Flag
      - Setting to ``FALSE`` will disable audio playback.
      - Read/Write
    * - ``@StackCount``
      - Integer
      - Number of call stacks
      - Read-only
    * - ``@Temp``
      - -
      - Can be used as a substitute when assigning variables with ``AssignTemp``.
      - Read/Write
    * - ``@TextDelay``
      - Integer
      - Default weight for inserted text.
      - ``Read/Write``
    * - ``@MidiPort``
      - String
      - Current MIDI port.
      - Read/Write
    * - ``@MidiPorts[Index]``
      - String
      - Available MIDI ports.
        Index can be ``0 ~ (GetArraySize(@MidiPorts) - 1)``
      - Read-only

Operator
--------

Function
--------
