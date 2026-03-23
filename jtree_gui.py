#!/usr/bin/env python3
"""PyQt GUI for visualizing structured tree-like files."""

from __future__ import annotations

from html import escape as html_escape
import math
import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

from tree_core import DataTreeBuilder, ParseError, TreeNode, TreeOperations

QT6 = False
try:
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QAction, QBrush, QColor, QPainter, QPainterPath, QPen
    from PyQt6.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QGraphicsScene,
        QGraphicsTextItem,
        QGraphicsView,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QSplitter,
        QStatusBar,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    QT6 = True
except ImportError:
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QAction, QBrush, QColor, QPainter, QPainterPath, QPen
    from PyQt5.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QGraphicsScene,
        QGraphicsTextItem,
        QGraphicsView,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QSplitter,
        QStatusBar,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )


if QT6:
    ORIENTATION_HORIZONTAL = Qt.Orientation.Horizontal
    ORIENTATION_VERTICAL = Qt.Orientation.Vertical
    USER_ROLE = Qt.ItemDataRole.UserRole
    CONTEXT_MENU_CUSTOM = Qt.ContextMenuPolicy.CustomContextMenu
    GRAPH_DRAG_MODE = QGraphicsView.DragMode.ScrollHandDrag
    GRAPH_VIEWPORT_UPDATE = QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate
    GRAPH_ANCHOR_MOUSE = QGraphicsView.ViewportAnchor.AnchorUnderMouse
    GRAPH_ANCHOR_CENTER = QGraphicsView.ViewportAnchor.AnchorViewCenter
    ANTIALIAS_HINT = QPainter.RenderHint.Antialiasing
    ASPECT_KEEP = Qt.AspectRatioMode.KeepAspectRatio
    LEFT_MOUSE_BUTTON = Qt.MouseButton.LeftButton
    NO_MOUSE_BUTTON = Qt.MouseButton.NoButton
else:
    ORIENTATION_HORIZONTAL = Qt.Horizontal
    ORIENTATION_VERTICAL = Qt.Vertical
    USER_ROLE = Qt.UserRole
    CONTEXT_MENU_CUSTOM = Qt.CustomContextMenu
    GRAPH_DRAG_MODE = QGraphicsView.ScrollHandDrag
    GRAPH_VIEWPORT_UPDATE = QGraphicsView.BoundingRectViewportUpdate
    GRAPH_ANCHOR_MOUSE = QGraphicsView.AnchorUnderMouse
    GRAPH_ANCHOR_CENTER = QGraphicsView.AnchorViewCenter
    ANTIALIAS_HINT = QPainter.Antialiasing
    ASPECT_KEEP = Qt.KeepAspectRatio
    LEFT_MOUSE_BUTTON = Qt.LeftButton
    NO_MOUSE_BUTTON = Qt.NoButton

PATH_ROLE = USER_ROLE
NODE_ROLE = USER_ROLE + 1
FILE_ROLE = USER_ROLE + 2


class MapGraphicsView(QGraphicsView):
    MIN_SCALE = 0.2
    MAX_SCALE = 5.5

    def __init__(
        self,
        scene: QGraphicsScene,
        on_node_click: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(scene, parent)
        self.on_node_click = on_node_click

    def _current_scale(self) -> float:
        return float(self.transform().m11())

    def zoom_by(self, factor: float) -> None:
        if factor <= 0:
            return
        next_scale = self._current_scale() * factor
        if next_scale < self.MIN_SCALE or next_scale > self.MAX_SCALE:
            return
        self.scale(factor, factor)

    def zoom_in(self) -> None:
        self.zoom_by(1.15)

    def zoom_out(self) -> None:
        self.zoom_by(1.0 / 1.15)

    def reset_zoom(self) -> None:
        self.resetTransform()

    def fit_to_scene(self, padding: float = 24.0) -> None:
        rect = self.sceneRect()
        if rect.isNull():
            return
        self.fitInView(rect.adjusted(-padding, -padding, padding, padding), ASPECT_KEEP)

    def wheelEvent(self, event) -> None:
        angle_delta = event.angleDelta().y()
        if angle_delta:
            self.zoom_by(1.12 if angle_delta > 0 else (1.0 / 1.12))
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:
        if self.on_node_click is not None and event.button() == LEFT_MOUSE_BUTTON:
            view_pos = event.position().toPoint() if QT6 else event.pos()
            scene_pos = self.mapToScene(view_pos)
            item = self.scene().itemAt(scene_pos, self.transform())
            while item is not None and item.data(0) is None:
                item = item.parentItem()
            if item is not None:
                self.on_node_click(str(item.data(0)))
        super().mousePressEvent(event)


class TreeExplorerWindow(QMainWindow):
    def __init__(self, initial_files: Optional[List[str]] = None):
        super().__init__()
        self.roots_by_file: Dict[str, TreeNode] = {}
        self.current_file: Optional[str] = None
        self.path_to_item: Dict[str, QTreeWidgetItem] = {}
        self.node_to_item: Dict[int, QTreeWidgetItem] = {}
        self.last_query = ""
        self.last_match_index = -1
        self.selected_node: Optional[TreeNode] = None
        self.selected_path: str = "."
        self.map_rect_by_path: Dict[str, object] = {}
        self.map_alias_to_path: Dict[str, str] = {}
        self._map_root_key: str = "root"

        self.setWindowTitle("Structured Tree Explorer")
        self.resize(1480, 900)
        self.setAcceptDrops(True)

        self._build_ui()
        self._build_toolbar()
        self._apply_theme()

        if initial_files:
            self.load_files(initial_files)

    def _build_ui(self) -> None:
        self.file_list = QListWidget()
        self.file_list.currentItemChanged.connect(self._on_file_selection_changed)

        self.tree_view = QTreeWidget()
        self.tree_view.setHeaderLabels(["Node", "Value", "Type"])
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setUniformRowHeights(True)
        self.tree_view.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.tree_view.setContextMenuPolicy(CONTEXT_MENU_CUSTOM)
        self.tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)

        self.map_scene = QGraphicsScene(self)
        self.map_view = MapGraphicsView(self.map_scene, self._on_map_item_clicked, self)
        self.map_view.setRenderHint(ANTIALIAS_HINT)
        self.map_view.setDragMode(GRAPH_DRAG_MODE)
        self.map_view.setViewportUpdateMode(GRAPH_VIEWPORT_UPDATE)
        self.map_view.setTransformationAnchor(GRAPH_ANCHOR_MOUSE)
        self.map_view.setResizeAnchor(GRAPH_ANCHOR_CENTER)

        self.structure_tabs = QTabWidget()
        self.structure_tabs.addTab(self.tree_view, "Outline")
        self.structure_tabs.addTab(self.map_view, "Map")

        left_panel = self._wrap_panel("Files", self.file_list)
        center_panel = self._wrap_panel("Structure", self.structure_tabs)
        right_panel = self._wrap_panel("Inspector", self._build_inspector_widget())

        splitter = QSplitter(ORIENTATION_HORIZONTAL)
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 830, 350])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(splitter)

        self.setCentralWidget(container)

        status = QStatusBar()
        status.showMessage("Drop JSON/XML/YAML/TOML/INI files to start")
        self.setStatusBar(status)

    def _build_inspector_widget(self) -> QWidget:
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Select a node to inspect details.")

        self.tree_preview = QTextEdit()
        self.tree_preview.setReadOnly(True)
        self.tree_preview.setPlaceholderText("Colored tree preview appears here.")

        details_box = QWidget()
        details_layout = QVBoxLayout(details_box)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(4)
        details_title = QLabel("Node Details")
        details_title.setStyleSheet("font: 700 10pt 'Segoe UI'; color: #ffffff;")
        details_layout.addWidget(details_title)
        details_layout.addWidget(self.details)

        preview_box = QWidget()
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(4)
        preview_title = QLabel("Color-Coded Tree Preview")
        preview_title.setStyleSheet("font: 700 10pt 'Segoe UI'; color: #ffffff;")
        preview_mode_row = QHBoxLayout()
        preview_mode_row.setContentsMargins(0, 0, 0, 0)
        preview_mode_row.setSpacing(8)
        preview_mode_label = QLabel("Mode")
        preview_mode_label.setStyleSheet("font: 600 9.5pt 'Segoe UI'; color: #ffffff;")
        self.preview_mode_combo = QComboBox()
        self.preview_mode_combo.addItem("Selected Subtree")
        self.preview_mode_combo.addItem("Full File Tree")
        self.preview_mode_combo.currentIndexChanged.connect(self._on_preview_mode_changed)
        preview_mode_row.addWidget(preview_mode_label)
        preview_mode_row.addWidget(self.preview_mode_combo, 1)
        preview_layout.addWidget(preview_title)
        preview_layout.addLayout(preview_mode_row)
        preview_layout.addWidget(self.tree_preview)

        inspector_splitter = QSplitter(ORIENTATION_VERTICAL)
        inspector_splitter.addWidget(details_box)
        inspector_splitter.addWidget(preview_box)
        inspector_splitter.setSizes([260, 420])

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(inspector_splitter)
        return wrapper

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_files_dialog)
        toolbar.addAction(open_action)

        clear_action = QAction("Clear", self)
        clear_action.triggered.connect(self.clear_session)
        toolbar.addAction(clear_action)

        expand_action = QAction("Expand All", self)
        expand_action.triggered.connect(self.tree_view.expandAll)
        toolbar.addAction(expand_action)

        collapse_action = QAction("Collapse All", self)
        collapse_action.triggered.connect(self.tree_view.collapseAll)
        toolbar.addAction(collapse_action)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Map"))

        map_zoom_in = QAction("Zoom +", self)
        map_zoom_in.setShortcut("Ctrl+=")
        map_zoom_in.triggered.connect(self.zoom_map_in)
        toolbar.addAction(map_zoom_in)

        map_zoom_out = QAction("Zoom -", self)
        map_zoom_out.setShortcut("Ctrl+-")
        map_zoom_out.triggered.connect(self.zoom_map_out)
        toolbar.addAction(map_zoom_out)

        map_reset = QAction("100%", self)
        map_reset.triggered.connect(self.reset_map_zoom)
        toolbar.addAction(map_reset)

        map_fit = QAction("Fit", self)
        map_fit.triggered.connect(self.fit_map_view)
        toolbar.addAction(map_fit)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Find"))

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search keys or values...")
        self.search_box.setMaximumWidth(220)
        self.search_box.returnPressed.connect(self.search_next)
        toolbar.addWidget(self.search_box)

        find_btn = QPushButton("Next")
        find_btn.clicked.connect(self.search_next)
        toolbar.addWidget(find_btn)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Go To Path"))

        self.path_box = QLineEdit()
        self.path_box.setPlaceholderText("Example: users.0.name or LinearLayout.child[1]")
        self.path_box.setMaximumWidth(280)
        self.path_box.returnPressed.connect(self.go_to_path)
        toolbar.addWidget(self.path_box)

        path_btn = QPushButton("Go")
        path_btn.clicked.connect(self.go_to_path)
        toolbar.addWidget(path_btn)

        stats_action = QAction("Info", self)
        stats_action.triggered.connect(self.show_tree_stats)
        toolbar.addAction(stats_action)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #1a1a1a;
            }
            QToolBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #202020, stop:1 #2b2b2b);
                border: none;
                spacing: 8px;
                padding: 6px;
            }
            QToolBar QLabel {
                color: #ffffff;
                font: 600 10pt "Segoe UI";
                margin-left: 8px;
            }
            QToolBar QLineEdit {
                background: #2a2a2a;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 5px;
                padding: 5px 8px;
                font: 10pt "Segoe UI";
                selection-background-color: #5e5e5e;
            }
            QToolBar QPushButton {
                background: #303030;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 4px 10px;
                font: 10pt "Segoe UI";
            }
            QToolBar QPushButton:hover {
                background: #3d3d3d;
            }
            QComboBox {
                background: #2a2a2a;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 5px;
                padding: 4px 8px;
                min-height: 24px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background: #2a2a2a;
                color: #ffffff;
                selection-background-color: #5a5a5a;
                border: 1px solid #4a4a4a;
            }
            QToolBar QToolButton {
                color: #ffffff;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 5px 10px;
                font: 10pt "Segoe UI";
            }
            QToolBar QToolButton:hover {
                border-color: #666666;
                background: rgba(255, 255, 255, 0.10);
            }
            QTreeWidget, QListWidget, QTextEdit {
                background: #242424;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                font: 10pt "Segoe UI";
                selection-background-color: #505050;
                selection-color: #ffffff;
            }
            QGraphicsView {
                background: #1f1f1f;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
            }
            QTabWidget::pane {
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                background: #242424;
                top: -1px;
            }
            QTabBar::tab {
                background: #2b2b2b;
                color: #d6d6d6;
                border: 1px solid #4a4a4a;
                border-bottom: none;
                min-width: 84px;
                padding: 6px 12px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #353535;
                color: #ffffff;
            }
            QTabBar::tab:hover {
                background: #3a3a3a;
            }
            QTreeWidget::item {
                height: 24px;
            }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background: #5a5a5a;
                color: #ffffff;
            }
            QHeaderView::section {
                background: #303030;
                color: #ffffff;
                border: none;
                border-right: 1px solid #4a4a4a;
                border-bottom: 1px solid #4a4a4a;
                padding: 5px;
                font: 600 9.5pt "Segoe UI";
            }
            QStatusBar {
                background: #222222;
                border-top: 1px solid #4a4a4a;
                color: #ffffff;
                font: 9.5pt "Segoe UI";
            }
            """
        )

    def _wrap_panel(self, title: str, widget: QWidget) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        label = QLabel(title)
        label.setStyleSheet(
            "font: 700 11pt 'Segoe UI'; color: #ffffff; padding-left: 2px;"
        )

        layout.addWidget(label)
        layout.addWidget(widget)
        return panel

    def open_files_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Open structured files",
            "",
            "Structured files (*.json *.xml *.yaml *.yml *.toml *.ini *.cfg);;All files (*)",
        )
        if files:
            self.load_files(files)

    def clear_session(self) -> None:
        self.roots_by_file.clear()
        self.current_file = None
        self.path_to_item.clear()
        self.node_to_item.clear()
        self.file_list.clear()
        self.tree_view.clear()
        self.map_scene.clear()
        self.map_rect_by_path.clear()
        self.map_alias_to_path.clear()
        self.details.clear()
        self.tree_preview.clear()
        self.selected_node = None
        self.selected_path = "."
        self.statusBar().showMessage("Session cleared")

    def load_files(self, paths: List[str]) -> None:
        loaded = 0
        failed = []

        for raw_path in paths:
            path = os.path.abspath(raw_path)
            if not os.path.isfile(path):
                failed.append(f"{path}: not a file")
                continue

            try:
                root = DataTreeBuilder.parse_file(path)
            except ParseError as exc:
                failed.append(f"{path}: {exc}")
                continue

            self.roots_by_file[path] = root
            loaded += 1

            if not self._file_in_list(path):
                item = QListWidgetItem(Path(path).name)
                item.setToolTip(path)
                item.setData(FILE_ROLE, path)
                self.file_list.addItem(item)

        if loaded and self.file_list.currentItem() is None:
            self.file_list.setCurrentRow(0)
        elif loaded:
            self.statusBar().showMessage(f"Loaded {loaded} file(s)")

        if failed:
            summary = "\n".join(failed[:8])
            if len(failed) > 8:
                summary += f"\n... and {len(failed) - 8} more"
            QMessageBox.warning(self, "Some files could not be loaded", summary)

    def _file_in_list(self, path: str) -> bool:
        for idx in range(self.file_list.count()):
            item = self.file_list.item(idx)
            if item.data(FILE_ROLE) == path:
                return True
        return False

    def _on_file_selection_changed(self, current: Optional[QListWidgetItem], _prev: Optional[QListWidgetItem]) -> None:
        if current is None:
            return

        filepath = current.data(FILE_ROLE)
        if not filepath or filepath not in self.roots_by_file:
            return

        self.current_file = filepath
        root = self.roots_by_file[filepath]
        self._populate_tree(root)

        fmt = DataTreeBuilder.detect_format(filepath)
        self.statusBar().showMessage(f"Loaded: {Path(filepath).name} ({fmt})")
        self.setWindowTitle(f"Structured Tree Explorer - {Path(filepath).name}")

    def _value_text(self, node: TreeNode) -> str:
        if node.type_name == "object":
            return "{}"
        if node.type_name == "array":
            return "[]"
        if node.type_name == "element":
            return node.value if node.value is not None else "(element)"
        return "" if node.value is None else str(node.value)

    def _register_path_aliases(self, path: str, item: QTreeWidgetItem, root_key: str) -> None:
        self.path_to_item[path] = item
        if path == root_key:
            self.path_to_item["."] = item
            self.path_to_item["root"] = item
        if path.startswith("root."):
            self.path_to_item[path[5:]] = item
        if path.startswith(f"{root_key}."):
            self.path_to_item[path[len(root_key) + 1 :]] = item

    def _register_map_aliases(self, path: str, root_key: str) -> None:
        self.map_alias_to_path[path] = path
        if path == root_key:
            self.map_alias_to_path["."] = path
            self.map_alias_to_path["root"] = path
        if path.startswith("root."):
            self.map_alias_to_path[path[5:]] = path
        if path.startswith(f"{root_key}."):
            self.map_alias_to_path[path[len(root_key) + 1 :]] = path

    def _children_with_segments(self, parent_node: TreeNode) -> List[tuple[TreeNode, str]]:
        result: List[tuple[TreeNode, str]] = []
        key_count: Dict[str, int] = {}
        for child in parent_node.children:
            key_count[child.key] = key_count.get(child.key, 0) + 1

        seen: Dict[str, int] = {}
        for child in parent_node.children:
            seen_index = seen.get(child.key, 0)
            seen[child.key] = seen_index + 1
            segment = child.key
            if key_count[child.key] > 1 and not child.key.isdigit():
                segment = f"{child.key}[{seen_index}]"
            result.append((child, segment))
        return result

    def _apply_item_color(self, item: QTreeWidgetItem, node: TreeNode) -> None:
        key_color = QBrush(QColor("#9ec4ff"))
        type_color = {
            "object": QBrush(QColor("#f4d35e")),
            "array": QBrush(QColor("#f4d35e")),
            "element": QBrush(QColor("#ffd166")),
            "string": QBrush(QColor("#97d9a8")),
            "number": QBrush(QColor("#89d7ff")),
            "boolean": QBrush(QColor("#d9b4ff")),
            "null": QBrush(QColor("#ff9a9a")),
        }.get(node.type_name, QBrush(QColor("#e6e6e6")))

        item.setForeground(0, key_color)
        item.setForeground(1, type_color)
        item.setForeground(2, type_color)

    def _populate_tree(self, root: TreeNode) -> None:
        self.tree_view.clear()
        self.path_to_item.clear()
        self.node_to_item.clear()
        self._map_root_key = root.key

        root_path = root.key
        root_item = QTreeWidgetItem([root.key, self._value_text(root), root.type_name])
        root_item.setData(0, PATH_ROLE, root_path)
        root_item.setData(0, NODE_ROLE, root)
        root_item.setToolTip(0, root_path)
        self._apply_item_color(root_item, root)

        self.tree_view.addTopLevelItem(root_item)
        self.node_to_item[id(root)] = root_item
        self._register_path_aliases(root_path, root_item, root.key)

        self._populate_children(root_item, root, root_path, root.key)
        self._render_graph_map(root)

        self.tree_view.expandToDepth(1)
        self.tree_view.resizeColumnToContents(0)
        self.tree_view.setCurrentItem(root_item)

    def _populate_children(
        self,
        parent_item: QTreeWidgetItem,
        parent_node: TreeNode,
        parent_path: str,
        root_key: str,
    ) -> None:
        for child, segment in self._children_with_segments(parent_node):
            child_path = f"{parent_path}.{segment}"
            child_item = QTreeWidgetItem([child.key, self._value_text(child), child.type_name])
            child_item.setData(0, PATH_ROLE, child_path)
            child_item.setData(0, NODE_ROLE, child)
            child_item.setToolTip(0, child_path)
            self._apply_item_color(child_item, child)
            parent_item.addChild(child_item)

            self.node_to_item[id(child)] = child_item
            self._register_path_aliases(child_path, child_item, root_key)
            self._populate_children(child_item, child, child_path, root_key)

    def _on_tree_selection_changed(self) -> None:
        item = self.tree_view.currentItem()
        if item is None:
            return

        node = item.data(0, NODE_ROLE)
        path = str(item.data(0, PATH_ROLE) or ".")
        if node is None:
            return

        child_count = len(node.children)
        subtree_nodes, subtree_depth = TreeOperations.get_stats(node)

        file_name = Path(self.current_file).name if self.current_file else "-"
        value_text = "(none)" if node.value is None else str(node.value)

        details = (
            f"File: {file_name}\n"
            f"Path: {path}\n"
            f"Key: {node.key}\n"
            f"Type: {node.type_name}\n"
            f"Value: {value_text}\n"
            f"Children: {child_count}\n"
            f"Subtree Nodes: {subtree_nodes}\n"
            f"Subtree Depth: {subtree_depth}\n"
        )
        self.details.setPlainText(details)
        self.selected_node = node
        self.selected_path = path
        self._refresh_tree_preview()
        self._highlight_map_path(path)
        self.statusBar().showMessage(f"Selected {path}")

    def _on_preview_mode_changed(self, _index: int) -> None:
        self._refresh_tree_preview()

    def _refresh_tree_preview(self) -> None:
        if not self.current_file:
            self.tree_preview.clear()
            return

        mode = self.preview_mode_combo.currentText().strip().lower()
        if mode.startswith("full"):
            root = self.roots_by_file.get(self.current_file)
            if root is None:
                self.tree_preview.clear()
                return
            self._render_tree_preview(root, ".", title_prefix="Full Tree")
            return

        if self.selected_node is not None:
            self._render_tree_preview(
                self.selected_node,
                self.selected_path if self.selected_path else ".",
                title_prefix="Subtree",
            )
            return

        root = self.roots_by_file.get(self.current_file)
        if root is not None:
            self._render_tree_preview(root, ".", title_prefix="Subtree")
        else:
            self.tree_preview.clear()

    def _tree_value_html(self, node: TreeNode) -> str:
        if node.type_name == "object":
            return (
                "<span style='color:#f4d35e'>{}</span> "
                "<span style='color:#9f9f9f'>(object)</span>"
            )
        if node.type_name == "array":
            return (
                "<span style='color:#f4d35e'>[]</span> "
                "<span style='color:#9f9f9f'>(array)</span>"
            )
        if node.type_name == "element":
            if node.value is None:
                return "<span style='color:#9f9f9f'>(element)</span>"
            text = html_escape(str(node.value))
            return (
                "<span style='color:#9f9f9f'>(element)</span>: "
                f"<span style='color:#97d9a8'>\"{text}\"</span>"
            )

        if node.value is None:
            return f"<span style='color:#d0d0d0'>&lt;{html_escape(node.type_name)}&gt;</span>"

        value = html_escape(str(node.value))
        if node.type_name == "string":
            return f": <span style='color:#97d9a8'>\"{value}\"</span>"
        if node.type_name == "number":
            return f": <span style='color:#89d7ff'>{value}</span>"
        if node.type_name == "boolean":
            return f": <span style='color:#d9b4ff'>{value}</span>"
        if node.type_name == "null":
            return f": <span style='color:#ff9a9a'>{value}</span>"
        return f": <span style='color:#e6e6e6'>{value}</span>"

    def _collect_preview_lines(
        self,
        node: TreeNode,
        lines: List[str],
        prefix: str = "",
        is_last: bool = True,
        is_root: bool = True,
    ) -> None:
        connector = "" if is_root else ("└── " if is_last else "├── ")
        line_prefix = f"<span style='color:#888888'>{html_escape(prefix + connector)}</span>"
        key_html = f"<span style='color:#9ec4ff'>{html_escape(node.key)}</span>"
        value_html = self._tree_value_html(node)
        lines.append(f"{line_prefix}{key_html}{value_html}")

        child_prefix = prefix + ("    " if is_last else "│   ")
        if is_root:
            child_prefix = ""

        for idx, child in enumerate(node.children):
            self._collect_preview_lines(
                child,
                lines,
                prefix=child_prefix,
                is_last=(idx == len(node.children) - 1),
                is_root=False,
            )

    def _render_tree_preview(self, node: TreeNode, path: str, title_prefix: str = "Subtree") -> None:
        lines: List[str] = []
        self._collect_preview_lines(node, lines)
        title = html_escape(path if path else ".")
        html = (
            f"<div style='color:#cfcfcf; margin-bottom:6px;'>{html_escape(title_prefix)}: <b>{title}</b></div>"
            "<pre style='margin:0; font-family: Consolas, \"Cascadia Mono\", monospace; "
            "font-size:10pt; line-height:1.35; color:#ffffff;'>"
            + "\n".join(lines)
            + "</pre>"
        )
        self.tree_preview.setHtml(html)

    def _on_map_item_clicked(self, path: str) -> None:
        target_item = self.path_to_item.get(path)
        if target_item is None:
            if path.startswith("root."):
                target_item = self.path_to_item.get(path[5:])
            elif path not in (".", "root", self._map_root_key):
                target_item = self.path_to_item.get(f"{self._map_root_key}.{path}")

        if target_item is None and path in (".", "root", self._map_root_key):
            target_item = self.path_to_item.get(self._map_root_key) or self.path_to_item.get(".")

        if target_item is None:
            return

        self.tree_view.setCurrentItem(target_item)
        self.tree_view.scrollToItem(target_item)

    def zoom_map_in(self) -> None:
        self.structure_tabs.setCurrentWidget(self.map_view)
        self.map_view.zoom_in()
        self.statusBar().showMessage("Map zoomed in")

    def zoom_map_out(self) -> None:
        self.structure_tabs.setCurrentWidget(self.map_view)
        self.map_view.zoom_out()
        self.statusBar().showMessage("Map zoomed out")

    def reset_map_zoom(self) -> None:
        self.structure_tabs.setCurrentWidget(self.map_view)
        self.map_view.reset_zoom()
        self.statusBar().showMessage("Map zoom reset")

    def fit_map_view(self) -> None:
        self.structure_tabs.setCurrentWidget(self.map_view)
        self.map_view.fit_to_scene()
        self.statusBar().showMessage("Map fit to view")

    def _map_header_color(self, node: TreeNode) -> str:
        return {
            "object": "#f4d35e",
            "array": "#f4d35e",
            "element": "#ffd166",
            "string": "#66d6ff",
            "number": "#88d8ff",
            "boolean": "#d9b4ff",
            "null": "#ff9a9a",
        }.get(node.type_name, "#9ec4ff")

    def _map_value_color(self, node: TreeNode) -> str:
        return {
            "string": "#97d9a8",
            "number": "#89d7ff",
            "boolean": "#d9b4ff",
            "null": "#ff9a9a",
            "object": "#f4d35e",
            "array": "#f4d35e",
            "element": "#97d9a8",
        }.get(node.type_name, "#d9e5ff")

    def _map_brief_value(self, node: TreeNode) -> str:
        if node.type_name == "object":
            return "{}"
        if node.type_name == "array":
            return "[]"
        if node.type_name == "element":
            if node.value is None:
                return "(element)"
            return str(node.value)
        if node.value is None:
            return f"<{node.type_name}>"
        return str(node.value)

    def _build_map_node_html(self, node: TreeNode) -> str:
        key = html_escape(node.key)
        head_color = self._map_header_color(node)
        lines: List[str] = []

        if node.children:
            summary_count = len(node.children)
            lines.append(
                f"<span style='color:{head_color}; font-weight:700'>{key}</span> "
                f"<span style='color:#d3dfff'>[{summary_count}]</span>"
            )
            preview_children = node.children[:8]
            for child in preview_children:
                child_key = html_escape(child.key)
                child_val = html_escape(self._map_brief_value(child))
                child_color = self._map_value_color(child)
                lines.append(
                    f"<span style='color:#65cfff; font-weight:600'>{child_key}</span>: "
                    f"<span style='color:{child_color}'>{child_val}</span>"
                )
            if len(node.children) > len(preview_children):
                lines.append("<span style='color:#9caad0'>...</span>")
        else:
            value = html_escape(self._map_brief_value(node))
            value_color = self._map_value_color(node)
            lines.append(
                f"<span style='color:{head_color}; font-weight:700'>{key}</span>: "
                f"<span style='color:{value_color}'>{value}</span>"
            )

        body = "<br/>".join(lines)
        return (
            "<div style='font-family: \"Cascadia Mono\", Consolas, monospace; "
            "font-size: 10.5pt; line-height: 1.25;'>"
            f"{body}</div>"
        )

    def _map_line_count(self, node: TreeNode) -> int:
        if node.children:
            count = 1 + min(len(node.children), 8)
            if len(node.children) > 8:
                count += 1
            return count
        return 1

    def _map_box_height(self, node: TreeNode) -> float:
        # Keep card sizes stable and readable.
        return max(58.0, 18.0 * self._map_line_count(node) + 18.0)

    def _compute_graph_layout(
        self,
        node: TreeNode,
        path: str,
        depth: int,
        positions: Dict[str, tuple[int, float, TreeNode, float]],
        edges: List[tuple[str, str]],
        next_leaf_y: List[float],
        vertical_gap: float,
    ) -> float:
        node_height = self._map_box_height(node)
        child_y_values: List[float] = []
        for child, segment in self._children_with_segments(node):
            child_path = f"{path}.{segment}"
            child_y = self._compute_graph_layout(
                child,
                child_path,
                depth + 1,
                positions,
                edges,
                next_leaf_y,
                vertical_gap,
            )
            child_y_values.append(child_y)
            edges.append((path, child_path))

        if child_y_values:
            node_y = sum(child_y_values) / len(child_y_values)
        else:
            node_y = next_leaf_y[0] + node_height / 2.0
            next_leaf_y[0] += node_height + vertical_gap

        positions[path] = (depth, node_y, node, node_height)
        return node_y

    def _add_arrow_tip(self, end: QPointF, control: QPointF) -> None:
        angle = math.atan2(end.y() - control.y(), end.x() - control.x())
        size = 8.0
        p1 = QPointF(
            end.x() - size * math.cos(angle - math.pi / 6),
            end.y() - size * math.sin(angle - math.pi / 6),
        )
        p2 = QPointF(
            end.x() - size * math.cos(angle + math.pi / 6),
            end.y() - size * math.sin(angle + math.pi / 6),
        )
        arrow_pen = QPen(QColor("#4f78bd"), 1.4)
        line1 = self.map_scene.addLine(end.x(), end.y(), p1.x(), p1.y(), arrow_pen)
        line2 = self.map_scene.addLine(end.x(), end.y(), p2.x(), p2.y(), arrow_pen)
        line1.setZValue(1)
        line2.setZValue(1)

    def _render_graph_map(self, root: TreeNode) -> None:
        self.map_scene.clear()
        self.map_rect_by_path.clear()
        self.map_alias_to_path.clear()
        self._map_root_key = root.key

        positions: Dict[str, tuple[int, float, TreeNode, float]] = {}
        edges: List[tuple[str, str]] = []
        self._compute_graph_layout(
            root,
            root.key,
            0,
            positions,
            edges,
            [40.0],
            vertical_gap=34.0,
        )

        box_width = 320.0
        col_gap = 380.0
        margin = 40.0
        geometry: Dict[str, tuple[float, float, float, float]] = {}

        for path, (depth, center_y, node, box_height) in sorted(
            positions.items(), key=lambda item: (item[1][0], item[1][1])
        ):
            x = margin + depth * col_gap
            html = self._build_map_node_html(node)
            text_item = QGraphicsTextItem()
            text_item.setHtml(html)
            text_item.setTextWidth(box_width - 22.0)
            text_height = float(text_item.document().size().height())
            box_height = max(box_height, text_height + 16.0)
            y = center_y - (box_height / 2.0)

            rect = self.map_scene.addRect(
                x,
                y,
                box_width,
                box_height,
                QPen(QColor("#4b5f93"), 1.2),
                QBrush(QColor("#252a3d")),
            )
            rect.setZValue(2)
            rect.setData(0, path)

            self.map_scene.addItem(text_item)
            text_item.setDefaultTextColor(QColor("#ffffff"))
            text_item.setPos(x + 10.0, y + 8.0)
            text_item.setZValue(3.5)
            text_item.setAcceptedMouseButtons(NO_MOUSE_BUTTON)

            self.map_rect_by_path[path] = rect
            self._register_map_aliases(path, root.key)
            geometry[path] = (x, y, box_width, box_height)

        connector_pen = QPen(QColor("#4f78bd"), 1.8)
        for parent_path, child_path in edges:
            if parent_path not in geometry or child_path not in geometry:
                continue

            px, py, pw, ph = geometry[parent_path]
            cx, cy, _, ch = geometry[child_path]
            start = QPointF(px + pw, py + ph / 2.0)
            end = QPointF(cx, cy + ch / 2.0)
            c1 = QPointF(start.x() + 100.0, start.y())
            c2 = QPointF(end.x() - 100.0, end.y())

            curve = QPainterPath(start)
            curve.cubicTo(c1, c2, end)
            curve_item = self.map_scene.addPath(curve, connector_pen)
            curve_item.setZValue(0)
            self._add_arrow_tip(end, c2)

        bounds = self.map_scene.itemsBoundingRect()
        self.map_scene.setSceneRect(bounds.adjusted(-80, -80, 80, 80))
        if not bounds.isNull():
            self.map_view.reset_zoom()
            root_rect = self.map_rect_by_path.get(root.key)
            if root_rect is not None:
                self.map_view.centerOn(root_rect)

    def _highlight_map_path(self, path: str) -> None:
        if not self.map_rect_by_path:
            return

        target_path = self.map_alias_to_path.get(path)
        if target_path is None and path.startswith("root."):
            target_path = self.map_alias_to_path.get(path[5:])
        if target_path is None and not path.startswith(f"{self._map_root_key}.") and path not in (".", "root", self._map_root_key):
            target_path = self.map_alias_to_path.get(f"{self._map_root_key}.{path}")
        if target_path is None:
            target_path = self.map_alias_to_path.get(".")
        if target_path is None:
            return

        for rect in self.map_rect_by_path.values():
            rect.setPen(QPen(QColor("#4b5f93"), 1.2))

        selected = self.map_rect_by_path.get(target_path)
        if selected is None:
            return

        selected.setPen(QPen(QColor("#ffd166"), 2.4))
        self.map_view.centerOn(selected)

    def _iter_tree_items(self) -> List[QTreeWidgetItem]:
        items: List[QTreeWidgetItem] = []

        def walk(item: QTreeWidgetItem) -> None:
            items.append(item)
            for idx in range(item.childCount()):
                walk(item.child(idx))

        for i in range(self.tree_view.topLevelItemCount()):
            walk(self.tree_view.topLevelItem(i))

        return items

    def search_next(self) -> None:
        query = self.search_box.text().strip()
        if not query:
            self.statusBar().showMessage("Enter a search string")
            return

        items = self._iter_tree_items()
        if not items:
            return

        if query != self.last_query:
            self.last_query = query
            self.last_match_index = -1

        start = self.last_match_index + 1
        query_lc = query.lower()

        for idx in range(start, len(items)):
            item = items[idx]
            haystack = f"{item.text(0)} {item.text(1)} {item.text(2)}".lower()
            if query_lc in haystack:
                self.last_match_index = idx
                self.tree_view.setCurrentItem(item)
                self.tree_view.scrollToItem(item)
                self.statusBar().showMessage(f"Search hit {idx + 1}/{len(items)}")
                return

        for idx in range(0, start):
            item = items[idx]
            haystack = f"{item.text(0)} {item.text(1)} {item.text(2)}".lower()
            if query_lc in haystack:
                self.last_match_index = idx
                self.tree_view.setCurrentItem(item)
                self.tree_view.scrollToItem(item)
                self.statusBar().showMessage("Search wrapped to start")
                return

        self.statusBar().showMessage("No matches found")

    def go_to_path(self) -> None:
        path = self.path_box.text().strip()
        if not path:
            self.statusBar().showMessage("Enter a path")
            return
        if not self.current_file:
            self.statusBar().showMessage("Load a file first")
            return

        root = self.roots_by_file[self.current_file]
        node = TreeOperations.get_node(root, path)
        if node is None:
            self.statusBar().showMessage(f"Path not found: {path}")
            return

        item = self.node_to_item.get(id(node))
        if item is None:
            item = self.path_to_item.get(path)

        if item is None:
            self.statusBar().showMessage("Matched node, but not visible in current tree state")
            return

        self.tree_view.setCurrentItem(item)
        self.tree_view.scrollToItem(item)
        self.statusBar().showMessage(f"Jumped to {item.data(0, PATH_ROLE)}")

    def show_tree_stats(self) -> None:
        if not self.current_file:
            self.statusBar().showMessage("Load a file first")
            return

        root = self.roots_by_file[self.current_file]
        count, depth = TreeOperations.get_stats(root)
        fmt = DataTreeBuilder.detect_format(self.current_file)

        QMessageBox.information(
            self,
            "Tree statistics",
            f"File: {Path(self.current_file).name}\n"
            f"Format: {fmt}\n"
            f"Total nodes: {count}\n"
            f"Max depth: {depth}",
        )

    def _show_tree_context_menu(self, pos) -> None:
        item = self.tree_view.itemAt(pos)
        if item is None:
            return

        menu = QMenu(self)
        copy_path = menu.addAction("Copy Path")
        copy_value = menu.addAction("Copy Value")
        menu.addSeparator()
        expand_branch = menu.addAction("Expand Branch")
        collapse_branch = menu.addAction("Collapse Branch")

        action = menu.exec_(self.tree_view.viewport().mapToGlobal(pos)) if not QT6 else menu.exec(self.tree_view.viewport().mapToGlobal(pos))
        if action is None:
            return

        clipboard = QApplication.clipboard()
        if action == copy_path:
            clipboard.setText(item.data(0, PATH_ROLE) or "")
            self.statusBar().showMessage("Path copied")
        elif action == copy_value:
            clipboard.setText(item.text(1))
            self.statusBar().showMessage("Value copied")
        elif action == expand_branch:
            self.tree_view.expandItem(item)
        elif action == collapse_branch:
            self.tree_view.collapseItem(item)

    def dragEnterEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(url.toLocalFile())

        if paths:
            self.load_files(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


def run_gui(initial_files: Optional[List[str]] = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Structured Tree Explorer")
    app.setOrganizationName("ADS")

    window = TreeExplorerWindow(initial_files=initial_files)
    window.show()

    if QT6:
        return app.exec()
    return app.exec_()


if __name__ == "__main__":
    preload = [arg for arg in sys.argv[1:] if os.path.exists(arg)]
    sys.exit(run_gui(preload))
