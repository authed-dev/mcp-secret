import asyncio
import logging
from dotenv import load_dotenv

from authed_mcp.server import create_server, run_server
from op_client import OnePasswordClient  # Simple import from the same directory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize 1Password client
op_client = OnePasswordClient()

def debug_check_tools(server):
    """Check if tools are properly registered with the MCP server."""
    # Get the internal MCP server object
    mcp_server = server.mcp._mcp_server
    
    # Get the FastMCP tool manager
    tool_manager = server.mcp._tool_manager
    
    # Check for registered tools
    tools = tool_manager.list_tools()
    
    if tools:
        logger.info(f"Found {len(tools)} tools registered with tool manager:")
        for tool in tools:
            logger.info(f"- {tool.name}: {tool.description}")
    else:
        logger.warning("No tools found in tool manager!")
    
    # DIRECT PATCHING: This is a more aggressive approach to ensure tools are advertised
    
    # 1. Patch the create_initialization_options method
    orig_init_fn = mcp_server.create_initialization_options
    
    def patched_init():
        options = orig_init_fn()
        logger.info("PATCHED INIT FUNCTION CALLED!")
        
        # Directly modify the capabilities
        if hasattr(options, 'capabilities'):
            caps = options.capabilities
            if hasattr(caps, 'tools') and hasattr(caps.tools, 'listChanged'):
                logger.info("Setting tools.listChanged = True (object attribute)")
                caps.tools.listChanged = True
            
            if hasattr(caps, 'resources') and hasattr(caps.resources, 'listChanged'):
                logger.info("Setting resources.listChanged = True (object attribute)")
                caps.resources.listChanged = True
                
            if hasattr(caps, 'prompts') and hasattr(caps.prompts, 'listChanged'):
                logger.info("Setting prompts.listChanged = True (object attribute)")
                caps.prompts.listChanged = True
                
        # Log the modified options
        logger.info(f"PATCHED initialization options: {options}")
        return options
    
    # Replace the function with our patched version
    mcp_server.create_initialization_options = patched_init
    logger.info("Server initialization function has been patched")
    
    # Force immediate test of our patched function
    test_options = mcp_server.create_initialization_options()
    logger.info(f"Test of patched initialization options: {test_options}")
    
    # 2. Try to access and modify the internal state directly
    # This is a more aggressive approach as we're trying to modify internal state
    for attr_name in dir(mcp_server):
        # Look for capabilities-related attributes
        if 'capab' in attr_name.lower() and not attr_name.startswith('__'):
            logger.info(f"Found potential capabilities attribute: {attr_name}")
            attr_value = getattr(mcp_server, attr_name, None)
            logger.info(f"Value: {attr_value}")
            
            # Try to modify it if it looks promising
            if attr_value and hasattr(attr_value, 'tools'):
                logger.info(f"Attempting to modify {attr_name}.tools.listChanged")
                if hasattr(attr_value.tools, 'listChanged'):
                    attr_value.tools.listChanged = True
                    logger.info(f"Modified {attr_name}.tools.listChanged to True")
    
    return tools

def main():
    """Run the 1Password MCP server with Authed authentication."""
    try:
        # Initialize 1Password client using a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Connect to 1Password
        loop.run_until_complete(op_client.connect())
        logger.info("Connected to 1Password")
        
        # Create the server with values from environment variables
        server = create_server(name="1password-secrets-server")
        logger.info("Server created successfully")
        
        # Register 1Password resources
        @server.resource("op://vaults")
        async def list_vaults_resource():
            """List all available 1Password vaults"""
            try:
                vaults = await op_client.list_vaults()
                return {"vaults": vaults}, "application/json"
            except Exception as e:
                logger.error(f"Error listing vaults: {str(e)}")
                return {"error": str(e)}, "application/json", 500

        @server.resource("op://vaults/{vault_id}/items")
        async def list_items_resource(vault_id: str):
            """List all items in a 1Password vault"""
            try:
                items = await op_client.list_items(vault_id)
                return {"items": items}, "application/json"
            except Exception as e:
                logger.error(f"Error listing items: {str(e)}")
                return {"error": str(e)}, "application/json", 500

        @server.resource("op://vaults/{vault_id}/items/{item_id}")
        async def get_secret_resource(vault_id: str, item_id: str):
            """Get a secret from 1Password"""
            try:
                # Get field from query param if present
                field = "credentials"
                secret = await op_client.get_secret(vault_id, item_id, field)
                return {"secret": secret}, "application/json"
            except Exception as e:
                logger.error(f"Error getting secret: {str(e)}")
                return {"error": str(e)}, "application/json", 500
        
        # Register 1Password tools
        @server.tool("onepassword_get_secret")
        async def get_secret_tool(vault_id: str, item_id: str, field_name: str = None):
            """
            Retrieve a secret from 1Password.
            
            Args:
                vault_id (str): ID or name of the vault containing the secret
                item_id (str): ID or title of the item containing the secret
                field_name (str, optional): Name of the field to retrieve
            """
            try:
                secret = await op_client.get_secret(vault_id, item_id, field_name)
                return {"secret": secret}
            except Exception as e:
                logger.error(f"Error with get_secret tool: {str(e)}")
                return {"error": str(e)}

        @server.tool("onepassword_list_vaults")
        async def list_vaults_tool():
            """List all available 1Password vaults"""
            try:
                vaults = await op_client.list_vaults()
                return {"vaults": vaults}
            except Exception as e:
                logger.error(f"Error with list_vaults tool: {str(e)}")
                return {"error": str(e)}

        @server.tool("onepassword_list_items")
        async def list_items_tool(vault_id: str):
            """
            List all items in a 1Password vault.
            
            Args:
                vault_id (str): ID or name of the vault to list items from
            """
            try:
                items = await op_client.list_items(vault_id)
                return {"items": items}
            except Exception as e:
                logger.error(f"Error with list_items tool: {str(e)}")
                return {"error": str(e)}
        

        # ADD THIS HERE - After registering all tools, check if they're properly registered
        logger.info("Checking registered tools...")
        # Access the underlying MCP server to check registered tools
        mcp_server = server.mcp._mcp_server
        registered_tools = mcp_server.list_tools() if hasattr(mcp_server, 'list_tools') else []
        logger.info(f"Tools registered with server: {registered_tools}")
        
        if not registered_tools:
            logger.warning("No tools found in server registry! This will cause client tool calls to fail.")
        
        # Also check registered resources
        registered_resources = mcp_server.list_resources() if hasattr(mcp_server, 'list_resources') else []
        logger.info(f"Resources registered with server: {registered_resources}")
        
        debug_check_tools(server)
        # Run the server
        logger.info("Starting 1Password MCP server with Authed authentication...")
        run_server(server, host="0.0.0.0", port=8080)
        
        return server
        
    except Exception as e:
        logger.error(f"Error running server: {str(e)}")
        logger.exception(e)
        return None

if __name__ == "__main__":
    main()
