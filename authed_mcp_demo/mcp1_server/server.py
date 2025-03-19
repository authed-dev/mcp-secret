import asyncio
import os
import logging
from dotenv import load_dotenv

# Import from the correct modules
from authed import Authed
from authed.cli.commands.keys import generate_keypair
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
        
        # Run the server
        logger.info("Starting 1Password MCP server with Authed authentication...")
        run_server(server, host="0.0.0.0", port=8000)
        
        return server
        
    except Exception as e:
        logger.error(f"Error running server: {str(e)}")
        logger.exception(e)
        return None

if __name__ == "__main__":
    main()
