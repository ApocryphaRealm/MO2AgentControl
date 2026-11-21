# MO2 reference - what Mod Organizer 2 does where MO2 Agent Control touches it

Standing rule: before adding to or altering an MO2 feature, read MO2's own implementation at the release tag and follow
its shape. Read 2026-10-24 for MO2 **2.5.2**, for 1.0.0.

## Sources read

| Feature | MO2 source |
|---|---|
| switching profile | https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/mainwindow.cpp (`MainWindow::on_profileBox_currentIndexChanged`, `activateSelectedProfile`, `refreshProfiles`) |
| starting a program through the VFS | https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/organizerproxy.cpp (`OrganizerProxy::startApplication`, `waitForApplication`), https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/processrunner.cpp (`ProcessRunner::setFromFileOrExecutable`) |
| refresh | https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/organizerproxy.cpp (`OrganizerProxy::refresh`), https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/organizercore.cpp (`OrganizerCore::refresh`, `refreshESPList`) |
| ticking mods | https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/modlist.cpp (`ModList::setActive` - both the single-name and the list overloads) |
| ticking plugins, and when plugins.txt is written | https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/pluginlist.cpp (`PluginList::setState`, `saveTo`) - see also MO2 Modlist Manager's MO2-REFERENCE.md for `saveTo` and the game plugin's writer |
| a plugin's settings, and when they are read | https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/settings.cpp (`PluginSettings::registerPlugin`, `setting`), https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/plugincontainer.cpp (`PluginContainer::registerPlugin`, `initPlugin`) |

## What MO2 does

| Feature | MO2 |
|---|---|
| switching profile | the profile box's `currentIndexChanged` handler does it all: it returns at once while the box is disabled; it saves the current lists (`saveCurrentLists`) before leaving a profile; index 0 is the "<Manage...>" entry and opens the profiles dialog (modal); otherwise `activateSelectedProfile` sets the profile, refreshes the saves list and calls `refresh()` |
| starting a program | `startApplication(exe, args, cwd, profile, overwrite, ignoreOverwrite)` runs it through a ProcessRunner WITHOUT waiting and returns the process handle - "the plugin is in charge of closing the handle, unless waitForApplication() is called on it". `exe` is a file path when it contains `\` or `/` (relative paths are taken from the game folder, and the cwd defaults to the binary's folder), otherwise the title of an entry in the executables list. `waitForApplication` locks MO2's window until the program ends |
| refresh | `refresh(saveChanges)`: with saveChanges it writes modlist.txt now (`writeModlistNow`), then re-reads mod info from disk, refreshes the mods' status and rebuilds the virtual file tree; the plugin list is rebuilt later, on the next refresh callback (`refreshESPList` through `onNextRefresh`) |
| ticking mods | `setActive(names, active)` turns the names into mod indices, skipping (with a debug log line) any name that does not exist, and enables or disables them all in one `setModsEnabled` call on the profile; it returns how many it found |
| ticking plugins | `setState` changes the state in memory only (no save is triggered), and a force-loaded or force-enabled plugin (the game's primary plugins) stays enabled whatever is asked, a force-disabled one stays off; plugins.txt is written only when MO2 saves its plugin list - later, not by `setState` - and leaves the primary plugins out |
| plugin settings | `registerPlugin` reads each `settings()` entry from ModOrganizer.ini `[Plugins] <plugin name>/<key>` (on disk `<plugin%20name>\<key>`), converting it to the default's type, and falls back to the default when it is missing or unreadable. It runs when the plugin is REGISTERED, which is before `init()` is called |

## What ours does, and how it follows MO2

| Feature | MO2 Agent Control |
|---|---|
| select_profile | sets the profile box's index, so MO2's own handler does the switch exactly as a pick in the box would (lists saved first, then the refresh); refuses a name the box does not have, so index 0 (the "<Manage...>" dialog) is never chosen; checks the profile actually changed, which catches the "box disabled" early return |
| run | `startApplication` with the title or path given, never `waitForApplication` (it would lock MO2's window); the handle is closed after its pid is read, as MO2 asks |
| refresh | `refresh(save)` as given; the docs say `save` writes modlist.txt only |
| set_mods | every name is checked against the mod list first, so the whole request fails instead of MO2 silently skipping an unknown name; then one `setActive` call |
| set_plugins | refuses the game's primary plugins (`managedGame().primaryPlugins()`), which MO2 never changes or lists; `setState` for each, then plugins.txt is written in MO2's own shape (`*` for active) at once and MO2 re-reads it with `refresh(False)` - because MO2's own write comes late, and a refresh before it read the old file back |
| settings | three `PluginSetting`s read through `pluginSetting`; their descriptions are translated, and since `settings()` is called before `init()`, the language is read from MO2's data folder (the application's `dataPath` property) on first use |

## The window commands (1.1.0) - what they rely on

`ui_tree`, `ui_click`, `ui_answer_modal` and `ui_set` add to no MO2 feature and hook none: they read and call Qt widgets
(`QApplication.topLevelWidgets`, `findChildren`, `QAbstractButton.click`, `QApplication.activeModalWidget`), MO2's own
and any plugin's alike. No MO2 source was read for them, and nothing in them depends on a widget MO2 names. What they
rely on is Qt's behaviour, proven by `tests/test_ui_widgets.py` against the plugin's own socket and widget code:

- a modal dialog's `exec()` runs a nested event loop on the GUI thread, and that loop still delivers the channel's
  socket notifications and timers - so a request is answered while a dialog is open;
- a press that opens a dialog does not return until the dialog closes - so every window write runs from a zero timer
  after its request has been read, and replies when it returns or after `wait_ms` with the open dialog described.

No timer is parented to an MO2 widget, no application-wide event filter is installed and no model signal is connected.

The list and menu commands (1.1.0) follow the same line: `ui_items` reads `view.model()` - the proxy the view shows, so
rows are in the order and filter on screen - with `rowCount`, `index` and `data`; `ui_item` selects through the view's
selection model, ticks with `model.setData(index, state, CheckStateRole)` (the call Qt makes for a click on the box,
so MO2's own models run their own handlers - enabling a mod exactly as a click does), opens with `setExpanded` and
calls `fetchMore` for a row that loads on demand. `ui_menus` walks `QMenuBar` / `QToolBar` actions and their
`menu()`; `ui_menu` calls `QAction.trigger()`. No MO2 source was read for them and no MO2 model is subclassed,
connected or replaced.

## The tool bar button (1.1.0)

MO2 has no plugin call for a tool bar button of a plugin's own, so `toolbar.py` adds a QAction to the main window's first
QToolBar (before Settings), as MO2 Modlist Manager does, and looks every two seconds: MO2 rebuilds its tool bar, and a
theme or .qss change must repaint the icon. The icon is the PNG's shape filled with the colour the stylesheet in force
gives the button (`ensurePolished`, palette ButtonText, else WindowText). The timer belongs to the plugin's own object,
no MO2 widget is subclassed, filtered or re-parented, and no MO2 source was read for it.

## Departures to revisit

- set_plugins writes plugins.txt itself instead of waiting for MO2's own save. If a later MO2 offers a call that saves the
  plugin list at once, use it instead.
- select_profile goes through the profile box widget (found by its object name `profileBox`), because the plugin API has
  no profile switch. A future MO2 that renames the widget breaks it; the command then fails with "MO2's profile box was
  not found" rather than doing anything else.
