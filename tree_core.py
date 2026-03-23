#!/usr/bin/env python3
"""Core tree parsing and operations for structured files."""

from __future__ import annotations

import configparser
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    TREE_LINES = "\033[90m"
    BRACKET = "\033[93m"

    KEY = "\033[94m"
    STRING = "\033[92m"
    NUMBER = "\033[96m"
    BOOLEAN = "\033[95m"
    NULL = "\033[91m"

    HEADER = "\033[95m"
    ERROR = "\033[91m"
    SUCCESS = "\033[92m"


class ParseError(Exception):
    """Raised when a file cannot be parsed into a tree."""


@dataclass
class TreeNode:
    key: str
    value: Optional[str]
    type_name: str
    children: List["TreeNode"]

    def __init__(self, key: str, value: Optional[str], type_name: str):
        self.key = key
        self.value = value
        self.type_name = type_name
        self.children = []

    def add_child(self, node: "TreeNode") -> None:
        self.children.append(node)

    def is_leaf(self) -> bool:
        if self.children:
            return False
        return self.type_name not in ("object", "array", "element")


class DataTreeBuilder:
    SUPPORTED_FORMATS = {
        ".json": "json",
        ".xml": "xml",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
    }

    @classmethod
    def parse_file(cls, filepath: str) -> TreeNode:
        if not os.path.exists(filepath):
            raise ParseError(f"File '{filepath}' not found.")

        ext = os.path.splitext(filepath)[1].lower()
        file_format = cls.SUPPORTED_FORMATS.get(ext)
        parsers = {
            "json": cls._parse_json,
            "xml": cls._parse_xml,
            "yaml": cls._parse_yaml,
            "toml": cls._parse_toml,
            "ini": cls._parse_ini,
        }

        if file_format:
            return parsers[file_format](filepath)

        for fmt in ("json", "xml", "yaml", "toml", "ini"):
            try:
                return parsers[fmt](filepath)
            except ParseError:
                continue

        supported = ", ".join(sorted(cls.SUPPORTED_FORMATS))
        raise ParseError(
            f"Unsupported or unreadable format for '{filepath}'. Supported: {supported}"
        )

    @classmethod
    def detect_format(cls, filepath: str) -> str:
        ext = os.path.splitext(filepath)[1].lower()
        return cls.SUPPORTED_FORMATS.get(ext, "auto")

    @staticmethod
    def _build_tree(key: str, value: Any) -> TreeNode:
        if isinstance(value, dict):
            node = TreeNode(key, None, "object")
            for child_key, child_value in value.items():
                node.add_child(DataTreeBuilder._build_tree(str(child_key), child_value))
            return node
        if isinstance(value, list):
            node = TreeNode(key, None, "array")
            for idx, child_value in enumerate(value):
                node.add_child(DataTreeBuilder._build_tree(str(idx), child_value))
            return node
        if isinstance(value, str):
            return TreeNode(key, value, "string")
        if isinstance(value, bool):
            return TreeNode(key, str(value).lower(), "boolean")
        if value is None:
            return TreeNode(key, "null", "null")
        if isinstance(value, (int, float)):
            return TreeNode(key, str(value), "number")
        return TreeNode(key, str(value), "unknown")

    @staticmethod
    def _parse_json(filepath: str) -> TreeNode:
        try:
            with open(filepath, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            return DataTreeBuilder._build_tree("root", data)
        except json.JSONDecodeError as exc:
            raise ParseError(f"Invalid JSON in '{filepath}': {exc}") from exc
        except Exception as exc:
            raise ParseError(f"Unable to parse JSON '{filepath}': {exc}") from exc

    @staticmethod
    def _build_xml_tree(element: ET.Element) -> TreeNode:
        node = TreeNode(element.tag, None, "element")

        if element.attrib:
            attrs = TreeNode("@attributes", None, "object")
            for attr_key, attr_val in element.attrib.items():
                attrs.add_child(TreeNode(attr_key, attr_val, "string"))
            node.add_child(attrs)

        text = (element.text or "").strip()
        if text:
            node.value = text

        for child in list(element):
            node.add_child(DataTreeBuilder._build_xml_tree(child))

        return node

    @staticmethod
    def _parse_xml(filepath: str) -> TreeNode:
        try:
            root = ET.parse(filepath).getroot()
            return DataTreeBuilder._build_xml_tree(root)
        except ET.ParseError as exc:
            raise ParseError(f"Invalid XML in '{filepath}': {exc}") from exc
        except Exception as exc:
            raise ParseError(f"Unable to parse XML '{filepath}': {exc}") from exc

    @staticmethod
    def _parse_yaml(filepath: str) -> TreeNode:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ParseError(
                "YAML support requires PyYAML. Install with: pip install pyyaml"
            ) from exc

        try:
            with open(filepath, "r", encoding="utf-8") as file_obj:
                data = yaml.safe_load(file_obj)
            if data is None:
                data = {}
            return DataTreeBuilder._build_tree("root", data)
        except Exception as exc:
            raise ParseError(f"Unable to parse YAML '{filepath}': {exc}") from exc

    @staticmethod
    def _parse_toml(filepath: str) -> TreeNode:
        toml_loader = None
        try:
            import tomllib as toml_loader  # type: ignore
        except ImportError:
            try:
                import tomli as toml_loader  # type: ignore
            except ImportError as exc:
                raise ParseError(
                    "TOML support requires Python 3.11+ or tomli (pip install tomli)"
                ) from exc

        try:
            with open(filepath, "rb") as file_obj:
                data = toml_loader.load(file_obj)
            return DataTreeBuilder._build_tree("root", data)
        except Exception as exc:
            raise ParseError(f"Unable to parse TOML '{filepath}': {exc}") from exc

    @staticmethod
    def _parse_ini(filepath: str) -> TreeNode:
        parser = configparser.ConfigParser()
        try:
            with open(filepath, "r", encoding="utf-8") as file_obj:
                parser.read_file(file_obj)

            data = {}
            for section in parser.sections():
                data[section] = dict(parser.items(section))

            # Include DEFAULT section if present.
            if parser.defaults():
                data["DEFAULT"] = dict(parser.defaults())

            return DataTreeBuilder._build_tree("root", data)
        except Exception as exc:
            raise ParseError(f"Unable to parse INI '{filepath}': {exc}") from exc


class TreeVisualizer:
    @staticmethod
    def _format_value(node: TreeNode, use_color: bool = True) -> str:
        color = {
            "string": Colors.STRING,
            "number": Colors.NUMBER,
            "boolean": Colors.BOOLEAN,
            "null": Colors.NULL,
        }.get(node.type_name, Colors.RESET)

        if node.type_name == "object":
            return f"{Colors.BRACKET}{{}}{Colors.RESET} {Colors.DIM}(object){Colors.RESET}" if use_color else "{} (object)"
        if node.type_name == "array":
            return f"{Colors.BRACKET}[]{Colors.RESET} {Colors.DIM}(array){Colors.RESET}" if use_color else "[] (array)"
        if node.type_name == "element":
            if node.value:
                val = f"\"{node.value}\""
                return f"{Colors.DIM}(element){Colors.RESET}: {Colors.STRING}{val}{Colors.RESET}" if use_color else f"(element): {val}"
            return f"{Colors.DIM}(element){Colors.RESET}" if use_color else "(element)"

        display_val = node.value if node.value is not None else f"<{node.type_name}>"
        if node.type_name == "string":
            display_val = f"\"{display_val}\""
        if use_color:
            return f": {color}{display_val}{Colors.RESET}"
        return f": {display_val}"

    @classmethod
    def print_tree(
        cls,
        node: TreeNode,
        prefix: str = "",
        is_last: bool = True,
        is_root: bool = True,
        use_color: bool = True,
    ) -> None:
        connector = "\\-- " if is_last else "|-- "
        if is_root:
            connector = ""
            print_prefix = ""
        else:
            line_color = Colors.TREE_LINES if use_color else ""
            reset = Colors.RESET if use_color else ""
            print_prefix = f"{line_color}{prefix}{connector}{reset}"

        key_str = f"{Colors.KEY}{node.key}{Colors.RESET}" if use_color else node.key
        value_str = cls._format_value(node, use_color=use_color)

        print(f"{print_prefix}{key_str}{value_str}")

        child_prefix = prefix + ("    " if is_last else "|   ")
        if is_root:
            child_prefix = ""

        child_count = len(node.children)
        for idx, child in enumerate(node.children):
            cls.print_tree(
                child,
                prefix=child_prefix,
                is_last=(idx == child_count - 1),
                is_root=False,
                use_color=use_color,
            )


class TreeOperations:
    @staticmethod
    def _node_display_value(node: TreeNode) -> str:
        if node.value is not None:
            return node.value
        return f"<{node.type_name}>"

    @staticmethod
    def _normalize_for_display(path: str, root_key: str) -> str:
        if path == root_key:
            return "."
        if root_key == "root" and path.startswith(f"{root_key}."):
            return path[len(root_key) + 1 :]
        return path

    @staticmethod
    def search(
        node: TreeNode,
        query: str,
        path: str = "",
        root_key: Optional[str] = None,
    ) -> List[str]:
        results: List[str] = []
        if root_key is None:
            root_key = node.key

        current_path = node.key if not path else path
        display_path = TreeOperations._normalize_for_display(current_path, root_key=root_key)

        query_lc = query.lower()
        if query_lc in node.key.lower():
            results.append(
                f"{Colors.KEY}{display_path}{Colors.RESET}: {TreeOperations._node_display_value(node)}"
            )

        if node.value is not None and query_lc in str(node.value).lower():
            if query_lc not in node.key.lower():
                results.append(f"{Colors.KEY}{display_path}{Colors.RESET}: {node.value}")

        key_counts: dict[str, int] = {}
        for child in node.children:
            key_counts[child.key] = key_counts.get(child.key, 0) + 1

        seen: dict[str, int] = {}
        for child in node.children:
            seen_idx = seen.get(child.key, 0)
            seen[child.key] = seen_idx + 1

            segment = child.key
            if key_counts[child.key] > 1 and not child.key.isdigit():
                segment = f"{child.key}[{seen_idx}]"

            child_path = f"{current_path}.{segment}"
            results.extend(
                TreeOperations.search(
                    child,
                    query,
                    path=child_path,
                    root_key=root_key,
                )
            )

        return results

    @staticmethod
    def get_node(root: TreeNode, path: str) -> Optional[TreeNode]:
        if not path or path == ".":
            return root

        if path == root.key:
            return root
        if path.startswith(f"{root.key}."):
            path = path[len(root.key) + 1 :]
        if path.startswith("root."):
            path = path[5:]
        if path == "root":
            return root

        current = root
        parts = [segment for segment in path.split(".") if segment]
        for part in parts:
            indexed = re.fullmatch(r"(.+)\[(\d+)\]", part)
            if indexed:
                key = indexed.group(1)
                idx = int(indexed.group(2))
                matches = [child for child in current.children if child.key == key]
                if idx >= len(matches):
                    return None
                current = matches[idx]
                continue

            key_match = [child for child in current.children if child.key == part]
            if key_match:
                current = key_match[0]
                continue

            if part.isdigit():
                idx = int(part)
                if idx < len(current.children):
                    current = current.children[idx]
                    continue

            return None

        return current

    @staticmethod
    def get_stats(node: TreeNode) -> Tuple[int, int]:
        count = 1
        depth = 1
        max_child_depth = 0
        for child in node.children:
            child_count, child_depth = TreeOperations.get_stats(child)
            count += child_count
            max_child_depth = max(max_child_depth, child_depth)
        return count, depth + max_child_depth
