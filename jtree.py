#!/usr/bin/env python3
import argparse
import os
import sys
from typing import Optional

from tree_core import (
    Colors,
    DataTreeBuilder,
    GraphOperations,
    ParseError,
    TreeGraphBuilder,
    TreeOperations,
    TreeVisualizer,
)


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
        ("graph-info", "Display graph node/edge counts and cycle status."),
        ("graph-bfs <start>", "Run BFS traversal from a start path."),
        ("graph-path <start> <end>", "Find shortest path (BFS) from start to end."),
        ("graph-cycle", "Check if graph has a cycle."),
        ("gui [files...]", "Launch the PyQt visual explorer."),
        ("help", "Show this help message."),
    ]

    for cmd, desc in commands:
        print(f"  {Colors.KEY}{cmd:<20}{Colors.RESET} {desc}")

    print(f"\n{Colors.BOLD}Examples:{Colors.RESET}")
    print("  python jtree.py test.json show")
    print("  python jtree.py layout.xml search button")
    print("  python jtree.py test.json get users.0.name")
    print("  python jtree.py test.json graph-info")
    print("  python jtree.py test.json graph-bfs .")
    print("  python jtree.py test.json graph-path . root.project1")
    print("  python jtree.py test.json graph-cycle")
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
    valid = {
        "show",
        "search",
        "get",
        "info",
        "graph-info",
        "graph-bfs",
        "graph-path",
        "graph-cycle",
    }

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
        start=None,
        end=None,
    )

    if command == "search":
        if len(argv) < 3:
            raise ValueError("Missing search query. Usage: python jtree.py <file> search <query>")
        args.query = " ".join(argv[2:])
    elif command == "get":
        if len(argv) < 3:
            raise ValueError("Missing path. Usage: python jtree.py <file> get <path>")
        args.path = argv[2]
    elif command == "graph-bfs":
        if len(argv) < 3:
            raise ValueError("Missing start path. Usage: python jtree.py <file> graph-bfs <start>")
        args.start = argv[2]
        if len(argv) > 3:
            extras = " ".join(argv[3:])
            raise ValueError(f"Unexpected arguments for '{command}': {extras}")
    elif command == "graph-path":
        if len(argv) < 4:
            raise ValueError(
                "Missing arguments. Usage: python jtree.py <file> graph-path <start> <end>"
            )
        args.start = argv[2]
        args.end = argv[3]
        if len(argv) > 4:
            extras = " ".join(argv[4:])
            raise ValueError(f"Unexpected arguments for '{command}': {extras}")
    elif command in ("graph-info", "graph-cycle"):
        if len(argv) > 2:
            extras = " ".join(argv[2:])
            raise ValueError(f"Unexpected arguments for '{command}': {extras}")
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

    if command.startswith("graph-"):
        graph = TreeGraphBuilder.build_from_tree(root)

        if command == "graph-info":
            print(f"\n{Colors.HEADER}--- Graph Statistics ---{Colors.RESET}\n")
            print(f"{Colors.BOLD}Total Graph Nodes:{Colors.RESET} {graph.node_count()}")
            print(f"{Colors.BOLD}Total Graph Edges:{Colors.RESET} {graph.edge_count()}")
            print(
                f"{Colors.BOLD}Cycle Present:{Colors.RESET} "
                f"{'yes' if GraphOperations.has_cycle(graph) else 'no'}"
            )
            print()
            return 0

        if command == "graph-bfs":
            start = args.start
            order = GraphOperations.bfs_order(graph, start)
            if order is None:
                print(f"{Colors.ERROR}Start node not found: {start}{Colors.RESET}\n")
                return 1

            print(f"\n{Colors.HEADER}--- Graph BFS from '{start}' ---{Colors.RESET}\n")
            print(f"{Colors.BOLD}Visit count:{Colors.RESET} {len(order)}")
            for idx, node_id in enumerate(order, start=1):
                print(f"{idx:>3}. {node_id}")
            print()
            return 0

        if command == "graph-path":
            start = args.start
            end = args.end
            path_nodes = GraphOperations.shortest_path(graph, start, end)
            if path_nodes is None:
                print(
                    f"{Colors.ERROR}No path found (or node missing) between '{start}' and '{end}'.{Colors.RESET}\n"
                )
                return 1

            print(
                f"\n{Colors.HEADER}--- Shortest Graph Path: '{start}' -> '{end}' ---{Colors.RESET}\n"
            )
            print(f"{Colors.BOLD}Hops:{Colors.RESET} {max(0, len(path_nodes) - 1)}")
            print(" -> ".join(path_nodes))
            print()
            return 0

        if command == "graph-cycle":
            has_cycle = GraphOperations.has_cycle(graph)
            print(f"\n{Colors.HEADER}--- Graph Cycle Check ---{Colors.RESET}\n")
            if has_cycle:
                print(f"{Colors.ERROR}Cycle detected in graph.{Colors.RESET}")
            else:
                print(f"{Colors.SUCCESS}No cycle detected in graph.{Colors.RESET}")
            print()
            return 0

    print_custom_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
