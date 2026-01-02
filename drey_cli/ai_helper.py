"""AI Assistant for Drey CLI using Claude."""

import os
import httpx
from typing import AsyncGenerator

# System prompt for the AI assistant
SYSTEM_PROMPT = """You are a helpful Linux command-line assistant integrated into a terminal called Drey CLI.

Your role is to:
1. Help users find the right commands for their tasks
2. Explain what commands do in simple terms
3. Provide examples that users can copy and run
4. Warn about potentially dangerous commands

Guidelines:
- Keep responses concise and terminal-friendly
- Format commands in a clear way users can copy
- If a task needs multiple commands, number them
- Always prioritize safety - warn about rm -rf, sudo, etc.
- If you're not sure, say so

The user is running Ubuntu Linux. Respond in a helpful, friendly manner."""


class AIAssistant:
    """AI Assistant using Claude API."""

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-sonnet-4-20250514"

    def is_configured(self) -> bool:
        """Check if API key is set."""
        return bool(self.api_key)

    async def ask(self, question: str) -> AsyncGenerator[str, None]:
        """Ask Claude a question and stream the response."""
        if not self.api_key:
            yield "⚠️  AI not configured. Set ANTHROPIC_API_KEY environment variable.\n"
            yield "\nTo set it up:\n"
            yield "  export ANTHROPIC_API_KEY='your-api-key'\n"
            yield "\nGet your API key from: https://console.anthropic.com/\n"
            return

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "stream": True,
            "messages": [
                {"role": "user", "content": question}
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.base_url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield f"⚠️  API Error: {response.status_code}\n{error_text.decode()}\n"
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                import json
                                event = json.loads(data)
                                if event.get("type") == "content_block_delta":
                                    delta = event.get("delta", {})
                                    if "text" in delta:
                                        yield delta["text"]
                            except json.JSONDecodeError:
                                continue

        except httpx.TimeoutException:
            yield "⚠️  Request timed out. Please try again.\n"
        except httpx.ConnectError:
            yield "⚠️  Could not connect to AI service. Check your internet connection.\n"
        except Exception as e:
            yield f"⚠️  Error: {str(e)}\n"

    async def ask_sync(self, question: str) -> str:
        """Ask Claude a question and return full response."""
        response_parts = []
        async for part in self.ask(question):
            response_parts.append(part)
        return "".join(response_parts)


# Quick command suggestions without API
QUICK_SUGGESTIONS = {
    "find large files": "find . -type f -size +100M -exec ls -lh {} \\;",
    "disk usage": "du -sh */ | sort -rh | head -20",
    "memory usage": "free -h && echo '---' && ps aux --sort=-%mem | head -10",
    "cpu usage": "top -bn1 | head -20",
    "running processes": "ps aux --sort=-%cpu | head -20",
    "listening ports": "ss -tulpn",
    "docker running": "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",
    "docker logs": "docker logs --tail 100 -f CONTAINER_NAME",
    "git status": "git status -sb",
    "git log": "git log --oneline --graph -20",
    "find text in files": "grep -rn 'SEARCH_TERM' .",
    "watch file changes": "watch -n 1 'ls -la'",
    "system info": "uname -a && lsb_release -a",
    "network info": "ip addr show && echo '---' && ip route",
    "kill process": "pkill -f PROCESS_NAME  # or: kill -9 PID",
    "compress folder": "tar -czvf archive.tar.gz FOLDER/",
    "extract archive": "tar -xzvf archive.tar.gz",
    "file permissions": "chmod 755 FILE  # rwxr-xr-x",
    "change owner": "chown user:group FILE",
    "cron jobs": "crontab -l  # list | crontab -e  # edit",
}


def get_quick_suggestion(query: str) -> str | None:
    """Get a quick suggestion without calling the API."""
    query_lower = query.lower()
    for key, command in QUICK_SUGGESTIONS.items():
        if key in query_lower or all(word in query_lower for word in key.split()):
            return command
    return None
