# Drey CLI

A modern terminal interface with AI assistance, smart autocomplete, and system monitoring.

## Features

- **AI Assistant** - Ask questions in natural language, get command suggestions
- **Dark themed UI** - Easy on the eyes
- **Smart autocomplete** - Suggestions as you type
- **Command history** - Navigate with arrow keys
- **Live system stats** - CPU, memory, disk usage
- **Quick actions** - AI, Docker, Git, System, Files, Network buttons

## Installation

```bash
cd /home/mother/homelab/drey-cli
uv sync
```

## Usage

```bash
uv run drey
```

## AI Assistant

Ask questions by starting with `?`:

```
? how to find large files
? compress a folder
? check disk space
? list running docker containers
```

To enable full AI responses, set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY='your-api-key'
uv run drey
```

Without the API key, you'll still get quick suggestions for common tasks.

## Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+A` | AI Help |
| `Ctrl+L` | Clear screen |
| `Ctrl+D` | Docker commands |
| `Ctrl+G` | Git commands |
| `Ctrl+C` | Quit |
| `Tab` | Show suggestions |
| `↑↓` | Navigate history |
| `Escape` | Hide suggestions |

## Quick Suggestions (No API needed)

The CLI includes instant suggestions for common tasks:
- Find large files
- Check disk/memory usage
- Docker commands
- Git operations
- Compress/extract archives
- And more...
