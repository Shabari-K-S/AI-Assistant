#!/usr/bin/env python3
"""Dummy MCP (Model Context Protocol) Server for S.A.R.A.

Implements the official Model Context Protocol (2024-11-05 spec) over stdio JSON-RPC 2.0.
Exposes demo tools for weather, safe math calculation, dice rolling, and server diagnostics.
"""

import ast
import json
import math
import operator
import random
import sys
import time

SERVER_NAME = "dummy-mcp-demo"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"
START_TIME = time.time()

_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pow": pow,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
}

_SAFE_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


def _eval_ast(node: ast.AST) -> float | int:
    """Recursively evaluate allowed mathematical AST nodes."""
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")
    if isinstance(node, ast.Name):
        if node.id in _SAFE_CONSTANTS:
            return _SAFE_CONSTANTS[node.id]
        raise ValueError(f"Unknown identifier '{node.id}'")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        if op_type is ast.Pow and abs(right) > 1000:
            raise ValueError("Exponent too large (capped at 1000 for safety)")
        return _SAFE_OPERATORS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _eval_ast(node.operand)
        return _SAFE_OPERATORS[op_type](operand)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCTIONS:
            func = _SAFE_FUNCTIONS[node.func.id]
            args = [_eval_ast(arg) for arg in node.args]
            return func(*args)
        raise ValueError(f"Unsupported function '{getattr(node.func, 'id', 'unknown')}'")
    raise ValueError(f"Unsupported syntax: {type(node).__name__}")


def handle_calculate(args: dict) -> str:
    expr = str(args.get("expression", "")).strip()
    if not expr:
        return "Error: Expression cannot be empty."

    try:
        parsed = ast.parse(expr, mode="eval")
        result = _eval_ast(parsed)
        return f"Calculation (via MCP): {expr} = {result}"
    except Exception as e:
        return f"Error evaluating '{expr}': {e}"

TOOLS = [
    {
        "name": "mcp_get_weather",
        "description": "Fetch simulated real-time weather and forecast data for any city worldwide via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City or location name (e.g., 'Tokyo', 'London', 'New York', 'Paris')",
                }
            },
            "required": ["city"],
        },
    },
    {
        "name": "mcp_calculate",
        "description": "Safely evaluate a mathematical expression using MCP (supports +, -, *, /, **, sqrt, sin, cos, pi).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical formula to compute, e.g., '125 * 8.4', 'sqrt(144) + 10', '2**16'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "mcp_dice_roll",
        "description": "Roll tabletop gaming dice with NdS format (e.g., 2d6, 1d20, 3d10) via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sides": {
                    "type": "integer",
                    "description": "Number of sides per die (default 6, common: 4, 6, 8, 10, 12, 20, 100)",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of dice to roll (1 to 20, default 1)",
                },
            },
        },
    },
    {
        "name": "mcp_server_info",
        "description": "Retrieve diagnostic status and capabilities of the connected MCP server.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def handle_get_weather(args: dict) -> str:
    city = str(args.get("city", "Unknown")).strip().title()
    # Deterministic yet diverse pseudo-weather based on city name hash
    seed = sum(ord(c) for c in city)
    random.seed(seed + int(time.time() // 3600))
    conditions = ["Sunny", "Partly Cloudy", "Cloudy", "Light Rain", "Clear Skies", "Breezy", "Scattered Showers"]
    cond = random.choice(conditions)
    temp_c = random.randint(12, 32)
    temp_f = int(temp_c * 9 / 5 + 32)
    humidity = random.randint(35, 85)
    wind_speed = random.randint(4, 22)
    wind_dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    wind_dir = random.choice(wind_dirs)
    return (
        f"Weather for {city} (via MCP):\n"
        f"• Condition: {cond}\n"
        f"• Temperature: {temp_c}°C ({temp_f}°F)\n"
        f"• Humidity: {humidity}%\n"
        f"• Wind: {wind_speed} km/h {wind_dir}\n"
        f"• Forecast: Stable conditions expected over the next 12 hours."
    )


def handle_dice_roll(args: dict) -> str:
    sides = int(args.get("sides", 6) or 6)
    count = int(args.get("count", 1) or 1)
    sides = max(2, min(1000, sides))
    count = max(1, min(20, count))

    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls)
    return f"Dice Roll {count}d{sides} (via MCP):\n• Rolls: {rolls}\n• Total Sum: {total}"


def handle_server_info(args: dict) -> str:
    del args
    uptime = int(time.time() - START_TIME)
    return (
        f"MCP Server Diagnostics:\n"
        f"• Server Name: {SERVER_NAME}\n"
        f"• Server Version: {SERVER_VERSION}\n"
        f"• Protocol Version: {PROTOCOL_VERSION}\n"
        f"• Transport: stdio (JSON-RPC 2.0)\n"
        f"• Active Tools: {len(TOOLS)} ({', '.join(t['name'] for t in TOOLS)})\n"
        f"• Server Uptime: {uptime} seconds"
    )


TOOL_HANDLERS = {
    "mcp_get_weather": handle_get_weather,
    "mcp_calculate": handle_calculate,
    "mcp_dice_roll": handle_dice_roll,
    "mcp_server_info": handle_server_info,
}


def send_response(response: dict) -> None:
    line = json.dumps(response)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def main() -> None:
    """Main JSON-RPC stdio loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method")
        req_id = req.get("id")

        if method == "initialize":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {
                            "listChanged": False,
                        }
                    },
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                },
            })
        elif method == "notifications/initialized":
            # Client notification — no response needed
            pass
        elif method == "ping":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {},
            })
        elif method == "tools/list":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": TOOLS,
                },
            })
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            handler = TOOL_HANDLERS.get(tool_name)
            if handler:
                try:
                    text_result = handler(tool_args)
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": text_result,
                                }
                            ],
                            "isError": False,
                        },
                    })
                except Exception as err:
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Error executing tool {tool_name}: {err}",
                                }
                            ],
                            "isError": True,
                        },
                    })
            else:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool '{tool_name}' not found",
                    },
                })
        elif req_id is not None:
            # Unknown method
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not supported",
                },
            })


if __name__ == "__main__":
    main()
