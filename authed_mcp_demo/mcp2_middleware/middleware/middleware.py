import logging
import sys
import os
import asyncio
from typing import Dict, Any, Optional
import threading
import time

from mcp.server.fastmcp import FastMCP, Context
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)  # Use stderr since stdout is for stdio transport
    ]
)
logger = logging.getLogger("middleware")

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("1password-bridge")

# Global variables for 1Password client and session
op_client = None
op_session = None
is_initialized = False
init_error = None

def init_op_client_sync():
    """Initialize the 1Password client synchronously before starting the MCP server"""
    global op_client, op_session, is_initialized, init_error
    
    try:
        # Import required modules
        from authed import Authed
        from authed_mcp import AuthedMCPClient
        
        # Configuration
        server_url = os.getenv("MCP1_SERVER_URL", "http://localhost:8080")
        server_agent_id = os.getenv("MCP1_SERVER_AGENT_ID")
        
        # Initialize Authed
        logger.info("Initializing Authed client...")
        authed_client = Authed.from_env()
        
        # Initialize MCP client
        logger.info("Initializing AuthedMCPClient...")
        mcp_client = AuthedMCPClient(
            registry_url=os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev"),
            agent_id=os.getenv("AUTHED_AGENT_ID"),
            agent_secret=os.getenv("AUTHED_AGENT_SECRET"),
            private_key=os.getenv("AUTHED_PRIVATE_KEY")
        )
        
        # Create a new event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Connect to 1Password MCP server
        logger.info(f"Connecting to 1Password MCP server at {server_url}...")
        op_session = loop.run_until_complete(
            mcp_client.connect_and_execute(
                server_url=server_url,
                server_agent_id=server_agent_id,
                operation=lambda session: session
            )
        )
        
        # Test connection
        tools = loop.run_until_complete(op_session.list_tools())
        logger.info(f"Successfully connected to 1Password. Available tools: {tools}")
        
        # Store client for later use
        op_client = mcp_client
        
        # Close the event loop
        loop.close()
        
        is_initialized = True
        logger.info("1Password initialization complete")
        
    except Exception as e:
        init_error = str(e)
        logger.error(f"Error connecting to 1Password MCP server: {str(e)}")
        logger.error("1Password integration disabled. Only local tools will be available.")
    finally:
        is_initialized = True

@mcp.tool()
async def test_tool() -> Dict[str, Any]:
    """Test tool to verify server functionality"""
    logger.info("Test tool called!")
    
    if not is_initialized:
        return {
            "status": "Server is initializing...",
            "connection": "Not yet connected to 1Password server"
        }
    
    if op_session:
        return {
            "status": "Server is working!",
            "connection": "Connected to 1Password server"
        }
    else:
        return {
            "status": "Server is working!",
            "connection": f"Not connected to 1Password server: {init_error}"
        }

@mcp.tool()
async def onepassword_list_vaults() -> Dict[str, Any]:
    """List all available 1Password vaults"""
    if not op_session:
        return {"error": "Not connected to 1Password server"}
    
    try:
        response = await op_session.call_tool("onepassword_list_vaults", {})
        return response
    except Exception as e:
        logger.error(f"Error listing vaults: {str(e)}")
        return {"error": str(e)}

@mcp.tool()
async def onepassword_list_items(vault_id: str) -> Dict[str, Any]:
    """List all items in a 1Password vault"""
    if not op_session:
        return {"error": "Not connected to 1Password server"}
    
    try:
        response = await op_session.call_tool("onepassword_list_items", {
            "vault_id": vault_id
        })
        return response
    except Exception as e:
        logger.error(f"Error listing items: {str(e)}")
        return {"error": str(e)}

@mcp.tool()
async def onepassword_get_secret(vault_id: str, item_id: str, field_name: Optional[str] = None) -> Dict[str, Any]:
    """Get a secret from 1Password"""
    if not op_session:
        return {"error": "Not connected to 1Password server"}
    
    try:
        response = await op_session.call_tool("onepassword_get_secret", {
            "vault_id": vault_id,
            "item_id": item_id,
            "field_name": field_name
        })
        return response
    except Exception as e:
        logger.error(f"Error getting secret: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    # First initialize the 1Password client
    init_thread = threading.Thread(target=init_op_client_sync)
    init_thread.daemon = True
    init_thread.start()
    
    # Wait for initialization to complete or timeout
    init_thread.join(timeout=10)  # Wait up to 10 seconds
    
    # Run the MCP server
    logger.info("Starting middleware server with stdio transport...")
    mcp.run(transport='stdio')
