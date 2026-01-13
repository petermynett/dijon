"""CLI command to display all commands in a hierarchical tree."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import click
import typer
from rich.console import Console
from typer.main import get_command

from ..base import get_logger

logger = get_logger(__name__)

# Known sources as fallback
# TODO: Populate this list with the data sources for your project.
# This is used as a fallback when source discovery fails.
KNOWN_SOURCES: list[str] = []


@dataclass
class OptionInfo:
    """Information about a command option/parameter."""

    name: str
    help_text: str | None = None
    is_flag: bool = False
    param_type: str | None = None


@dataclass
class CommandNode:
    """Represents a command or command group in the CLI tree."""

    name: str
    help_text: str | None = None
    is_group: bool = False
    is_broken: bool = False
    options: list[OptionInfo] = field(default_factory=list)
    children: list[CommandNode] = field(default_factory=list)


def discover_sources() -> list[str]:
    """Discover source names by scanning sources directory.

    Scans the sources directory for subdirectories and returns
    a list of source names. Filters out non-directory entries and
    common non-source directories like __pycache__.

    Returns:
        List of source names (e.g., ["transactions", "receipts", ...]).
    """
    sources_dir = Path(__file__).parent.parent.parent / "sources"
    sources = []

    if not sources_dir.exists():
        logger.warning("Sources directory not found: %s", sources_dir)
        return KNOWN_SOURCES

    try:
        for item in sources_dir.iterdir():
            is_valid_dir = (
                item.is_dir()
                and not item.name.startswith("_")
                and item.name != "__pycache__"
            )
            if is_valid_dir:
                sources.append(item.name)
    except Exception as e:
        logger.warning("Error scanning sources directory: %s", e)
        return KNOWN_SOURCES

    # Sort for deterministic output
    sources.sort()
    return sources


def _get_click_app(typer_app: typer.Typer) -> click.Group | None:
    """Get the underlying Click app from a Typer app.

    Args:
        typer_app: Typer application instance.

    Returns:
        Click Group instance, or None if access fails.
    """
    try:
        click_app = get_command(typer_app)
        return click_app if isinstance(click_app, click.Group) else None
    except Exception:
        return None


def _extract_options(click_cmd: click.Command) -> list[OptionInfo]:  # noqa: PLR0911, PLR0912
    """Extract option information from a Click command.

    Args:
        click_cmd: Click command instance.

    Returns:
        List of OptionInfo objects.
    """
    options = []
    try:
        for param in click_cmd.params:
            if isinstance(param, click.Option):
                # Get option names
                names = param.opts or param.secondary_opts or []
                if not names:
                    continue

                # Format name (prefer short form if available)
                SHORT_OPT_LEN = 2
                name_parts = []
                for opt in names:
                    if len(opt) == SHORT_OPT_LEN and opt.startswith("-"):
                        name_parts.append(opt)
                    else:
                        name_parts.append(opt)
                name = ", ".join(name_parts)

                # Determine type hint
                param_type = None
                if param.type is not None:
                    type_name = str(param.type)
                    if "Path" in type_name:
                        param_type = "PATH"
                    elif "int" in type_name.lower() or "Integer" in type_name:
                        param_type = "N"
                    elif "str" in type_name.lower() or "String" in type_name:
                        param_type = "TEXT"
                    elif "bool" in type_name.lower() or "Boolean" in type_name:
                        param_type = None  # Flags don't need type hints
                    else:
                        param_type = "VALUE"

                # Format option string
                if param_type:
                    option_str = f"{name} {param_type}"
                else:
                    option_str = name

                options.append(
                    OptionInfo(
                        name=option_str,
                        help_text=param.help,
                        is_flag=isinstance(param.type, click.types.BoolParamType)
                        or param.is_flag,
                    )
                )
    except Exception as e:
        logger.debug("Failed to extract options from command: %s", e)

    return options


def _get_help_text(click_cmd: click.Command) -> str | None:
    """Get help text from a Click command.

    Args:
        click_cmd: Click command instance.

    Returns:
        Help text string, or None if unavailable.
    """
    try:
        return click_cmd.get_short_help_str() or click_cmd.help
    except Exception:
        return None


def _sort_command_node(node: CommandNode) -> None:
    """Sort children of a command node with custom ordering.

    Prefers: acquire, ingest, load (in that order), then alphabetical.
    """
    if not node.children:
        return

    # Preferred order for subcommands
    preferred_order = ["acquire", "ingest", "load"]

    def sort_key(child: CommandNode) -> tuple[int, str]:
        """Return (priority, name) for sorting."""
        try:
            priority = preferred_order.index(child.name)
        except ValueError:
            # Not in preferred order, sort after all preferred items
            priority = len(preferred_order)
        return (priority, child.name)

    node.children.sort(key=sort_key)

    # Recursively sort all children
    for child in node.children:
        _sort_command_node(child)


def walk_typer_app(
    typer_app: typer.Typer,
    name: str | None = None,
) -> CommandNode:  # noqa: PLR0911
    """Walk a Typer app and build a command tree."""
    resolved = name or typer_app.info_name or "app"

    click_app = _get_click_app(typer_app)
    if click_app is None:
        return CommandNode(name=resolved, is_broken=True)

    root_node = _build_node_from_click(click_app, name=resolved)
    _sort_command_node(root_node)
    return root_node


def _build_node_from_click(click_cmd: click.Command, name: str | None = None) -> CommandNode:
    """Convert a Click command/group into a CommandNode recursively."""
    node_name = name or getattr(click_cmd, "name", "") or "command"
    is_group = isinstance(click_cmd, click.Group)
    help_text = _get_help_text(click_cmd)
    options = [] if is_group else _extract_options(click_cmd)

    node = CommandNode(
        name=node_name,
        help_text=help_text,
        is_group=is_group,
        options=options,
    )

    if is_group and getattr(click_cmd, "commands", None):
        for sub_name, sub_cmd in click_cmd.commands.items():
            child = _build_node_from_click(sub_cmd, name=sub_name)
            node.children.append(child)

    return node


def filter_tree(
    node: CommandNode,
    sources: list[str],
    filter_verb: str | None = None,
    verbose: bool = False,
    is_root: bool = False,
) -> CommandNode | None:  # noqa: PLR0911, PLR0912
    """Filter a command tree based on criteria.

    Args:
        node: Root node of the tree to filter.
        sources: List of source names for source filtering.
        filter_verb: Verb to filter by (e.g., "acquire", "load", "sources").
        verbose: If True, show help text and options (default is compact mode).
        is_root: Whether this is the root node (special handling for source filtering).

    Returns:
        Filtered CommandNode, or None if node should be excluded.
    """
    # Handle source filtering
    if filter_verb == "sources":
        # For root node, keep it but filter children to only sources
        if is_root:
            filtered_children = []
            for child in node.children:
                filtered_child = filter_tree(
                    child, sources, filter_verb="sources", verbose=verbose, is_root=False
                )
                if filtered_child is not None:
                    filtered_children.append(filtered_child)
            node.children = filtered_children
            # Apply compact mode if not verbose
            if not verbose:
                node.help_text = None
                node.options = []
            return node
        
        # Only include if this is a source command
        if node.name in sources:
            # Include this source and all its children
            filtered_children = []
            for child in node.children:
                filtered_child = filter_tree(
                    child, sources, filter_verb=None, verbose=verbose, is_root=False
                )
                if filtered_child is not None:
                    filtered_children.append(filtered_child)
            node.children = filtered_children
            # Apply compact mode if not verbose
            if not verbose:
                node.help_text = None
                node.options = []
            return node
        # Not a source, exclude
        return None

    # Handle verb filtering
    if filter_verb and filter_verb != "sources":
        # Check if this node or any descendant matches the verb
        matches = False
        if node.name == filter_verb:
            matches = True
        else:
            # Check children recursively
            filtered_children = []
            for child in node.children:
                filtered_child = filter_tree(
                    child, sources, filter_verb=filter_verb, verbose=verbose, is_root=False
                )
                if filtered_child is not None:
                    filtered_children.append(filtered_child)
                    matches = True
            node.children = filtered_children

        # If this is a group and has matching children, include it for context
        if node.is_group and matches:
            # Apply compact mode if not verbose
            if not verbose:
                node.help_text = None
                node.options = []
            return node
        # If this command matches, include it
        if matches and not node.is_group:
            # Apply compact mode if not verbose
            if not verbose:
                node.help_text = None
                node.options = []
            return node
        # Otherwise exclude
        return None

    # Apply compact mode (default: verbose=False means compact=True)
    if not verbose:
        node.help_text = None
        node.options = []

    # Recursively filter children
    filtered_children = []
    for child in node.children:
        filtered_child = filter_tree(
            child, sources, filter_verb=filter_verb, verbose=verbose, is_root=False
        )
        if filtered_child is not None:
            filtered_children.append(filtered_child)
    node.children = filtered_children

    return node


def render_tree(
    node: CommandNode,
    console: Console | None = None,
    indent: int = 0,
    indent_str: str = "  ",
) -> None:
    """Render a command tree using Rich with indentation and colors.

    Args:
        node: CommandNode to render.
        console: Rich Console instance (None to create new).
        indent: Current indentation level.
        indent_str: String to use for each indentation level.
    """
    if console is None:
        console = Console()

    # Build prefix with indentation
    prefix = indent_str * indent

    # Color scheme by level:
    # Level 0 (root): bold cyan
    # Level 1 (top-level groups/commands): bold yellow
    # Level 2: bold blue
    # Level 3+: bold green
    # Regular commands (non-groups): white/cyan

    if node.is_broken:
        label = f"{prefix}[red dim]{node.name} [BROKEN][/red dim]"
        console.print(label)
    elif node.is_group:
        if indent == 0:
            # Root level
            label_color = "bold cyan"
        elif indent == 1:
            # Top-level groups
            label_color = "bold yellow"
        elif indent == 2:
            # Second level
            label_color = "bold blue"
        else:
            # Deeper levels
            label_color = "bold green"

        label = f"{prefix}[{label_color}]{node.name}[/{label_color}]"
        if node.help_text:
            label += f" [dim]— {node.help_text}[/dim]"
        console.print(label)
    else:
        # Regular command (non-group)
        if indent == 0:
            label_color = "cyan"
        elif indent == 1:
            label_color = "yellow"
        elif indent == 2:
            label_color = "blue"
        else:
            label_color = "green"

        label = f"{prefix}[{label_color}]{node.name}[/{label_color}]"
        if node.help_text:
            label += f" [dim]— {node.help_text}[/dim]"
        console.print(label)

        # Render options on one line with indentation
        if node.options:
            option_prefix = prefix + indent_str
            option_part = " ".join([f"[dim][{opt.name}][/dim]" for opt in node.options])
            console.print(f"{option_prefix}{option_part}")

    # Render children with increased indentation
    for child in node.children:
        render_tree(child, console, indent=indent + 1, indent_str=indent_str)


def tree_command(
    typer_app: typer.Typer,
    filter_verb: str | None = None,
    verbose: bool = False,
) -> None:
    """Main entry point for the tree command.

    Displays all CLI commands in a hierarchical tree format with optional
    filtering. By default shows compact mode (command names only). Use --verbose
    to show descriptions and options.

    Args:
        typer_app: Root Typer application to introspect.
        filter_verb: Optional verb to filter by (e.g., "acquire", "load", "sources").
        verbose: If True, show help text and options (default is compact mode).
    """
    try:
        # Discover sources
        sources = discover_sources()

        # Walk the Typer app structure
        root_node = walk_typer_app(typer_app)

        # Apply filters (pass is_root=True for the root node)
        filtered_node = filter_tree(
            root_node, sources, filter_verb=filter_verb, verbose=verbose, is_root=True
        )

        if filtered_node is None:
            # No commands match the filter
            console = Console()
            console.print("[yellow]No commands match the specified filter.[/yellow]")
            return

        # Render the tree
        render_tree(filtered_node)
    except Exception as e:
        logger.exception("Error generating command tree")
        console = Console()
        console.print(f"[red]Error generating command tree: {e}[/red]")
        # Always succeed, even on error
        return

