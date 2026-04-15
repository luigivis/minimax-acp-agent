#!/usr/bin/env python3
"""
MiniMax ACP Agent - An ACP-compatible agent with MiniMax-M2.7 backend.
Designed for integration with JetBrains IDEs via Agent Client Protocol.
"""

import json
import sys
import subprocess
import os
import uuid
import asyncio
import re
from typing import Any, AsyncIterator, Optional

TOOLS = {
    "read_file": {
        "name": "read_file",
        "description": "Read contents of a file from the filesystem",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to read",
                }
            },
            "required": ["path"],
        },
    },
    "write_file": {
        "name": "write_file",
        "description": "Write content to a file, creating it if it doesn't exist",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    },
    "edit_file": {
        "name": "edit_file",
        "description": "Edit a specific part of a file using regex replacement",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to edit",
                },
                "old": {
                    "type": "string",
                    "description": "Regex pattern to match in the file",
                },
                "new": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old", "new"],
        },
    },
    "run_shell": {
        "name": "run_shell",
        "description": "Execute a shell command and return its output",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
    },
    "list_directory": {
        "name": "list_directory",
        "description": "List files and directories at a given path",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list",
                    "default": ".",
                }
            },
        },
    },
    "glob": {
        "name": "glob",
        "description": "Find files matching a glob pattern",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., **/*.py)",
                },
                "root": {
                    "type": "string",
                    "description": "Root directory to search from",
                    "default": ".",
                },
            },
            "required": ["pattern"],
        },
    },
    "grep": {
        "name": "grep",
        "description": "Search for text patterns in files",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in",
                    "default": ".",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Search recursively",
                    "default": False,
                },
            },
            "required": ["pattern"],
        },
    },
}


class MiniMaxClient:
    def __init__(self):
        self.api_key: Optional[str] = None

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        cmd = ["mmx", "text", "chat", "--output", "json"]

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                text_content = " ".join(
                    c.get("text", "") for c in content if c.get("type") == "text"
                )
            else:
                text_content = str(content).replace("\n", " ").strip()
            cmd.extend(["--message", f"{role}:{text_content}"])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
            response = json.loads(result.stdout)
            content = response.get("content", [])
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "thinking":
                        text_parts.append(f"[Thinking: {item.get('thinking', '')}]")
                return "\n".join(text_parts)
            return str(content)
        except subprocess.TimeoutExpired:
            return "Error: Request timed out"
        except json.JSONDecodeError as e:
            return f"Error: Invalid response from mmx: {e}"
        except subprocess.CalledProcessError as e:
            return f"Error: mmx failed: {e.stderr}"
        except Exception as e:
            return f"Error: {str(e)}"


class MCPServer:
    def __init__(
        self, name: str, command: str, args: list[str] = None, env: dict = None
    ):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0

    async def start(self):
        cmd = [self.command] + self.args
        full_env = os.environ.copy()
        full_env.update(self.env)

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )

        init_result = await self._send_request(
            "initialize",
            {
                "protocol_version": "2024-11-05",
                "capabilities": {},
                "client_info": {"name": "minimax-acp-agent", "version": "1.0.0"},
            },
        )

        return init_result

    async def _send_request(self, method: str, params: dict) -> dict:
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params,
        }

        if self.process and self.process.stdin:
            self.process.stdin.write(json.dumps(request).encode() + b"\n")
            await self.process.stdin.drain()

            if self.process.stdout:
                line = await self.process.stdout.readline()
                if line:
                    response = json.loads(line.decode("utf-8"))
                    return response.get("result", {})

        return {}

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        result = await self._send_request(
            "tools/call", {"name": tool_name, "arguments": arguments}
        )
        return result

    async def list_tools(self) -> list[dict]:
        result = await self._send_request("tools/list", {})
        return result.get("tools", [])

    async def stop(self):
        if self.process:
            self.process.terminate()
            await self.process.wait()


class MiniMaxACPAgent:
    def __init__(self):
        self.client = MiniMaxClient()
        self.sessions: dict[str, list[dict]] = {}
        self.protocol_version = 1
        self.mcp_servers: dict[str, MCPServer] = {}
        self._mcp_tools: dict[str, dict] = {}

    def _build_system_prompt(self) -> str:
        return """You are MiniMax-Coder, an expert coding assistant powered by MiniMax-M2.7.

You have access to tools for filesystem operations, shell commands, and MCP servers.

Available local tools:
- read_file: Read file contents
- write_file: Create or overwrite files with content
- edit_file: Edit file using regex replacement (path, old, new)
- run_shell: Execute shell commands
- list_directory: List directory contents
- glob: Find files matching glob patterns
- grep: Search for patterns in files

You may also have access to MCP servers that provide additional capabilities.

Always:
- Write clean, well-documented code
- Explain your reasoning when making significant changes
- Use tools efficiently to accomplish tasks
- Ask for clarification if a request is ambiguous

Current working directory is where you were invoked."""

    async def _execute_tool(self, tool_name: str, arguments: dict) -> dict:
        try:
            if tool_name == "read_file":
                path = arguments.get("path", "")
                if not os.path.isabs(path):
                    return {"error": f"Path must be absolute: {path}"}
                with open(path, "r") as f:
                    content = f.read()
                return {"output": content}

            elif tool_name == "write_file":
                path = arguments.get("path", "")
                content = arguments.get("content", "")
                if not os.path.isabs(path):
                    return {"error": f"Path must be absolute: {path}"}
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(content)
                return {"output": f"Successfully wrote to {path}"}

            elif tool_name == "edit_file":
                path = arguments.get("path", "")
                old_pattern = arguments.get("old", "")
                new_content = arguments.get("new", "")
                if not os.path.isabs(path):
                    return {"error": f"Path must be absolute: {path}"}
                with open(path, "r") as f:
                    file_content = f.read()
                new_file_content = re.sub(
                    old_pattern, new_content, file_content, count=1
                )
                if new_file_content == file_content:
                    return {"error": f"Pattern '{old_pattern}' not found in file"}
                with open(path, "w") as f:
                    f.write(new_file_content)
                return {"output": f"Successfully edited {path}"}

            elif tool_name == "run_shell":
                command = arguments.get("command", "")
                timeout = arguments.get("timeout", 30)
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                output = result.stdout if result.stdout else result.stderr
                if result.returncode != 0:
                    return {
                        "error": f"Command failed (exit {result.returncode}): {output}"
                    }
                return {"output": output}

            elif tool_name == "list_directory":
                path = arguments.get("path", ".")
                if not os.path.isabs(path):
                    path = os.path.abspath(path)
                entries = os.listdir(path)
                return {"output": "\n".join(sorted(entries))}

            elif tool_name == "glob":
                import glob as glob_module

                pattern = arguments.get("pattern", "")
                root = arguments.get("root", ".")
                if not os.path.isabs(root):
                    root = os.path.abspath(root)
                matches = glob_module.glob(pattern, root_dir=root)
                return {"output": "\n".join(matches)}

            elif tool_name == "grep":
                pattern = arguments.get("pattern", "")
                path = arguments.get("path", ".")
                recursive = arguments.get("recursive", False)
                if not os.path.isabs(path):
                    path = os.path.abspath(path)
                results = []
                if os.path.isfile(path):
                    with open(path, "r") as f:
                        for i, line in enumerate(f, 1):
                            if re.search(pattern, line):
                                results.append(f"{path}:{i}:{line.rstrip()}")
                elif os.path.isdir(path):
                    for root, dirs, files in os.walk(path):
                        if not recursive and root != path:
                            continue
                        for file in files:
                            filepath = os.path.join(root, file)
                            try:
                                with open(filepath, "r") as f:
                                    for i, line in enumerate(f, 1):
                                        if re.search(pattern, line):
                                            results.append(
                                                f"{filepath}:{i}:{line.rstrip()}"
                                            )
                            except Exception:
                                pass
                return {"output": "\n".join(results) if results else "No matches found"}

            else:
                for server_name, server in self.mcp_servers.items():
                    try:
                        result = await server.call_tool(tool_name, arguments)
                        return result
                    except Exception:
                        pass
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"error": str(e)}

    async def handle_messages_stream(
        self, session_id: str, messages: list[dict]
    ) -> AsyncIterator[dict]:
        if session_id not in self.sessions:
            self.sessions[session_id] = []

        session_messages = self.sessions[session_id]

        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_content = " ".join(
                        c.get("text", "") for c in content if c.get("type") == "text"
                    )
                else:
                    text_content = content
                session_messages.append({"role": "user", "content": text_content})

        messages_for_llm = [
            {"role": "system", "content": self._build_system_prompt()},
        ] + session_messages

        full_response = self.client.chat(messages_for_llm)
        session_messages.append({"role": "assistant", "content": full_response})

        yield {
            "type": "content",
            "content": [{"type": "text", "text": full_response}],
            "done": True,
        }

    def get_capabilities(self) -> dict:
        all_tools = dict(TOOLS)
        for name, server in self.mcp_servers.items():
            all_tools[f"{name}_mcp"] = {
                "name": f"{name}_mcp",
                "description": f"MCP server: {name}",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            }

        return {
            "protocolVersion": self.protocol_version,
            "agentCapabilities": {
                "loadSession": False,
                "mcpCapabilities": {"http": False, "sse": False},
                "promptCapabilities": {
                    "audio": False,
                    "embeddedContext": False,
                    "image": False,
                },
                "sessionCapabilities": {},
            },
            "agentInfo": {
                "name": "MiniMax ACP Agent",
                "version": "1.0.0",
            },
            "authMethods": [],
            "tools": all_tools,
        }


async def setup_mcp_servers(agent: MiniMaxACPAgent, mcp_config: dict):
    for name, config in mcp_config.items():
        if not config.get("enabled", True):
            continue
        cmd = config.get("command", "")
        args = config.get("args", [])
        env = config.get("env", {})
        if not cmd:
            continue

        server = MCPServer(name, cmd, args, env)
        try:
            await server.start()
            agent.mcp_servers[name] = server
            tools = await server.list_tools()
            for tool in tools:
                tool_name = tool.get("name", "")
                if tool_name:
                    agent._mcp_tools[f"{name}.{tool_name}"] = tool
        except Exception as e:
            print(f"Failed to start MCP server {name}: {e}", file=sys.stderr)


async def main():
    agent = MiniMaxACPAgent()

    env_mcp_config = os.environ.get("MINIMAX_ACP_MCP_CONFIG", "")
    if env_mcp_config:
        try:
            mcp_config = json.loads(env_mcp_config)
            await setup_mcp_servers(agent, mcp_config)
        except Exception as e:
            print(f"Failed to parse MCP config: {e}", file=sys.stderr)

    current_session_id = str(uuid.uuid4())

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method")
        msg_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            if "mcp_servers" in params:
                await setup_mcp_servers(agent, params.get("mcp_servers", {}))

            result = agent.get_capabilities()
            response = {"jsonrpc": "2.0", "id": msg_id, "result": result}
            print(json.dumps(response), flush=True)

        elif method == "session/new":
            session_id = str(uuid.uuid4())
            current_session_id = session_id
            if session_id not in agent.sessions:
                agent.sessions[session_id] = []

            result = {
                "sessionId": session_id,
            }
            response = {"jsonrpc": "2.0", "id": msg_id, "result": result}
            print(json.dumps(response), flush=True)

        elif method == "session/prompt":
            session_id = params.get("sessionId", current_session_id)
            if session_id not in agent.sessions:
                agent.sessions[session_id] = []
                current_session_id = session_id
            prompt = params.get("prompt", [])
            messages = []
            for block in prompt:
                if isinstance(block, dict) and block.get("type") == "text":
                    messages.append({"role": "user", "content": block.get("text", "")})

            full_response = ""
            async for block in agent.handle_messages_stream(session_id, messages):
                if block.get("type") == "thinking":
                    notification = {
                        "jsonrpc": "2.0",
                        "method": "session/update",
                        "params": {
                            "sessionId": session_id,
                            "update": {
                                "sessionUpdate": "thinking",
                                "thinking": {
                                    "text": block.get("thinking", ""),
                                },
                            },
                        },
                    }
                    print(json.dumps(notification), flush=True)
                else:
                    content = block.get("content", [])
                    text_content = ""
                    if isinstance(content, list):
                        for item in content:
                            if item.get("type") == "text":
                                text_content += item.get("text", "")
                    elif isinstance(content, str):
                        text_content = content

                    if text_content:
                        notification = {
                            "jsonrpc": "2.0",
                            "method": "session/update",
                            "params": {
                                "sessionId": session_id,
                                "update": {
                                    "sessionUpdate": "message",
                                    "message": {
                                        "role": "assistant",
                                        "content": [
                                            {"type": "text", "text": text_content}
                                        ],
                                    },
                                },
                            },
                        }
                        print(json.dumps(notification), flush=True)
                        full_response += text_content

            final_result = {
                "stopReason": "end_turn",
            }
            response = {"jsonrpc": "2.0", "id": msg_id, "result": final_result}
            print(json.dumps(response), flush=True)

        elif method == "tool_call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            result = await agent._execute_tool(tool_name, arguments)
            response = {"jsonrpc": "2.0", "id": msg_id, "result": result}
            print(json.dumps(response), flush=True)

        elif method == "session/list":
            sessions = [
                {"id": sid, "name": f"Session {sid[:8]}"}
                for sid in agent.sessions.keys()
            ]
            result = {"sessions": sessions}
            response = {"jsonrpc": "2.0", "id": msg_id, "result": result}
            print(json.dumps(response), flush=True)

        elif method == "session/delete":
            session_id = params.get("session_id")
            if session_id in agent.sessions:
                del agent.sessions[session_id]
            response = {"jsonrpc": "2.0", "id": msg_id, "result": {"deleted": True}}
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
