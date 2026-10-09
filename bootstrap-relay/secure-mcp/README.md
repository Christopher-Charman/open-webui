# PowerPC Secure MCP bootstrap

This installer binds OpenAI's official Secure MCP Tunnel client directly to the existing PowerPC stdio MCP:

`<POWERPC_WEBAPP_ROOT>/bin/local-mcp`

It does not expose the MCP server publicly and does not create a second local MCP.

The script verifies the PowerPC UID, runs the existing MCP smoke test when available, downloads the latest official `openai/tunnel-client` Linux amd64 release, verifies the archive against the release checksum manifest, and prepares the local tunnel profile.

A tunnel ID is an OpenAI Platform control-plane object. If it is not already stored locally at `.secure-mcp-tunnel/tunnel_id`, the installer stops cleanly at that human/control-plane boundary instead of weakening the architecture.
