import asyncio
import os
import logging
import sys
import json
import time
import traceback
from typing import Dict, Any

from dotenv import load_dotenv

# Import Authed components
from authed import Authed
from authed_mcp import AuthedMCPClient

# Configure logging with more detailed information
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("authed_client")

# Set other loggers to debug level
logging.getLogger("mcp").setLevel(logging.DEBUG)
logging.getLogger("authed_mcp").setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.INFO)  # Keep HTTP logging at INFO to reduce noise

# Load environment variables
load_dotenv()

# Configuration for 1Password MCP server
MCP1_SERVER_URL = os.getenv("MCP1_SERVER_URL", "http://localhost:8080/sse")
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
    """Connect to the 1Password MCP server with minimal approach"""
    global mcp_client, mcp_session
    
    try:
        # Initialize Authed client
        logger.info("Initializing Authed client...")
        authed_client = Authed.from_env()
        
        # Initialize our MCP client
        logger.info("Initializing AuthedMCPClient...")
        mcp_client = AuthedMCPClient(
            registry_url=AUTHED_REGISTRY_URL,
            agent_id=AUTHED_AGENT_ID,
            agent_secret=AUTHED_AGENT_SECRET,
            private_key=AUTHED_PRIVATE_KEY
        )
        
        # Create connection to the MCP server
        logger.info(f"Creating connection to 1Password MCP server at {MCP1_SERVER_URL}...")
        
        # Add a timeout to the create_session call
        import asyncio
        try:
            # Set a timeout for the operation
            mcp_session = await asyncio.wait_for(
                mcp_client.create_session(
                    server_url=MCP1_SERVER_URL,
                    server_agent_id=MCP1_SERVER_AGENT_ID
                ),
                timeout=15.0  # 5 second timeout
            )
            logger.info("Successfully created session to 1Password MCP server")
        except asyncio.TimeoutError:
            logger.error("Timeout creating session - operation took too long")
            # Try to access the session anyway
            if mcp_client._session:
                logger.info("Found session in client object despite timeout")
                mcp_session = mcp_client._session
            else:
                logger.error("No session found after timeout")
                raise
        
        logger.info("Session created, continuing with execution")
        logger.info(f"Session object type: {type(mcp_session)}")
        
        # Try to access basic session properties
        for attr_name in ['session_id', 'protocol_version', 'server_info', 'capabilities']:
            if hasattr(mcp_session, attr_name):
                value = getattr(mcp_session, attr_name)
                logger.info(f"Session.{attr_name} = {value}")
            else:
                logger.warning(f"Session has no {attr_name} attribute")
        
        return mcp_session
        
    except Exception as e:
        logger.error(f"Error in connect_to_1password: {e}")
        logger.error(traceback.format_exc())
        return None

async def wait_for_messages():
    """Simply wait for any server-sent events or messages"""
    logger.info("Waiting for server messages...")
    try:
        # Just wait for incoming messages
        await asyncio.sleep(30)
        logger.info("Initial wait period complete")
        return True
    except Exception as e:
        logger.error(f"Error while waiting for messages: {str(e)}")
        return False



async def main():
    """Main function to run the 1Password MCP client"""
    try:
        # Just establish the connection
        logger.info("=========== STARTING CONNECTION SEQUENCE ===========")
        session = await connect_to_1password()
        logger.info("Connection established successfully")
        
        # Test a call to one of the tools to see if it works
        logger.info("=========== TESTING TOOL CALLS ===========")
        try:
            logger.info("Attempting to call onepassword_list_vaults tool...")
            if hasattr(session, 'invoke_tool'):
                result = await session.invoke_tool("onepassword_list_vaults")
                logger.info(f"Tool call result: {result}")
            else:
                logger.warning("Session does not have invoke_tool method")
                
                # Try alternative methods
                if hasattr(session, 'invoke'):
                    logger.info("Trying session.invoke method...")
                    result = await session.invoke("onepassword_list_vaults")
                    logger.info(f"Invoke result: {result}")
                elif hasattr(session, 'call'):
                    logger.info("Trying session.call method...")
                    result = await session.call("onepassword_list_vaults")
                    logger.info(f"Call result: {result}")
        except Exception as e:
            logger.error(f"Error testing tool call: {e}")
            logger.error(traceback.format_exc())
        
        # Wait for any initial messages
        logger.info("Waiting for initial messages...")
        await wait_for_messages()
        
        # Keep the connection alive
        logger.info("=========== MAINTAINING CONNECTION ===========")
        count = 0
        while True:
            count += 1
            logger.info(f"Keeping connection alive... (check #{count})")
            await asyncio.sleep(15)
    except Exception as e:
        logger.error(f"Unhandled exception in main: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        # Cleanup
        if mcp_session:
            logger.info("Closing session...")
            await mcp_session.close()
            logger.info("Session closed")

# Main function
def run():
    """Run the 1Password MCP client"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Unhandled exception in run: {str(e)}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    run()
