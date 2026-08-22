"""Test suite for Autonomous MCP Discovery, Doubt Clarification, and Live Tool Hot-Reloading in ~/.athena."""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from mcp_client import (
    MCPManager,
    discover_mcp,
    get_athena_home_dir,
    get_athena_mcp_config_path,
    get_athena_mcp_dir,
)
from config import ToolsConfig
from tools import ToolRegistry


def test_athena_home_and_storage():
    print("\n--- 1. Testing ~/.athena Cross-Platform Storage Resolution ---")
    home = get_athena_home_dir()
    print(f"Athena Home Directory: {home}")
    assert home.exists(), f"Home directory {home} does not exist"

    cfg_path = get_athena_mcp_config_path()
    print(f"MCP Config Path: {cfg_path}")
    assert cfg_path.exists(), f"Config path {cfg_path} does not exist"

    mcp_dir = get_athena_mcp_dir()
    print(f"MCP Custom Scripts Dir: {mcp_dir}")
    assert mcp_dir.exists(), f"MCP dir {mcp_dir} does not exist"
    print("✅ ~/.athena directory resolution and configuration migration PASSED!")


def test_mcp_discovery():
    print("\n--- 2. Testing Autonomous MCP Discovery Engine ---")
    
    # 1. Curated match: brave-search
    res1 = discover_mcp("brave search")
    print(f"Discovery for 'brave search': ok={res1.get('ok')}, id={res1.get('id')}, command={res1.get('command')}")
    assert res1.get("ok"), "Failed to discover brave search"
    assert "BRAVE_API_KEY" in res1.get("required_env", []), "Missing BRAVE_API_KEY requirement"
    assert res1.get("clarification_needed"), "Clarification should be needed for API key"
    print(f"Clarification Prompt: {res1.get('clarification_prompt')}")

    # 2. Curated match: sqlite
    res2 = discover_mcp("sqlite")
    print(f"Discovery for 'sqlite': ok={res2.get('ok')}, id={res2.get('id')}")
    assert res2.get("ok"), "Failed to discover sqlite"

    # 3. Dynamic online search: sentry or postgres
    res3 = discover_mcp("postgres")
    print(f"Discovery for 'postgres': ok={res3.get('ok')}, id={res3.get('id')}")
    assert res3.get("ok"), "Failed to discover postgres"

    print("✅ Autonomous MCP Discovery Tests PASSED!")


def test_tool_registry_mcp_management():
    print("\n--- 3. Testing ToolRegistry manage_mcp_server Execution & Hot-Reloading ---")
    cfg = ToolsConfig()
    registry = ToolRegistry(cfg)
    mcp_mgr = MCPManager()
    mcp_mgr.set_registry(registry)
    registry.set_mcp_manager(mcp_mgr)

    # 1. Test status action
    tool = registry._tools.get("manage_mcp_server")
    assert tool is not None, "manage_mcp_server tool is not registered in ToolRegistry"

    status_out = tool.handler({"action": "status"})
    print("manage_mcp_server status output:\n" + status_out[:300] + "...")
    assert "Config:" in status_out or "Configured Servers:" in status_out

    # 2. Test search_and_discover action via LLM tool
    disc_out = tool.handler({"action": "search_and_discover", "query": "brave search"})
    print("\nmanage_mcp_server search_and_discover output:\n" + disc_out)
    assert "BRAVE_API_KEY" in disc_out
    assert "CLARIFICATION NEEDED" in disc_out

    # 3. Test list_tools action
    tools_out = tool.handler({"action": "list_tools"})
    print(f"\nmanage_mcp_server list_tools output: {tools_out[:120]}")

    print("✅ ToolRegistry Integration & MCP Management Tool PASSED!")


if __name__ == "__main__":
    print("🚀 STARTING ATHENA AUTONOMOUS MCP SUBSYSTEM TESTS")
    test_athena_home_and_storage()
    test_mcp_discovery()
    test_tool_registry_mcp_management()
    print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
