#!/usr/bin/env python3
import argparse
import os
import sys
from typing import Optional

from tree_core import Colors, DataTreeBuilder, ParseError, TreeOperations, TreeVisualizer


def print_custom_help() -> None:
    print(f"\n{Colors.HEADER}--- Structured Tree Viewer Help ---{Colors.RESET}\n")
    print(
        f"{Colors.BOLD}Usage:{Colors.RESET} python jtree.py <file> <command> [options]\n"
    )
    print(
        f"{Colors.BOLD}Supported extensions:{Colors.RESET} "
        ".json, .xml, .yml/.yaml, .toml, .ini/.cfg\n"
    )
    print(f"{Colors.BOLD}Commands:{Colors.RESET}")
    commands = [
        ("show", "Render the file as a colorful tree."),
        ("search <query>", "Search for keys or values containing a query string."),
        ("get <path>", "Get a specific node by dot path (e.g., users.0.name)."),
        ("info", "Display node count and max depth."),
        ("gui [files...]", "Launch the PyQt visual explorer."),
        ("help", "Show this help message."),
    ]

    for cmd, desc in commands:
        print(f"  {Colors.KEY}{cmd:<20}{Colors.RESET} {desc}")

    print(f"\n{Colors.BOLD}Examples:{Colors.RESET}")
    print("  python jtree.py test.json show")
    print("  python jtree.py layout.xml search button")
    print("  python jtree.py test.json get users.0.name")
    print("  python jtree.py gui test.json layout.xml")
    print()


def launch_gui(files: Optional[list[str]] = None) -> int:
    try:
        import jtree_gui
    except ImportError as exc:
        print(
            f"{Colors.ERROR}PyQt GUI dependencies are missing. "
            f"Install PyQt6 or PyQt5. Details: {exc}{Colors.RESET}"
        )
        return 1
    return jtree_gui.run_gui(files or [])


def parse_args(argv: list[str]) -> argparse.Namespace:
    if not argv:
        return argparse.Namespace(mode="help")

    first = argv[0].strip()
    if first in ("help", "-h", "--help"):
        return argparse.Namespace(mode="help")

    if first == "gui":
        return argparse.Namespace(mode="gui", files=argv[1:])

    file_arg = first
    command = argv[1].strip() if len(argv) > 1 else "show"
    valid = {"show", "search", "get", "info"}

    if command not in valid:
        raise ValueError(
            f"Unknown command '{command}'. Valid commands: show, search, get, info, gui, help"
        )

    args = argparse.Namespace(
        mode="cli",
        file=file_arg,
        command=command,
        query=None,
        path=None,
    )

    if command == "search":
        if len(argv) < 3:
            raise ValueError("Missing search query. Usage: python jtree.py <file> search <query>")
        args.query = " ".join(argv[2:])
    elif command == "get":
        if len(argv) < 3:
            raise ValueError("Missing path. Usage: python jtree.py <file> get <path>")
        args.path = argv[2]
    elif len(argv) > 2:
        extras = " ".join(argv[2:])
        raise ValueError(f"Unexpected arguments for '{command}': {extras}")

    return args


def _ensure_ansi_on_windows() -> None:
    if os.name == "nt":
        os.system("color")


def main() -> int:
    _ensure_ansi_on_windows()

    try:
        args = parse_args(sys.argv[1:])
    except ValueError as exc:
        print(f"{Colors.ERROR}Error: {exc}{Colors.RESET}\n")
        print_custom_help()
        return 1

    if args.mode == "help":
        print_custom_help()
        return 0

    if args.mode == "gui":
        return launch_gui(args.files)

    command = args.command

    try:
        root = DataTreeBuilder.parse_file(args.file)
    except ParseError as exc:
        print(f"{Colors.ERROR}Error: {exc}{Colors.RESET}")
        return 1

    if command == "show":
        print(f"\n{Colors.HEADER}--- Tree View ---{Colors.RESET}\n")
        TreeVisualizer.print_tree(root)
        print()
        return 0

    if command == "search":
        query = args.query
        print(f"\n{Colors.HEADER}--- Search Results for '{query}' ---{Colors.RESET}\n")
        results = TreeOperations.search(root, query)
        if results:
            for result in results:
                print(result)
        else:
            print(f"{Colors.DIM}No matches found.{Colors.RESET}")
        print()
        return 0

    if command == "get":
        path = args.path
        print(f"\n{Colors.HEADER}--- Node at '{path}' ---{Colors.RESET}\n")
        target = TreeOperations.get_node(root, path)
        if target is None:
            print(f"{Colors.ERROR}Node not found at path '{path}'{Colors.RESET}\n")
            return 1

        TreeVisualizer.print_tree(target, is_root=True)
        print()
        return 0

    if command == "info":
        node_count, max_depth = TreeOperations.get_stats(root)
        print(f"\n{Colors.HEADER}--- Tree Statistics ---{Colors.RESET}\n")
        print(f"{Colors.BOLD}Total Nodes:{Colors.RESET} {node_count}")
        print(f"{Colors.BOLD}Max Depth:{Colors.RESET}   {max_depth}")
        print(f"{Colors.DIM}(Depth includes the root container){Colors.RESET}\n")
        return 0

    print_custom_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
