"""Main entry point for Drey CLI."""

import asyncio
import subprocess
import os
import sys
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header,
    Footer,
    Input,
    Static,
    Button,
    Label,
    ListView,
    ListItem,
    RichLog,
)
from textual.binding import Binding
from textual import events
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.console import Console
import psutil

from drey_cli.ai_helper import AIAssistant, get_quick_suggestion, QUICK_SUGGESTIONS


# Command suggestions database
COMMAND_SUGGESTIONS = {
    "git": ["git status", "git add .", "git commit -m ''", "git push", "git pull", "git log --oneline", "git branch", "git checkout"],
    "docker": ["docker ps", "docker ps -a", "docker images", "docker compose up -d", "docker compose down", "docker logs", "docker exec -it"],
    "system": ["htop", "df -h", "free -h", "uname -a", "uptime", "whoami", "pwd", "ls -la"],
    "network": ["ip addr", "ping", "curl", "wget", "netstat -tulpn", "ss -tulpn"],
    "files": ["ls -la", "find . -name", "grep -r", "cat", "head", "tail -f", "chmod", "chown"],
    "process": ["ps aux", "kill", "killall", "top", "htop", "pgrep", "pkill"],
}

ALL_COMMANDS = []
for category, commands in COMMAND_SUGGESTIONS.items():
    ALL_COMMANDS.extend(commands)


class CommandOutput(RichLog):
    """Widget to display command output."""

    DEFAULT_CSS = """
    CommandOutput {
        background: #000000;
        color: #eee;
        padding: 1;
        border: solid #333;
        height: 100%;
    }
    """


class SystemStats(Static):
    """Display system statistics."""

    DEFAULT_CSS = """
    SystemStats {
        background: #000000;
        color: #0ff;
        padding: 1;
        border: solid #333;
        height: auto;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(id="stats-content")

    def on_mount(self) -> None:
        self.update_stats()
        self.set_interval(2, self.update_stats)

    def update_stats(self) -> None:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        stats_text = Text()
        stats_text.append("  CPU: ", style="bold cyan")
        stats_text.append(f"{cpu:5.1f}%", style="green" if cpu < 50 else "yellow" if cpu < 80 else "red")
        stats_text.append("  │  MEM: ", style="bold cyan")
        stats_text.append(f"{mem.percent:5.1f}%", style="green" if mem.percent < 50 else "yellow" if mem.percent < 80 else "red")
        stats_text.append(f" ({mem.used // (1024**3)}/{mem.total // (1024**3)}GB)", style="dim")
        stats_text.append("  │  DISK: ", style="bold cyan")
        stats_text.append(f"{disk.percent:5.1f}%", style="green" if disk.percent < 50 else "yellow" if disk.percent < 80 else "red")

        self.query_one("#stats-content", Static).update(stats_text)


class SuggestionsList(ListView):
    """List of command suggestions."""

    DEFAULT_CSS = """
    SuggestionsList {
        background: #000000;
        height: auto;
        max-height: 10;
        border: solid #333;
        display: none;
    }

    SuggestionsList.visible {
        display: block;
    }

    SuggestionsList > ListItem {
        background: #000000;
        color: #eee;
        padding: 0 1;
    }

    SuggestionsList > ListItem.--highlight {
        background: #333;
        color: #fff;
    }
    """


class QuickActions(Horizontal):
    """Quick action buttons."""

    DEFAULT_CSS = """
    QuickActions {
        height: 3;
        margin-bottom: 1;
        align: center middle;
        background: #000000;
    }

    QuickActions Button {
        margin: 0 1;
        min-width: 10;
        background: #111;
        color: #0f0;
        border: solid #333;
    }

    QuickActions Button:hover {
        background: #222;
    }
    """

    def compose(self) -> ComposeResult:
        yield Button("AI", id="btn-ai")
        yield Button("Docker", id="btn-docker")
        yield Button("Git", id="btn-git")
        yield Button("System", id="btn-system")
        yield Button("Files", id="btn-files")
        yield Button("Network", id="btn-network")


class CommandInput(Input):
    """Enhanced command input with autocomplete."""

    DEFAULT_CSS = """
    CommandInput {
        background: #000000;
        color: #0f0;
        border: solid #333;
        padding: 0 1;
        height: 3;
    }

    CommandInput:focus {
        border: solid #0f0;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(placeholder="Enter command or ? for AI help (e.g., ? how to find large files)", **kwargs)
        self.history: list[str] = []
        self.history_index = -1
        self.load_history()

    def load_history(self) -> None:
        """Load command history from bash history."""
        history_file = os.path.expanduser("~/.bash_history")
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", errors="ignore") as f:
                    self.history = [line.strip() for line in f.readlines()[-500:] if line.strip()]
            except Exception:
                pass

    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            if self.history and self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.value = self.history[-(self.history_index + 1)]
                self.cursor_position = len(self.value)
            event.prevent_default()
        elif event.key == "down":
            if self.history_index > 0:
                self.history_index -= 1
                self.value = self.history[-(self.history_index + 1)]
                self.cursor_position = len(self.value)
            elif self.history_index == 0:
                self.history_index = -1
                self.value = ""
            event.prevent_default()


class DreyCLI(App):
    """Main Drey CLI Application."""

    # Disable command palette and allow terminal paste
    ENABLE_COMMAND_PALETTE = False

    def __init__(self):
        super().__init__()
        self.cwd = os.getcwd()
        self.current_suggestions: list[str] = []
        self.ai = AIAssistant()

    # Override to disable mouse capture for paste support
    def on_mount(self) -> None:
        self.query_one("#command-input", CommandInput).focus()
        # Disable mouse capture so right-click paste works
        self.capture_mouse(False)

    CSS = """
    Screen {
        background: #000000;
    }

    Header {
        background: #000000;
        color: #0f0;
    }

    Footer {
        background: #000000;
    }

    #main-container {
        height: 100%;
        padding: 1;
        background: #000000;
    }

    #output-container {
        height: 1fr;
        margin-bottom: 1;
    }

    #input-area {
        height: auto;
    }

    #cwd-label {
        color: #0f0;
        text-style: bold;
        padding: 0 1;
        height: 1;
    }

    #welcome-panel {
        background: #000000;
        border: solid #333;
        padding: 1;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+d", "docker_menu", "Docker"),
        Binding("ctrl+g", "git_menu", "Git"),
        Binding("ctrl+a", "ai_help", "AI Help"),
        Binding("escape", "hide_suggestions", "Hide"),
        Binding("tab", "show_suggestions", "Suggest", show=False),
    ]

    TITLE = "Drey CLI"
    SUB_TITLE = "Modern Terminal with AI"

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main-container"):
            yield SystemStats()
            yield QuickActions()

            with ScrollableContainer(id="output-container"):
                yield Static(self.get_welcome_panel(), id="welcome-panel")
                yield CommandOutput(id="output", highlight=True, markup=True)

            with Vertical(id="input-area"):
                yield Static(f"  {self.cwd}", id="cwd-label")
                yield SuggestionsList(id="suggestions")
                yield CommandInput(id="command-input")

        yield Footer()

    def get_welcome_panel(self) -> Text:
        text = Text()
        text.append("  Welcome to ", style="bold white")
        text.append("Drey CLI", style="bold cyan")
        text.append(" v0.1.0\n\n", style="dim")

        text.append("  AI Assistant:\n", style="bold magenta")
        text.append("    • ", style="white")
        text.append("? ", style="bold yellow")
        text.append("your question", style="white")
        text.append("  →  Ask AI anything\n", style="dim")
        text.append("    • Examples: ", style="white")
        text.append("? how to find large files", style="dim")
        text.append(" | ", style="white")
        text.append("? compress a folder\n\n", style="dim")

        text.append("  Commands:\n", style="bold yellow")
        text.append("    • Type any command and press Enter\n", style="white")
        text.append("    • Press Tab for smart suggestions\n", style="white")
        text.append("    • Use ↑↓ arrows for command history\n", style="white")

        text.append("\n  Shortcuts: ", style="bold yellow")
        text.append("Ctrl+L ", style="cyan")
        text.append("Clear  ", style="dim")
        text.append("Ctrl+A ", style="cyan")
        text.append("AI  ", style="dim")
        text.append("Ctrl+D ", style="cyan")
        text.append("Docker  ", style="dim")
        text.append("Ctrl+G ", style="cyan")
        text.append("Git  ", style="dim")
        text.append("Ctrl+C ", style="cyan")
        text.append("Quit", style="dim")
        return text

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "command-input":
            self.update_suggestions(event.value)

    def update_suggestions(self, text: str) -> None:
        suggestions_list = self.query_one("#suggestions", SuggestionsList)
        suggestions_list.clear()

        if not text or text.startswith("?"):
            suggestions_list.remove_class("visible")
            return

        # Find matching commands
        matches = []
        text_lower = text.lower()

        # Search in all commands
        for cmd in ALL_COMMANDS:
            if text_lower in cmd.lower():
                matches.append(cmd)

        # Search in history
        cmd_input = self.query_one("#command-input", CommandInput)
        for hist_cmd in reversed(cmd_input.history[-50:]):
            if text_lower in hist_cmd.lower() and hist_cmd not in matches:
                matches.append(hist_cmd)

        if matches:
            self.current_suggestions = matches[:8]
            for cmd in self.current_suggestions:
                suggestions_list.append(ListItem(Label(cmd)))
            suggestions_list.add_class("visible")
        else:
            suggestions_list.remove_class("visible")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "suggestions":
            label = event.item.query_one(Label)
            cmd_input = self.query_one("#command-input", CommandInput)
            cmd_input.value = str(label.renderable)
            cmd_input.cursor_position = len(cmd_input.value)
            event.list_view.remove_class("visible")
            cmd_input.focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "command-input":
            command = event.value.strip()
            if command:
                # Check if it's an AI query
                if command.startswith("?"):
                    query = command[1:].strip()
                    if query:
                        await self.ask_ai(query)
                elif command.lower().startswith("/ask "):
                    query = command[5:].strip()
                    if query:
                        await self.ask_ai(query)
                else:
                    await self.run_command(command)

                event.input.value = ""
                event.input.history.append(command)
                event.input.history_index = -1
                self.query_one("#suggestions", SuggestionsList).remove_class("visible")

    async def ask_ai(self, query: str) -> None:
        """Ask the AI assistant a question."""
        output = self.query_one("#output", CommandOutput)

        # Show the question
        output.write(Text(f"\n  🤖 AI Query:\n", style="bold magenta"))
        output.write(Text(f"  ? {query}\n\n", style="bold yellow"))

        # Check for quick suggestions first (no API needed)
        quick = get_quick_suggestion(query)
        if quick:
            output.write(Text("  💡 Quick Suggestion:\n", style="bold green"))
            output.write(Text(f"  {quick}\n\n", style="bold white"))
            output.write(Text("  (Asking AI for more details...)\n\n", style="dim"))

        # Stream AI response
        output.write(Text("  ", style="white"))

        try:
            async for chunk in self.ai.ask(query):
                # Handle newlines in the response
                lines = chunk.split('\n')
                for i, line in enumerate(lines):
                    if i > 0:
                        output.write(Text("\n  ", style="white"))
                    if line:
                        output.write(Text(line, style="white"))
        except Exception as e:
            output.write(Text(f"\n  Error: {e}\n", style="bold red"))

        output.write(Text("\n\n", style="white"))

    async def run_command(self, command: str) -> None:
        output = self.query_one("#output", CommandOutput)

        # Show command being run
        output.write(Text(f"\n  {self.cwd}\n", style="bold cyan"))
        output.write(Text(f"  $ {command}\n", style="bold green"))

        # Handle built-in commands
        if command.startswith("cd "):
            path = command[3:].strip()
            try:
                if path == "~":
                    path = os.path.expanduser("~")
                elif path.startswith("~/"):
                    path = os.path.expanduser(path)
                os.chdir(path)
                self.cwd = os.getcwd()
                self.query_one("#cwd-label", Static).update(f"  {self.cwd}")
                output.write(Text(f"  Changed to: {self.cwd}\n", style="dim"))
            except Exception as e:
                output.write(Text(f"  Error: {e}\n", style="bold red"))
            return

        if command == "clear":
            output.clear()
            return

        if command == "exit" or command == "quit":
            self.exit()
            return

        # Run external command
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.cwd,
            )

            for line in iter(process.stdout.readline, ''):
                if line:
                    output.write(Text(f"  {line.rstrip()}\n", style="white"))

            process.wait()

            if process.returncode != 0:
                output.write(Text(f"\n  Exit code: {process.returncode}\n", style="yellow"))

        except Exception as e:
            output.write(Text(f"  Error: {e}\n", style="bold red"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        output = self.query_one("#output", CommandOutput)

        if event.button.id == "btn-ai":
            self.show_ai_help(output)
        elif event.button.id == "btn-docker":
            self.show_category_commands("docker", output)
        elif event.button.id == "btn-git":
            self.show_category_commands("git", output)
        elif event.button.id == "btn-system":
            self.show_category_commands("system", output)
        elif event.button.id == "btn-files":
            self.show_category_commands("files", output)
        elif event.button.id == "btn-network":
            self.show_category_commands("network", output)

    def show_ai_help(self, output: CommandOutput) -> None:
        """Show AI help and example queries."""
        output.write(Text("\n  🤖 AI Assistant\n", style="bold magenta"))
        output.write(Text("  ─────────────────────────────────────\n", style="dim"))

        if self.ai.is_configured():
            output.write(Text("  ✓ AI is ready!\n\n", style="bold green"))
        else:
            output.write(Text("  ⚠ API key not set. Set ANTHROPIC_API_KEY to enable.\n\n", style="yellow"))

        output.write(Text("  How to use:\n", style="bold cyan"))
        output.write(Text("    ? ", style="bold yellow"))
        output.write(Text("your question", style="white"))
        output.write(Text("     (e.g., ? how to find large files)\n\n", style="dim"))

        output.write(Text("  Quick Suggestions (no API needed):\n", style="bold cyan"))
        for i, (key, cmd) in enumerate(list(QUICK_SUGGESTIONS.items())[:8]):
            output.write(Text(f"    • {key}: ", style="white"))
            output.write(Text(f"{cmd[:50]}{'...' if len(cmd) > 50 else ''}\n", style="dim"))

        output.write(Text("\n  Try: ", style="bold yellow"))
        output.write(Text("? how do I check disk space\n", style="white"))

    def show_category_commands(self, category: str, output: CommandOutput) -> None:
        output.write(Text(f"\n  {category.upper()} Commands:\n", style="bold cyan"))
        for cmd in COMMAND_SUGGESTIONS.get(category, []):
            output.write(Text(f"    • {cmd}\n", style="white"))
        output.write(Text("\n  Type or click a command to run it.\n", style="dim"))

    def action_clear(self) -> None:
        self.query_one("#output", CommandOutput).clear()

    def action_hide_suggestions(self) -> None:
        self.query_one("#suggestions", SuggestionsList).remove_class("visible")

    def action_docker_menu(self) -> None:
        output = self.query_one("#output", CommandOutput)
        self.show_category_commands("docker", output)

    def action_git_menu(self) -> None:
        output = self.query_one("#output", CommandOutput)
        self.show_category_commands("git", output)

    def action_ai_help(self) -> None:
        output = self.query_one("#output", CommandOutput)
        self.show_ai_help(output)

    def action_show_suggestions(self) -> None:
        cmd_input = self.query_one("#command-input", CommandInput)
        if cmd_input.value:
            self.update_suggestions(cmd_input.value)
        else:
            # Show all categories
            output = self.query_one("#output", CommandOutput)
            output.write(Text("\n  Available Categories:\n", style="bold cyan"))
            for category in COMMAND_SUGGESTIONS:
                output.write(Text(f"    • {category}\n", style="white"))


def main():
    """Entry point."""
    app = DreyCLI()
    app.run()


if __name__ == "__main__":
    main()
