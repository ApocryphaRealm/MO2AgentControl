# MO2 Agent Control - copyright and licence

Copyright (C) 2026 ApocryphaRealm

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public
License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program (`LICENSE`). If not, see
<https://www.gnu.org/licenses/>.

SPDX-License-Identifier: GPL-3.0-or-later

## Why GPL-3.0-or-later

Every mod of this project is GPL-3.0-or-later by default. The plugin and the client are our own Python code; the
plugin runs inside Mod Organizer 2's Python plugin host (`mobase`, PyQt6) and links nothing else, and the client uses
only Python's standard library.

## What it builds on

Mod Organizer 2 (https://github.com/ModOrganizer2/modorganizer, GPL-3.0) provides the plugin API (`IOrganizer`,
`IModList`, `IPluginList`, `startApplication`, the persistent settings store) and Qt's `QTcpServer` through PyQt6.

Source code: https://github.com/ApocryphaRealm/MO2AgentControl
