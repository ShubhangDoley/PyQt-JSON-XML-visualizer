# Modular Design — Tree & Graph
### PyQt JSON / XML Visualizer

---

## 1. Project Files & Roles

| File | Role |
|---|---|
| `tree_core.py` | Core data structures and algorithms — no UI dependency |
| `jtree.py` | CLI entry-point — wires arguments to `tree_core` |
| `jtree_gui.py` | PyQt GUI — visual rendering of tree and graph |

---

## 2. Why Two Structures?

| | Tree (`TreeNode`) | Graph (`GraphModel`) |
|---|---|---|
| **Models** | Hierarchical file data as-is | Directed graph derived from tree + optional cross-reference edges |
| **Edges** | Parent → child only | Parent → child + `ref` / `link` / `depends_on` edges |
| **Purpose** | Parsing, display, search, navigation | BFS, shortest path, cycle detection, visual map layout |
| **Built** | Always — every command needs it | On demand — `graph-*` CLI commands or GUI Map tab |

> **Rule:** Tree is always built first. Graph is derived on top of the tree.

---

## 3. Module — `tree_core.py`

### 3.1 Tree Module

#### `TreeNode` — Core Data Unit

| Field | Type | Meaning |
|---|---|---|
| `key` | `str` | Node label (e.g., `"users"`, `"name"`) |
| `value` | `Optional[str]` | Leaf value as string (`"Alice"`, `"42"`, `"null"`) |
| `type_name` | `str` | One of: `object`, `array`, `element`, `string`, `number`, `boolean`, `null` |
| `children` | `List[TreeNode]` | Ordered list of child nodes |

| Method | Purpose |
|---|---|
| `add_child(node)` | Appends a child node |
| `is_leaf()` | Returns `True` if no children and not a container type |

**Used in:** CLI (every command) and GUI (all panels)

---

#### `DataTreeBuilder` — File → Tree Factory

| Method | Description |
|---|---|
| `parse_file(filepath)` | Detects format, dispatches to correct parser, returns root `TreeNode` |
| `detect_format(filepath)` | Returns format string (`json`, `xml`, `yaml`, `toml`, `ini`) |
| `_build_tree(key, value)` | Recursively converts Python dicts/lists/scalars to `TreeNode` |
| `_parse_json(filepath)` | `json.load` → `_build_tree` |
| `_parse_xml(filepath)` | `xml.etree.ElementTree` → `_build_xml_tree` |
| `_build_xml_tree(element)` | Converts XML elements + attributes recursively |
| `_parse_yaml(filepath)` | `yaml.safe_load` → `_build_tree` |
| `_parse_toml(filepath)` | `tomllib.load` → `_build_tree` |
| `_parse_ini(filepath)` | `configparser` → `_build_tree` |

**Supported formats:** `.json` `.xml` `.yaml` `.yml` `.toml` `.ini` `.cfg`

**Called in:**
- `jtree.py` — every CLI command (line 168)
- `jtree_gui.py` — `load_files()` (line 698), `show_tree_stats()` (line 1430)

---

#### `TreeVisualizer` — Terminal ASCII Tree Renderer

| Method | Description |
|---|---|
| `_format_value(node)` | Returns color-coded string for node value |
| `print_tree(node, prefix, is_last, is_root)` | Recursive DFS — prints `├──` / `└──` tree to stdout |

**Called in:** CLI only — `show` command (line 175) and `get` command (line 199)

---

#### `TreeOperations` — Tree Algorithms

| Method | Algorithm | Complexity | Called In |
|---|---|---|---|
| `search(node, query)` | Recursive DFS — matches key or value substring | O(N) | CLI `search`, GUI search bar |
| `get_node(root, path)` | Dot-path navigation (`users.0.name`) | O(depth) | CLI `get`, GUI Go To Path |
| `get_stats(node)` | Counts total nodes + max depth via DFS | O(N) | CLI `info`, GUI inspector, GUI Info dialog |

---

### 3.2 Graph Module

#### `GraphModel` — Adjacency-List Directed Graph

| Field | Type | Meaning |
|---|---|---|
| `adj` | `dict[str, set[str]]` | Adjacency list — `node_id → set of neighbor IDs` |
| `node_meta` | `dict[str, dict[str, str]]` | Metadata per node: `key`, `type`, `value` |
| `alias_to_node` | `dict[str, str]` | Maps `.`, `root`, short paths → full node IDs |

| Method | Purpose |
|---|---|
| `add_node(node_id, **meta)` | Registers a node with optional metadata |
| `add_edge(src, dst)` | Adds directed edge, auto-creates both nodes |
| `add_alias(alias, node_id)` | Registers a name alias |
| `resolve(name)` | Returns canonical node ID for a name or alias |
| `node_count()` | Total number of nodes |
| `edge_count()` | Total number of directed edges |

> Node IDs are dot-path strings matching the tree paths (e.g., `root.users.0.name`).

**Used in:** CLI only — `graph-*` commands

---

#### `TreeGraphBuilder` — Tree → Graph Bridge

| Method | Description |
|---|---|
| `_children_with_segments(parent_node)` | Returns `(child, segment)` pairs; handles duplicate keys with `[idx]` suffix |
| `_register_aliases(graph, path, root_key)` | Registers `.`, `root`, short-path aliases |
| `build_from_tree(root)` | DFS walk: adds every `TreeNode` as a graph node + parent→child edges + cross-reference edges |

**Two types of edges:**

| Edge Type | When Added |
|---|---|
| Structural | Always — mirrors every parent→child relationship in the tree |
| Cross-reference | When a node's key is `ref`, `link`, `depends_on`, `target`, `parent_ref`, or value starts with `ref:` / `path:` / `node:` |

**Called in:** CLI only — line 212, before any `graph-*` command

---

#### `GraphOperations` — Graph Algorithms

| Method | Algorithm | Complexity | Command |
|---|---|---|---|
| `bfs_order(graph, start)` | BFS — returns visit order | O(V + E) | `graph-bfs` |
| `shortest_path(graph, start, target)` | BFS — reconstructs path via parent dict | O(V + E) | `graph-path` |
| `has_cycle(graph)` | DFS — 3-color marking (0=unvisited, 1=in-stack, 2=done) | O(V + E) | `graph-info`, `graph-cycle` |

**Called in:** CLI only — `graph-bfs`, `graph-path`, `graph-cycle`, `graph-info`

---

## 4. Module — `jtree.py` (CLI Entry Point)

Thin orchestration layer. Defines no data structures — only wires arguments to `tree_core`.

| Command | Tree Used | Graph Used | Classes Called |
|---|---|---|---|
| `show` | ✅ | — | `DataTreeBuilder`, `TreeVisualizer` |
| `search` | ✅ | — | `DataTreeBuilder`, `TreeOperations` |
| `get` | ✅ | — | `DataTreeBuilder`, `TreeOperations`, `TreeVisualizer` |
| `info` | ✅ | — | `DataTreeBuilder`, `TreeOperations` |
| `graph-info` | ✅ | ✅ | `DataTreeBuilder`, `TreeGraphBuilder`, `GraphOperations` |
| `graph-bfs` | ✅ | ✅ | `DataTreeBuilder`, `TreeGraphBuilder`, `GraphOperations` |
| `graph-path` | ✅ | ✅ | `DataTreeBuilder`, `TreeGraphBuilder`, `GraphOperations` |
| `graph-cycle` | ✅ | ✅ | `DataTreeBuilder`, `TreeGraphBuilder`, `GraphOperations` |
| `gui` | — | — | Launches `jtree_gui.run_gui()` |

---

## 5. Module — `jtree_gui.py` (PyQt GUI)

### 5.1 `MapGraphicsView` — Visual Graph Canvas

Custom `QGraphicsView` with zoom/pan and node-click detection.

| Method | Purpose |
|---|---|
| `zoom_by(factor)` | Scales view, clamped to `0.2x – 5.5x` |
| `zoom_in() / zoom_out() / reset_zoom()` | Convenience wrappers |
| `fit_to_scene()` | `fitInView` with padding |
| `wheelEvent()` | Mouse wheel → zoom |
| `mousePressEvent()` | Left-click on a node card → fires `on_node_click(path)` callback |

---

### 5.2 `TreeExplorerWindow` — Main Window

#### Key State Fields

| Field | Type | Tracks |
|---|---|---|
| `roots_by_file` | `Dict[str, TreeNode]` | One parsed tree root per loaded file |
| `path_to_item` | `Dict[str, QTreeWidgetItem]` | Dot-path → outline tree row |
| `node_to_item` | `Dict[int, QTreeWidgetItem]` | `id(TreeNode)` → outline tree row |
| `map_rect_by_path` | `Dict[str, QGraphicsRectItem]` | Dot-path → map card (graph box) |
| `map_alias_to_path` | `Dict[str, str]` | Alias resolution for map (`.` → `root`) |
| `selected_node` | `Optional[TreeNode]` | Currently selected node |

---

#### 5.3 Tree Usage in GUI

| Feature / UI Element | Tree Role | Method |
|---|---|---|
| **Outline tab** (`QTreeWidget`) | Each row = one `TreeNode`; stores path and node reference | `_populate_tree()`, `_populate_children()` |
| **Tree View tab** (HTML `<pre>`) | Renders `├──` / `└──` ASCII tree from `TreeNode` recursively | `_refresh_structure_tree_text()`, `_collect_preview_lines()` |
| **Inspector — Node Details** | Shows `key`, `type`, `value`, children count, subtree stats | `_on_tree_selection_changed()` |
| **Inspector — Color-Coded Preview** | Subtree or full tree as HTML; mode switchable | `_refresh_tree_preview()`, `_render_tree_preview()` |
| **Go To Path toolbar** | `TreeOperations.get_node()` → scroll to node | `go_to_path()` |
| **Info dialog** | `TreeOperations.get_stats()` → total nodes + depth | `show_tree_stats()` |
| **Search bar** | Scans `QTreeWidgetItem` text, highlights matches | `_navigate_search()`, `_build_search_matches()` |

---

#### 5.4 Graph Usage in GUI

> **The GUI does NOT use `GraphModel` or `GraphOperations` from `tree_core.py`.
> It implements its own visual graph layout directly on `TreeNode`.**

| Method | Description |
|---|---|
| `_compute_graph_layout(node, path, depth, ...)` | Recursively assigns `(depth, Y)` position to every node — leaves get sequential Y positions; parent Y = average of children Y (bottom-up centring) |
| `_render_graph_map(root)` | Clears scene; draws card boxes (`QGraphicsRectItem`) + bezier-curve arrows (`QPainterPath.cubicTo`) with arrowheads |
| `_build_map_node_html(node)` | Builds HTML label for each card — shows key, child count, and up to 8 child previews |
| `_highlight_map_path(path)` | Sets gold border (`#ffd166`) on selected node's map card; resolves path aliases |
| `_on_map_item_clicked(path)` | Click on map card → scrolls Outline tree to matching node |
| `_add_arrow_tip(end, control)` | Draws 2-line arrowhead at connector endpoint |

**Bidirectional Sync:**

| Action | Result |
|---|---|
| Select node in Outline tree | Corresponding map card highlighted + centred |
| Click card in Map tab | Outline tree scrolls to matching node |

---

## 6. Summary Table — Who Uses What

| Class / Feature | Tree | Graph | CLI | GUI |
|---|:---:|:---:|:---:|:---:|
| `TreeNode` | ✅ | — | ✅ | ✅ |
| `DataTreeBuilder` | ✅ | — | ✅ | ✅ |
| `TreeVisualizer` | ✅ | — | ✅ | — |
| `TreeOperations` | ✅ | — | ✅ | ✅ |
| `GraphModel` | — | ✅ | ✅ | — |
| `TreeGraphBuilder` | ✅ → 🔵 | ✅ | ✅ | — |
| `GraphOperations` | — | ✅ | ✅ | — |
| `MapGraphicsView` | — | ✅ | — | ✅ |
| `_compute_graph_layout` | ✅ input | ✅ output | — | ✅ |
| `_render_graph_map` | — | ✅ | — | ✅ |

---

## 7. Key Design Principles

| # | Principle |
|---|---|
| 1 | `tree_core.py` has **zero PyQt imports** — fully decoupled from UI |
| 2 | **Tree is always built first** — no graph exists without a tree |
| 3 | **Two graph implementations** — CLI uses `GraphModel` (algorithmic); GUI uses direct `TreeNode` layout (visual) |
| 4 | **Cross-reference edges** exist only in `TreeGraphBuilder` — graph can represent more than raw file hierarchy |
| 5 | **Bidirectional sync** in GUI — Outline tree ↔ Map tab, keyed on dot-path strings |
