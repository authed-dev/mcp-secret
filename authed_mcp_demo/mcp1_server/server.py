import asyncio
import os
from dotenv import load_dotenv

# Import from our local implementation instead
from authed import Authed
from authed_mcp import AuthedMCPServer
from .op_client import OnePasswordClient
from authed.cli.commands.keys import generate_keypair

# Load environment variables
load_dotenv()

# Initialize 1Password client
op_client = OnePasswordClient()

async def main():
    # Initialize Authed client
    registry_url = os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev")
    agent_id = os.getenv("AUTHED_AGENT_ID")
    agent_secret = os.getenv("AUTHED_AGENT_SECRET")
    private_key = os.getenv("AUTHED_PRIVATE_KEY")
    public_key = os.getenv("AUTHED_PUBLIC_KEY")
    
    # Create MCP server with Authed authentication
    server = AuthedMCPServer(
        name="1password-secrets-server",
        registry_url=registry_url,
        agent_id=agent_id,
        agent_secret=agent_secret,
        private_key=private_key,
        public_key=public_key
    )
    
    # Initialize 1Password client
    await op_client.connect()
    
    # Register MCP resources
    
    @server.resource("/1password/vaults")
    async def list_vaults_resource():
        """List all available 1Password vaults"""
        try:
            vaults = await op_client.list_vaults()
            return {"vaults": vaults}, "application/json"
        except Exception as e:
            return {"error": str(e)}, "application/json", 500

    @server.resource("/1password/vaults/{vault_id}/items")
    async def list_items_resource(vault_id: str):
        """List all items in a 1Password vault"""
        try:
            items = await op_client.list_items(vault_id)
            return {"items": items}, "application/json"
        except Exception as e:
            return {"error": str(e)}, "application/json", 500

    @server.resource("/1password/vaults/{vault_id}/items/{item_id}")
    async def get_secret_resource(vault_id: str, item_id: str, field: str = None):
        """Get a secret from 1Password"""
        try:
            secret = await op_client.get_secret(vault_id, item_id, field)
            return {"secret": secret}, "application/json"
        except Exception as e:
            return {"error": str(e)}, "application/json", 500
    
    # Register MCP tools
    
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
            return {"error": str(e)}

    @server.tool("onepassword_list_vaults")
    async def list_vaults_tool():
        """List all available 1Password vaults"""
        try:
            vaults = await op_client.list_vaults()
            return {"vaults": vaults}
        except Exception as e:
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
            return {"error": str(e)}
    
    # Register the server
    await register_server_if_needed()
    
    # Run the server
    print("Starting 1Password MCP server with Authed authentication...")
    await server.run(host="0.0.0.0", port=8000)

# Register server as an Authed agent if not already registered
async def register_server_if_needed():
    """Register this server as an Authed agent if not already registered"""
    try:
        # Check if we already have agent credentials
        agent_id = os.getenv("AUTHED_AGENT_ID")
        if agent_id:
            print(f"Server already registered with agent ID: {agent_id}")
            return
        
        # Initialize Authed client
        authed = Authed.from_env()
        
        # Generate keys
        private_key, public_key = generate_keypair()
        
        # Register agent
        agent = await authed.register_agent(
            name="1Password MCP Server",
            description="MCP server with 1Password integration and Authed authentication",
            capabilities={
                "mcp": ["list_resources", "get_resource", "list_tools", "call_tool"]
            },
            public_key=public_key
        )
        
        # Print registration info
        print(f"Server registered with agent ID: {agent.id}")
        print("Update your .env file with the following variables:")
        print(f"AUTHED_AGENT_ID={agent.id}")
        print(f"AUTHED_AGENT_SECRET={agent.secret}")
        print(f"AUTHED_PRIVATE_KEY={private_key}")
        print(f"AUTHED_PUBLIC_KEY={public_key}")
    except Exception as e:
        print(f"Error registering server: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
