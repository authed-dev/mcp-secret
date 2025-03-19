import asyncio
import os
import logging
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Any, List, Optional

from dotenv import load_dotenv

# Import the actual MCP SDK components
from mcp.server.fastmcp import Context, FastMCP

# Import Authed components
from authed import Authed
from authed_mcp import AuthedMCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("mcp2_middleware")

# Load environment variables
load_dotenv()

# Configuration for 1Password MCP server
MCP1_SERVER_URL = os.getenv("MCP1_SERVER_URL", "http://localhost:8080")
MCP1_SERVER_AGENT_ID = os.getenv("MCP1_SERVER_AGENT_ID")

# Configuration for Authed
AUTHED_REGISTRY_URL = os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev")
AUTHED_AGENT_ID = os.getenv("AUTHED_AGENT_ID")
AUTHED_AGENT_SECRET = os.getenv("AUTHED_AGENT_SECRET")
AUTHED_PRIVATE_KEY = os.getenv("AUTHED_PRIVATE_KEY")

# Global client references
authed_client = None
mcp_client = None
mcp_session = None  # Store the MCP session globally

# Type-safe context for the application
@dataclass
class AppContext:
    authed_client: Authed
    mcp_client: AuthedMCPClient

# Lifespan context manager
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with initialization and cleanup"""
    global authed_client, mcp_client, mcp_session
    
    logger.info("Initializing 1Password MCP Bridge...")
    
    # Initialize Authed client
    # logger.info("Initializing Authed client...")
    # authed_client = Authed.from_env()
    
    # Initialize MCP client
    # logger.info("Initializing AuthedMCPClient...")
    # mcp_client = AuthedMCPClient(
    #     registry_url=AUTHED_REGISTRY_URL,
    #     agent_id=AUTHED_AGENT_ID,
    #     agent_secret=AUTHED_AGENT_SECRET,
    #     private_key=AUTHED_PRIVATE_KEY
    # )
    
    # Create and yield the application context
    context = AppContext(
        authed_client=None,
        mcp_client=None
    )
    
    try:
        # Test connection to 1Password MCP server and establish session
        # try:
        #     logger.info(f"Testing connection to 1Password MCP server at {MCP1_SERVER_URL}...")
        #     # Establish a single SSE connection and session
        #     mcp_session = await mcp_client.connect_and_execute(
        #         server_url=MCP1_SERVER_URL,
        #         server_agent_id=MCP1_SERVER_AGENT_ID,
        #         operation=lambda session: session
        #     )
        #     logger.info(f"Successfully connected to 1Password MCP server")
            
        #     # Test the connection by listing resources
        #     resources = await mcp_session.list_resources()
        #     logger.info(f"Available resources: {resources}")
        # except Exception as e:
        #     logger.error(f"Error connecting to 1Password MCP server: {str(e)}")
        #     logger.error("Please check your configuration and make sure the MCP1 server is running.")
        #     # We continue despite the error to allow the server to start
        #     # The connection might be established later
        
        yield context
    finally:
        # Cleanup resources on shutdown
        logger.info("Shutting down 1Password MCP Bridge...")
        # if mcp_session:
        #     await mcp_session.close()

# Create a FastMCP server with proper name and metadata
mcp = FastMCP(
    "1Password MCP Bridge",
    description="Bridge between standard MCP and Authed-authenticated 1Password MCP server",
    host="0.0.0.0",  # Bind to all interfaces
    port=8000        # Explicit port for Cursor
)

# Add a test tool to verify server functionality
@mcp.tool()
async def test_tool() -> Dict[str, str]:
    """Test tool to verify server functionality"""
    return {"status": "Server is working!"}

# Define resources that mirror the 1Password MCP server
@mcp.resource("op://vaults")
async def list_vaults() -> Dict[str, List[Dict[str, Any]]]:
    """List all available 1Password vaults"""
    logger.info("Processing request to list vaults")
    try:
        # Using global session reference
        global mcp_session
        
        # Use the existing session
        response = await mcp_session.list_resources()
        
        logger.info(f"Successfully retrieved vaults from 1Password MCP server")
        return response
    except Exception as e:
        logger.error(f"Error listing vaults: {str(e)}")
        raise Exception(f"Error listing vaults: {str(e)}")

@mcp.resource("op://vaults/{vault_id}/items")
async def list_items(vault_id: str) -> Dict[str, Any]:
    """List all items in a 1Password vault"""
    logger.info(f"Processing request to list items in vault {vault_id}")
    try:
        # Using global session reference
        global mcp_session
        
        # Use the existing session
        response = await mcp_session.read_resource(f"op://vaults/{vault_id}/items")
        
        logger.info(f"Successfully retrieved items from vault {vault_id}")
        return response
    except Exception as e:
        logger.error(f"Error listing items in vault {vault_id}: {str(e)}")
        raise Exception(f"Error listing items: {str(e)}")

@mcp.resource("op://vaults/{vault_id}/items/{item_id}")
async def get_secret(vault_id: str, item_id: str) -> Dict[str, Any]:
    """Get a secret from 1Password"""
    logger.info(f"Processing request to get secret {item_id} from vault {vault_id}")
    
    try:
        # Using global session reference
        global mcp_session
        
        # Use the existing session
        response = await mcp_session.read_resource(f"op://vaults/{vault_id}/items/{item_id}")
        
        logger.info(f"Successfully retrieved secret {item_id} from vault {vault_id}")
        return response
    except Exception as e:
        logger.error(f"Error getting secret: {str(e)}")
        raise Exception(f"Error getting secret: {str(e)}")

# Define tools that mirror the 1Password MCP server's tools
@mcp.tool()
async def onepassword_get_secret(ctx: Context, vault_id: str, item_id: str, field_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve a secret from 1Password
    
    Args:
        vault_id: ID or name of the vault containing the secret
        item_id: ID or title of the item containing the secret
        field_name: Optional name of the field to retrieve
    """
    logger.info(f"Processing tool call to get secret {item_id} from vault {vault_id}")
    try:
        # Using global session reference
        global mcp_session
        
        # Use the existing session
        response = await mcp_session.call_tool("onepassword_get_secret", {
            "vault_id": vault_id,
            "item_id": item_id,
            "field_name": field_name
        })
        
        logger.info(f"Successfully retrieved secret using tool")
        return response
    except Exception as e:
        logger.error(f"Error with onepassword_get_secret tool: {str(e)}")
        return {"error": str(e)}

@mcp.tool()
async def onepassword_list_vaults(ctx: Context) -> Dict[str, Any]:
    """List all available 1Password vaults"""
    logger.info("Processing tool call to list vaults")
    try:
        # Using global session reference
        global mcp_session
        
        # Use the existing session
        response = await mcp_session.call_tool("onepassword_list_vaults", {})
        
        logger.info("Successfully retrieved vaults using tool")
        return response
    except Exception as e:
        logger.error(f"Error with onepassword_list_vaults tool: {str(e)}")
        return {"error": str(e)}

@mcp.tool()
async def onepassword_list_items(ctx: Context, vault_id: str) -> Dict[str, Any]:
    """
    List all items in a 1Password vault
    
    Args:
        vault_id: ID or name of the vault to list items from
    """
    logger.info(f"Processing tool call to list items in vault {vault_id}")
    try:
        # Using global session reference
        global mcp_session
        
        # Use the existing session
        response = await mcp_session.call_tool("onepassword_list_items", {
            "vault_id": vault_id
        })
        
        logger.info(f"Successfully retrieved items using tool")
        return response
    except Exception as e:
        logger.error(f"Error with onepassword_list_items tool: {str(e)}")
        return {"error": str(e)}

# Main function
def main():
    """Run the 1Password MCP Bridge server"""
    # Start the MCP server
    logger.info("Starting 1Password MCP Bridge server...")
    mcp.run(transport="sse")

if __name__ == "__main__":
    main()
