# weather_server.py
from mcp.server.fastmcp import FastMCP
from typing_extensions import Annotated
from typing import List, Optional, Union
# from src.tools.mcp.command_execution import command_execution
import subprocess

CONTAINER_NAME = "attacker"
mcp = FastMCP("reconnaissance", port=3001)
from _exec import exec_command  # dual-mode kali/local execution backend

def command_execution(command: Annotated[str, "Commands to run on Kali Linux"]) -> Annotated[str, "Command Execution Result"]:
    """
    Run one command at a time in a kali linux environment and return the result.

    Dual-mode (see _exec.py): docker `attacker` container when Docker is up,
    local Git Bash execution otherwise. Full tool parity in both modes.
    """
    try:
        mode, returncode, output = exec_command(command)
        if returncode != 0 and not output.startswith("[-]"):
            return f"[-] Command execution error (exit {returncode}, mode {mode}): {output}"
        return output
    except Exception as e:
        return f"[-] Error: {str(e)} (Type: {type(e).__name__})"

# MCP 도구 정의
@mcp.tool(description="Network discovery and port scanning")
def nmap(target: str, options: Optional[Union[str, List[str]]] = None) -> Annotated[str, "command execution Result"]:
    if options is None:
        args_str = ""
    elif isinstance(options, list):
        args_str = " ".join(options)
    else:
        args_str = options
    command = f'nmap {args_str} {target}'
    return command_execution(command)

@mcp.tool(description="Web service analysis and content retrieval")
def curl(target: str = "", options: str = "") -> Annotated[str, "command execution Result"]:
    command = f'curl {options} {target}'
    return command_execution(command)

@mcp.tool(description="DNS information gathering")
def dig(target: str, options: str = "") -> Annotated[str, "command execution Result"]:
    command = f'dig {options} {target}'
    return command_execution(command)

@mcp.tool(description="Domain registration and ownership lookup")
def whois(target: str, options: str = "") -> Annotated[str, "command execution Result"]:
    command = f'whois {options} {target}'
    return command_execution(command)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")