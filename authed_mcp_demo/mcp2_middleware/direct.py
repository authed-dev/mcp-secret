import asyncio
import os
import logging
import sys
from dotenv import load_dotenv

# Correct imports for MCP client based on the structure
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import JSONRPCRequest

# Import Authed for authentication
from authed import Authed

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("direct_client")

# Load environment variables
load_dotenv()

# Configuration
SERVER_URL = os.getenv("MCP1_SERVER_URL", "http://localhost:8080/sse")
SERVER_AGENT_ID = os.getenv("MCP1_SERVER_AGENT_ID")

async def run_client():
    """Run a direct MCP client with Authed authentication"""
    try:
        # Initialize Authed SDK for authentication only
        logger.info("Initializing Authed SDK...")
        authed = Authed.from_env()
        
        # Get authentication headers
        logger.info("Getting authentication headers...")
        auth_headers = await authed.auth.protect_request(
            url=SERVER_URL,
            method="GET", 
            target_agent_id=SERVER_AGENT_ID
        )
        logger.info(f"Got authentication headers")
        
        # Create a direct connection using sse_client function
        logger.info(f"Creating direct SSE connection to {SERVER_URL}")
        async with sse_client(SERVER_URL, headers=auth_headers) as (read_stream, write_stream):
            logger.info("SSE connection established successfully")
            
            # Create a session using the transport streams
            session = ClientSession(transport_read=read_stream, transport_write=write_stream)
            logger.info("Client session created")
            
            # Initialize the session
            logger.info("Initializing session...")
            await session.initialize()
            logger.info("Session initialized successfully")
            
            # Get tool list
            logger.info("Requesting tools list...")
            tools = await session.get_tools()
            if tools:
                logger.info(f"SUCCESS! Found {len(tools)} tools:")
                for i, tool in enumerate(tools):
                    logger.info(f"Tool {i+1}: {tool.name} - {tool.description}")
                    
                # Try a tool invocation
                logger.info("Trying to invoke onepassword_list_vaults tool...")
                result = await session.invoke_tool("onepassword_list_vaults")
                logger.info(f"Tool invocation result: {result}")
            else:
                logger.warning("No tools found")
            
            # Keep session alive for a bit
            logger.info("Keeping session alive...")
            for i in range(5):
                logger.info(f"Heartbeat {i+1}")
                await asyncio.sleep(5)
            
            logger.info("Session completed")
            
    except Exception as e:
        logger.error(f"Error in client: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    try:
        asyncio.run(run_client())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        import traceback
        logger.error(traceback.format_exc())