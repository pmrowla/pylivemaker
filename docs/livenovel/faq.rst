LiveNovel FAQ
=============

Project
-------

Cannot select folder for "New Project"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Please specify an empty folder.
A directory cannot be used if it contains any files or subdirectories.

Cannot exit game at runtime
~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the system menu is disabled, you will not be able to exit the game via menus.
In this case, use ALT-F4 to exit the game.

Specifying the text string displayed for a save file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The text string displayed for a save file is normally the in-game text content displayed at the time of the save.
If you assign a text string to the variable ``セーブキャプション`` (``SaveCaption``), the string will be displayed (with date and time appended).

Example (Using compute nodes)::

    セーブキャプション = "In front of school - 3:00PM"

This state will be retained until the next time that variable is changed.
If the variable is cleared, the default behavior will be restored. ::

    セーブキャプション = ""

Chart
-----

Chart is too narrow
~~~~~~~~~~~~~~~~~~~

Right click on the chart and select ``チャートのプロパティ`` (``Chart Properties``) from the menu.
When the properties are displayed, change ``チャートサイズ`` (``Chart Size``) and click ``OK``.

Text
----

Changing message box design
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Select ``プロジェクト`` → ``オプション`` (``Project`` → ``Options``) from the menu to open the Options dialog, and set ``メッセージボックス`` → ``ボックス`` → ``デザイン`` (``Message Box`` → ``Box`` → ``Design``).
If ``タイプ`` (``Type``) is set to ``画像`` (``Image``), the specified image file can be used as a message box.

Changing message box click sound
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Select ``プロジェクト`` → ``オプション`` from the menu to open the Options dialog and set ``メッセージボックス`` → ``ボックス`` → ``サウンド`` → ``改ページ`` (``Message Box`` → ``Box`` → ``Sound`` → ``Page Break``)

Removing a line from scenario recollection mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Text which has already been displayed can be re-read from the Scenario Recollection option in the system menu, but there may be text which you want to be hidden in this mode.
In that case, right-click the scenario node and check ``説明文として扱う`` (``Treat as description``) (the node color will change to green).

Graphic
-------

Displaying two images at the same time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Insert two ``画像表示`` (``Display Image``) commands and set ``「画像表示」の「画面効果」`` (``Display Image`` → ``Screen Effect``) for the first image to ``裏画面に配置`` (``Background placement``).
This way, when the second display command is executed, the first image will also be displayed.

Displaying and hiding images at the same time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Insert a ``画像表示`` (``Display Image``) command and ``画像消去`` (``Delete Image``) command in that order, and set ``「画像表示」の「画面効果」`` (``Display Image`` → ``Screen Effect``) to ``裏画面に配置`` (``Background placement``).
This way, when the delete command is executed, the first image will be displayed.

Image is not displayed
~~~~~~~~~~~~~~~~~~~~~~

If ``「画像表示」の「プライオリティ」`` (``Display Image`` → ``Priority``) is low, it may be hidden behind other images.

Sound
-----

Calculation/Variable
--------------------

Installer
---------
