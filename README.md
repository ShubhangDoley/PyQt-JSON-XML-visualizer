# Structured Tree Explorer (CLI + PyQt GUI)

A professional tree visualizer for structured files.

It started as a JSON CLI viewer and is now upgraded to support:
- JSON
- XML (including layout-style XML)
- YAML (`.yml`/`.yaml`)
- TOML
- INI / CFG

You can use it in terminal (`jtree.py`) or through a modern Outlook-style desktop interface (`jtree_gui.py`).

## Features

### CLI (backward-compatible + extended)
- `show` - render the structure as a colored tree
- `search <query>` - deep search across keys and values
- `get <path>` - jump to a specific dot-path
- `info` - total nodes + maximum depth
- `gui [files...]` - launch GUI from CLI

### GUI (PyQt)
- Professional three-pane layout:
  - Left: loaded files
  - Center: tree explorer
  - Right: node details
- Drag and drop files directly into the window
- Multi-file session management
- Search-next navigation
- Path-based jump (`Go To Path`)
- Expand/collapse actions
- Right-click context menu (copy path/value)
- Quick stats dialog

## Requirements

- Python 3.9+
- For GUI: `PyQt6` or `PyQt5`

Optional parsers:
- YAML: `pyyaml`
- TOML (for Python < 3.11): `tomli`

## Installation

```bash
pip install pyqt6 pyyaml
```

If you prefer PyQt5:

```bash
pip install pyqt5 pyyaml
```

## Usage

### CLI examples

```bash
python jtree.py test.json show
python jtree.py test.json search version
python jtree.py test.json get project1.author.name
python jtree.py test.json info
```

### XML examples

```bash
python jtree.py layout.xml show
python jtree.py layout.xml search button
python jtree.py layout.xml get LinearLayout.child[1]
```

### Launch GUI

```bash
python jtree.py gui
python jtree.py gui test.json layout.xml
# or directly
python jtree_gui.py
```

## Path notes

- Arrays use numeric segments: `users.0.name`
- Repeated XML sibling tags use index form in search/path views: `item[0]`, `item[1]`
- Root path can be represented as `.` in most contexts

## Project files

- `tree_core.py` - parsing, tree model, operations, and console renderer
- `jtree.py` - CLI entrypoint (and GUI launcher command)
- `jtree_gui.py` - PyQt desktop app
- `test.json` - sample data
