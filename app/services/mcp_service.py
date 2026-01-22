import sys
import json
import inspect
from contextlib import AsyncExitStack
from typing import Any, Awaitable, Callable, ClassVar

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import traceback

class MCPClient:
    """MCP client that fetches tool metadata and stores it as JSON."""

    client_session: ClassVar[ClientSession]

    # Stores final results to send to DeepSeek
    members: dict = {
        "tools": [],
        "prompts": [],
        "resources": []
    }

    def __init__(self, server_path: str):
        self.server_path = server_path
        self.exit_stack = AsyncExitStack()

    async def __aenter__(self):
        type(self).client_session = await self._connect_to_server()
        return self

    async def __aexit__(self, *_) -> None:
        await self.exit_stack.aclose()

    async def _connect_to_server(self) -> ClientSession:
        try:
            read, write = await self.exit_stack.enter_async_context(
                stdio_client(
                    server=StdioServerParameters(
                        command="sh",
                        args=["-c", f"{sys.executable} {self.server_path} 2>/dev/null"],
                        env=None,
                    )
                )
            )

            client_session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )

            await client_session.initialize()
            return client_session

        except Exception:
            raise RuntimeError("Error: Failed to connect to server")

    def clean_schema(self, schema: dict) -> dict:
        """
        Convert MCP / Pydantic JSON schema into
        OpenAI-friendly function schema.
        """
        def resolve_ref(ref: str):
            # ref like "#/$defs/Gender"
            return schema["$defs"][ref.split("/")[-1]]

        def clean(node):
            if isinstance(node, dict):
                # Resolve $ref
                if "$ref" in node:
                    return clean(resolve_ref(node["$ref"]))

                # Convert anyOf [X, null] → X
                if "anyOf" in node:
                    non_null = [x for x in node["anyOf"] if x.get("type") != "null"]
                    return clean(non_null[0]) if non_null else {}

                cleaned = {}
                for k, v in node.items():
                    if k in {"$defs", "title", "default"}:
                        continue
                    cleaned[k] = clean(v)
                return cleaned

            elif isinstance(node, list):
                return [clean(x) for x in node]

            return node

        return clean(schema)

    # ---------- New: Collect data instead of printing ----------
    async def _collect_section(
        self,
        section: str,
        list_method: Callable[[], Awaitable[Any]],
    ):
        try:
            response = await list_method()
            items = getattr(response, section)

            formatted = []

            for item in items:
                cleaned_schema = self.clean_schema(item.inputSchema)
                formatted.append({
                    "name": item.name,
                    "description": inspect.cleandoc(item.description or ""), 
                    "input_schema": cleaned_schema,
                    "output_schema": item.outputSchema if hasattr(item, "outputSchema") else None,
                })

            self.members[section] = formatted

        except Exception as e:
            self.members[section] = {"error": str(e)}

    # ---------- Public method ----------
    async def fetch_all_members(self) -> dict:
        """Fetch all tool/prompt/resource metadata and store in JSON structure."""

        sections = {
            "tools": self.client_session.list_tools,
            "prompts": self.client_session.list_prompts,
            "resources": self.client_session.list_resources,
        }

        # Run sections sequentially (MCP servers often not thread-safe)
        for section, method in sections.items():
            await self._collect_section(section, method)

        return self.members
    
    def get_sections(self, type:str):
        return self.members.get(type, [])

    # ---------- Helper: export JSON string ----------
    def get_json(self, pretty=True) -> str:
        return json.dumps(self.members, indent=2 if pretty else None)
    
    async def call_tool(self, tool_name: str, arguments: dict):
        """
        Call a tool exposed by the MCP server.

        Args:
            tool_name (str): name of the MCP tool
            arguments (dict): parameters to send to the tool

        Returns:
            dict: result from the MCP server
        """
        try:
            result = await self.client_session.call_tool(
                name=tool_name,
                arguments=arguments
            )

            return {
                "success": True,
                "tool": tool_name,
                "input": arguments,
                "output": result.output if hasattr(result, "output") else result,
            }

        except Exception as e:
            return {
                "success": False,
                "tool": tool_name,
                "input": arguments,
                "error": repr(e),
                "traceback": traceback.format_exc(),
                "error": repr(e),
                "traceback": traceback.format_exc(),
            }

    def format_tools_for_llm(self, tools_list: list) -> str:
        """
        Convert list of tool dictionaries into a clear, natural language string 
        for LLM prompts.
        """
        if not tools_list:
            return "No tools available."

        formatted_output = "AVAILABLE FUNCTIONS:\n"
        
        for tool in tools_list:
            name = tool.get("name")
            description = tool.get("description", "").strip()
            input_schema = tool.get("input_schema", {})
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])

            formatted_output += f"Function: {name}\n"
            formatted_output += f"Description: {description}\n"
            formatted_output += "Arguments:\n"

            if not properties:
                formatted_output += "  - None\n"
            
            for arg_name, arg_details in properties.items():
                arg_type = arg_details.get("type", "unknown")
                # Handle Enums
                enum_values = arg_details.get("enum", [])
                
                req_marker = "(REQUIRED)" if arg_name in required else "(Optional)"
                
                formatted_output += f"  - {arg_name} {req_marker}: {arg_type}"
                
                if enum_values:
                    formatted_output += f" [Allowed: {', '.join(map(str, enum_values))}]"
                
                formatted_output += "\n"
        
        return formatted_output

    def format_tool_descriptions_for_llm(self, tools_list: list) -> str:
        """
        Convert list of tool dictionaries into a simple string of names and descriptions.
        Used for the initial tool selection step.
        """
        if not tools_list:
            return "No tools available."

        formatted_output = "AVAILABLE TOOLS:\n"
        for tool in tools_list:
            name = tool.get("name")
            description = tool.get("description", "").strip()
            formatted_output += f"- Function: {name}\n"
            formatted_output += f"  Description: {description}\n\n"
        
        return formatted_output