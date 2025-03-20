import asyncio
import os
import logging
import sys
from typing import Dict, Any

from dotenv import load_dotenv

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
logger = logging.getLogger("authed_client")

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

async def connect_to_1password():
    """Connect to the 1Password MCP server using AuthedMCPClient"""
    global authed_client, mcp_client, mcp_session
    
    logger.info("Initializing 1Password MCP client...")
    
    try:
        # Initialize Authed client
        logger.info("Initializing Authed client...")
        authed_client = Authed.from_env()
        
        # Initialize MCP client
        logger.info("Initializing AuthedMCPClient...")
        mcp_client = AuthedMCPClient(
            registry_url=AUTHED_REGISTRY_URL,
            agent_id=AUTHED_AGENT_ID,
            agent_secret=AUTHED_AGENT_SECRET,
            private_key=AUTHED_PRIVATE_KEY
        )
        
        # Test connection to 1Password MCP server and establish session
        try:
            logger.info(f"Connecting to 1Password MCP server at {MCP1_SERVER_URL}...")
            # Establish a single SSE connection and session
            mcp_session = await mcp_client.connect_and_execute(
                server_url=MCP1_SERVER_URL,
                server_agent_id=MCP1_SERVER_AGENT_ID,
                operation=lambda session: session
            )
            logger.info(f"Successfully connected to 1Password MCP server")
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to 1Password MCP server: {str(e)}")
            logger.error("Please check your configuration and make sure the MCP1 server is running.")
            return False
            
    except Exception as e:
        logger.error(f"Error initializing clients: {str(e)}")
        return False

async def test_list_vaults():
    """Test the onepassword_list_vaults tool"""
    if not mcp_session:
        logger.error("No active session. Cannot list vaults.")
        return
    
    try:
        # Test listing vaults
        logger.info("Testing onepassword_list_vaults...")
        
        # Method 1: Call the tool directly
        logger.info("Method 1: Using tool call...")
        vaults_response = await mcp_session.call_tool("onepassword_list_vaults", {})
        logger.info(f"Vaults response from tool call: {vaults_response}")
        
        # Method 2: Access the resource
        logger.info("Method 2: Using resource...")
        resources = await mcp_session.list_resources()
        logger.info(f"Available resources: {resources}")
        
        resources_response = await mcp_session.read_resource("op://vaults")
        logger.info(f"Vaults response from resource: {resources_response}")
        
        return vaults_response
        
    except Exception as e:
        logger.error(f"Error testing list_vaults: {str(e)}")
        return None

async def test_list_items(vault_id=None):
    """Test the onepassword_list_items tool with the first vault"""
    if not mcp_session:
        logger.error("No active session. Cannot list items.")
        return
    
    try:
        # If no vault_id provided, get the first one from list_vaults
        if not vault_id:
            vaults_response = await test_list_vaults()
            if not vaults_response or "vaults" not in vaults_response or not vaults_response["vaults"]:
                logger.error("No vaults found to list items from")
                return None
            
            vault_id = vaults_response["vaults"][0]["id"]
            
        logger.info(f"Testing onepassword_list_items for vault {vault_id}...")
        items_response = await mcp_session.call_tool("onepassword_list_items", {
            "vault_id": vault_id
        })
        logger.info(f"Items response: {items_response}")
        
        return items_response
        
    except Exception as e:
        logger.error(f"Error listing items: {str(e)}")
        return None

async def main():
    """Main function to run the 1Password MCP client"""
    # Connect to 1Password
    success = await connect_to_1password()
    
    if success:
        logger.info("Connection to 1Password established successfully")
        
        # Test the list_vaults functionality
        await test_list_vaults()
        
        # Test list_items with the results from list_vaults
        await test_list_items()
        
        # Keep the connection alive until interrupted
        try:
            logger.info("Tests completed. Keeping connection alive...")
            while True:
                await asyncio.sleep(5)
                # Periodically test the connection to keep it alive
                await test_list_vaults()
        except asyncio.CancelledError:
            logger.info("Connection cancelled")
        finally:
            # Cleanup
            if mcp_session:
                await mcp_session.close()
                logger.info("Session closed")
    else:
        logger.error("Failed to connect to 1Password")

# Main function
def run():
    """Run the 1Password MCP client"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")

if __name__ == "__main__":
    run()
