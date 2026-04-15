# MiniMax ACP Agent

An ACP (Agent Client Protocol) compatible coding agent powered by **MiniMax-M2.7**, designed for seamless integration with JetBrains IDEs.

## Features

- **Thinking Support**: The agent shows its reasoning process before responding
- **Streaming Responses**: Real-time streaming of responses as they're generated
- **MCP Integration**: Connect to Model Context Protocol servers for extended capabilities
- **File Operations**: Read, write, edit files directly from the IDE
- **Shell Commands**: Execute shell commands with timeout control
- **Pattern Matching**: Glob and grep for finding files and content
- **Session Management**: Persistent conversation sessions

## Requirements

- Python 3.11+
- [mmx-cli](https://github.com/MiniMaxAI/mmx) - MiniMax's official CLI tool
- MiniMax API key

## Installation

### 1. Install mmx-cli

```bash
npm install -g mmx-cli
```

### 2. Authenticate

```bash
mmx auth login --api-key your-api-key
```

### 3. Clone and Setup

```bash
git clone https://github.com/luigivis/minimax-acp-agent.git
cd minimax-acp-agent
```

### 4. Configure JetBrains

Add the following to `~/.jetbrains/acp.json`:

```json
{
  "default_mcp_settings": {
    "use_idea_mcp": true,
    "use_custom_mcp": true
  },
  "agent_servers": {
    "MiniMax ACP Agent": {
      "command": "/path/to/minimax-acp-agent/launcher.sh",
      "args": [],
      "env": {}
    }
  }
}
```

### 5. Using the Agent

1. Open a JetBrains IDE (IntelliJ IDEA, PyCharm, WebStorm, etc.)
2. Go to **AI Chat** tool window
3. Click **Add Custom Agent**
4. Select **MiniMax ACP Agent**
5. Start chatting!

## Available Tools

### Local Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read contents of a file |
| `write_file` | Create or overwrite files |
| `edit_file` | Edit files using regex replacement |
| `run_shell` | Execute shell commands |
| `list_directory` | List directory contents |
| `glob` | Find files matching glob patterns |
| `grep` | Search for patterns in files |

### MCP Servers

You can configure MCP servers via the `MINIMAX_ACP_MCP_CONFIG` environment variable:

```json
{
  "server_name": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/directory"],
    "env": {},
    "enabled": true
  }
}
```

## Architecture

```
┌─────────────────┐
│  JetBrains IDE  │
│   (ACP Client) │
└────────┬────────┘
         │ JSON-RPC (stdio)
         ▼
┌─────────────────┐
│ MiniMax ACP     │
│ Agent           │
├─────────────────┤
│ - Session Mgmt  │
│ - Tool Executor │
│ - MCP Bridge    │
└────────┬────────┘
         │ mmx-cli
         ▼
┌─────────────────┐
│  MiniMax API    │
│  (M2.7 Model)   │
└─────────────────┘
```

## Protocol

This agent implements the [Agent Client Protocol (ACP)](https://agentclientprotocol.com/), a standard protocol for communication between IDEs and coding agents developed by JetBrains and Zed.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MINIMAX_API_KEY` | Your MiniMax API key (optional if authenticated via `mmx auth`) |
| `MINIMAX_ACP_MCP_CONFIG` | JSON configuration for MCP servers |

## Development

```bash
# Run the agent directly
python3 src/agent.py

# Test with JSON-RPC
echo '{"jsonrpc":"2.0","method":"initialize","id":1}' | python3 src/agent.py
```

## Author

**Luigi Vismara**  
Email: [luigivis98@gmail.com](mailto:luigivis98@gmail.com)

## License

MIT License

## Acknowledgments

- [MiniMax](https://minimax.io/) - For the powerful M2.7 model
- [Agent Client Protocol](https://agentclientprotocol.com/) - For the open protocol standard
- [JetBrains](https://jetbrains.com/) - For IDE integration
