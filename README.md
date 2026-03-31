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

## Algorithms Used

This project is built around a recursive tree model (`TreeNode`) and uses a small set of clean algorithms.

### 1) Command Routing (CLI)

File: `jtree.py`

- The CLI first parses arguments and routes to one of these commands: `show`, `search`, `get`, `info`, or `gui`.
- This is a simple command-dispatch algorithm: validate input, select branch, run the matching function.

Why it matters:
- Keeps behavior predictable and easy to extend.
- Makes each command independent.

### 2) Format Detection + Fallback Parsing

File: `tree_core.py` (`DataTreeBuilder.parse_file`)

- The parser checks file extension first (`.json`, `.xml`, `.yaml`, `.toml`, `.ini`, etc.).
- If extension is unknown, it tries all known parsers in sequence until one succeeds.
- If all fail, it raises a clear parse error.

Algorithm style:
- Ordered trial/fallback strategy.

Why it matters:
- Good user experience for files with wrong/missing extensions.

### 3) Recursive Tree Construction (Core)

File: `tree_core.py` (`DataTreeBuilder._build_tree`, `_build_xml_tree`)

- JSON/YAML/TOML/INI objects are converted into a generic tree recursively:
  - dictionary -> `object` node with child nodes per key
  - list -> `array` node with child nodes per index
  - primitive values -> leaf nodes (`string`, `number`, `boolean`, `null`)
- XML is also converted recursively:
  - element tag becomes node
  - attributes become a special `@attributes` object child
  - text content is stored as node value (if non-empty)

Algorithm style:
- Depth-first recursive construction.

Why it matters:
- One unified model supports every feature (CLI + GUI) for all formats.

### 4) Tree Rendering Traversal

Files: `tree_core.py` (`TreeVisualizer.print_tree`), `jtree_gui.py` (preview/tree text collectors)

- The app prints tree structure using recursive traversal with prefix/connector logic.
- Connectors (`|--`, `\\--`, `├──`, `└──`) are chosen based on whether a node is last among siblings.

Algorithm style:
- Pre-order depth-first traversal with state carried as prefix.

Why it matters:
- Produces readable, stable tree output in terminal and GUI preview.

### 5) Deep Search Across Keys and Values

File: `tree_core.py` (`TreeOperations.search`), `jtree_gui.py` (UI-side match navigation)

- Search scans each node key and value recursively.
- It builds full paths as it goes.
- For repeated sibling names (common in XML), it adds indexed segments like `item[0]`, `item[1]`.

Algorithm style:
- Depth-first search (DFS) with path accumulation.

Why it matters:
- Finds matches anywhere in large nested structures.

### 6) Dot-Path Resolution (`get` / Go To Path)

File: `tree_core.py` (`TreeOperations.get_node`)

- Path is split by `.` into segments.
- Each segment is resolved step-by-step:
  - direct key match (e.g., `project`)
  - array index segment (e.g., `0`)
  - repeated-key indexed syntax (e.g., `child[2]`)
- Stops early and returns `None` if any segment is invalid.

Algorithm style:
- Iterative path-walk with optional regex parsing for indexed segments.

Why it matters:
- Gives precise random access to any subtree.

### 7) Node Count and Maximum Depth

File: `tree_core.py` (`TreeOperations.get_stats`)

- Recursively computes:
  - `count`: total number of nodes in subtree
  - `depth`: longest path from current node to deepest descendant
- Combines child results using max depth aggregation.

Algorithm style:
- Post-order DFS dynamic aggregation.

Why it matters:
- Fast structural summary for CLI `info` and GUI stats dialog.

### 8) GUI Search Navigation (Next/Prev)

File: `jtree_gui.py`

- GUI builds a list of matched row indices for current query.
- Next/Prev moves a cursor through that list using modular wrap-around.

Algorithm style:
- Linear scan for match building + circular index navigation.

Why it matters:
- Smooth browsing through multiple hits.

### 9) Graph Map Layout Algorithm (GUI "Map" tab)

File: `jtree_gui.py` (`_compute_graph_layout`, `_render_graph_map`)

- Layout is generated recursively by depth (x-axis) and balanced vertical position (y-axis):
  - leaf nodes get next available y-slot
  - parent y is centered as average of children y-values
- Then cubic Bezier connectors are drawn between parent/child cards.

Algorithm style:
- Recursive hierarchical layout (topology-driven), then edge rendering pass.

Why it matters:
- Produces a readable map for complex trees without manual placement.

### 10) Path Alias Mapping (GUI Convenience)

File: `jtree_gui.py`

- The GUI stores aliases for equivalent paths (e.g., `.`, `root`, and normalized variants).
- This allows map-click, search, and path-jump actions to resolve to the same tree item reliably.

Algorithm style:
- Hash-map indexing for O(1)-style lookup.

Why it matters:
- Reduces user friction from path format differences.

## Time Complexity (High-Level)

- Tree build: O(n), where n = number of nodes/items in input data.
- Show/render traversal: O(n).
- Search traversal: O(n).
- Stats (count/depth): O(n).
- Path lookup (`get`): O(k * s) in worst case, where k = path segments and s = siblings scanned per step.
- GUI map layout: O(n) for position computation + O(e) for edges (for trees, e ~ n-1).

In practice, most operations are linear in tree size, which is efficient for typical configuration/data files.

## Project files

- `tree_core.py` - parsing, tree model, operations, and console renderer
- `jtree.py` - CLI entrypoint (and GUI launcher command)
- `jtree_gui.py` - PyQt desktop app
- `test.json` - sample data
