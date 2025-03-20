import asyncio
import os
import logging
from dotenv import load_dotenv
import inspect

# Import FastMCP
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from mcp.server.sse import SseServerTransport

# Import Authed for verification
from authed import Authed

# Import 1Password client
from op_client import OnePasswordClient

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize 1Password client
op_client = OnePasswordClient()

# Initialize Authed SDK for verification only
authed = Authed.from_env()

# Auth middleware
class AuthedMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Only check authentication for SSE endpoint
        # Check for authentication headers
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning("No Authorization header found")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
            
        # Verify the token
        if not auth_header.startswith("Bearer "):
            logger.warning("No Bearer token found in Authorization header")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication failed - no Bearer token"}
            )
            
        # Extract token from Authorization header
        token = auth_header.replace("Bearer ", "")
        
        # Extract DPoP proof from headers
        dpop_header = request.headers.get("dpop")
        if not dpop_header:
            logger.warning("Missing DPoP proof header")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication failed - missing DPoP proof header"}
            )
        
        try:
            # Create a new DPoP proof specifically for the verification request
            verify_url = f"{authed.registry_url}/tokens/verify"
            dpop_handler = DPoPHandler()
            verification_proof = dpop_handler.create_proof(
                "POST",  # Verification endpoint uses POST
                verify_url,  # Use the verification endpoint URL
                authed._private_key
            )
            
            # Set up verification headers
            verify_headers = {
                "authorization": f"Bearer {token}",
                "dpop": verification_proof,  # Use the new proof for verification
                "original-method": request.method  # Include original method
            }
            
            # Verify the token using standalone httpx client instead of authed_auth.client
            async with httpx.AsyncClient(base_url=authed_auth.registry_url) as client:
                response = await client.post(
                    "/tokens/verify",
                    headers=verify_headers,
                    json={"token": token}
                )
                
                if response.status_code != 200:
                    logger.warning(f"Token verification failed: {response.text}")
                    return JSONResponse(
                        status_code=401,
                        content={"detail": f"Authentication failed: {response.text}"}
                    )
                logger.info("Token verified successfully")
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            return JSONResponse(
                status_code=401,
                content={"detail": f"Authentication failed: {str(e)}"}
            )
        
        # Continue with the request
        return await call_next(request)

def create_server():
    """Create and configure the FastMCP server"""
    # Create the FastMCP server
    server = FastMCP(
        name="1password-secrets-server",
        debug=True,
        log_level="DEBUG",
        host="0.0.0.0",
        port=8080
    )
    
    # Register 1Password resources
    @server.resource("op://vaults", name="List Vaults", description="List all available 1Password vaults")
    async def list_vaults_resource():
        try:
            vaults = await op_client.list_vaults()
            return {"vaults": vaults}
        except Exception as e:
            logger.error(f"Error listing vaults: {e}")
            return {"error": str(e)}
    
    @server.resource("op://vaults/{vault_id}/items", 
                   name="List Items", 
                   description="List all items in a 1Password vault")
    async def list_items_resource(vault_id: str):
        try:
            items = await op_client.list_items(vault_id)
            return {"items": items}
        except Exception as e:
            logger.error(f"Error listing items: {e}")
            return {"error": str(e)}
    
    @server.resource("op://vaults/{vault_id}/items/{item_id}",
                   name="Get Secret",
                   description="Get a secret from 1Password")
    async def get_secret_resource(vault_id: str, item_id: str):
        try:
            field = "credentials"
            secret = await op_client.get_secret(vault_id, item_id, field)
            return {"secret": secret}
        except Exception as e:
            logger.error(f"Error getting secret: {e}")
            return {"error": str(e)}
    
    # Register 1Password tools
    @server.tool(name="onepassword_list_vaults", 
                description="List all available 1Password vaults")
    async def list_vaults_tool():
        try:
            vaults = await op_client.list_vaults()
            return {"vaults": vaults}
        except Exception as e:
            logger.error(f"Error with list_vaults tool: {e}")
            return {"error": str(e)}
    
    @server.tool(name="onepassword_list_items",
                description="List all items in a 1Password vault")
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
            logger.error(f"Error with list_items tool: {e}")
            return {"error": str(e)}
    
    @server.tool(name="onepassword_get_secret",
                description="Retrieve a secret from 1Password")
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
            logger.error(f"Error with get_secret tool: {e}")
            return {"error": str(e)}
    
    # Patch initialization options to ensure listChanged=True
    orig_init_fn = server._mcp_server.create_initialization_options
    
    def patched_init():
        options = orig_init_fn()
        # Force capabilities to show tools as changed
        if hasattr(options, 'capabilities'):
            for cap_type in ['tools', 'resources', 'prompts']:
                cap_obj = getattr(options.capabilities, cap_type, None)
                if cap_obj and hasattr(cap_obj, 'listChanged'):
                    setattr(cap_obj, 'listChanged', True)
                    logger.info(f"Set {cap_type}.listChanged = True")
        return options
    
    # Apply the patch
    server._mcp_server.create_initialization_options = patched_init
    
    # Log the registered tools and resources
    logger.info(f"Registered {len(server._tool_manager.list_tools())} tools")
    logger.info(f"Registered {len(server._resource_manager.list_resources())} resources")
    
    return server

# Create our own version of the run_sse_async method to include auth middleware
async def run_server_with_auth(server):
    # Create the SSE transport
    sse = SseServerTransport("/messages/")
    
    # Create the original handler
    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as streams:
            await server._mcp_server.run(
                streams[0],
                streams[1],
                server._mcp_server.create_initialization_options(),
            )
    
    # Create Starlette app with auth middleware
    app = Starlette(
        debug=server.settings.debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        middleware=[
            Middleware(AuthedMiddleware),
        ]
    )
    
    # Run with Uvicorn
    import uvicorn
    config = uvicorn.Config(
        app,
        host=server.settings.host,
        port=server.settings.port,
        log_level=server.settings.log_level.lower(),
    )
    server_instance = uvicorn.Server(config)
    await server_instance.serve()

async def main():
    """Run the 1Password MCP server with Authed authentication"""
    try:
        # Initialize 1Password client
        await op_client.connect()
        logger.info("Connected to 1Password")
        
        # Create the server
        server = create_server()
        
        # Run our custom version with auth middleware
        logger.info(f"Starting server on {server.settings.host}:{server.settings.port}")
        await run_server_with_auth(server)
        
    except Exception as e:
        logger.error(f"Error in server: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())