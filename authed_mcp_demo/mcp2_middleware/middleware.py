import asyncio
import os
import json
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from authed import Authed
from authed_mcp import AuthedMCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="MCP2 Middleware")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MCP1_SERVER_URL = os.getenv("MCP1_SERVER_URL", "http://localhost:8000")
MCP1_SERVER_AGENT_ID = os.getenv("MCP1_SERVER_AGENT_ID")

# Initialize Authed client for MCP1 server access
authed = Authed.from_env()
mcp1_client = None

async def get_mcp1_client():
    """Get or initialize the AuthedMCPClient for the MCP1 server"""
    global mcp1_client
    if mcp1_client is None:
        mcp1_client = AuthedMCPClient(authed=authed)
    return mcp1_client

# MCP protocol endpoints for Cursor
@app.get("/mcp/resources")
async def list_resources(request: Request):
    """MCP endpoint to list available resources by proxying to MCP1 server"""
    client = await get_mcp1_client()
    try:
        # List resources from MCP1 server
        resources = await client.list_resources(
            server_url=MCP1_SERVER_URL,
            server_agent_id=MCP1_SERVER_AGENT_ID
        )
        
        # Return resources to Cursor
        return resources
    except Exception as e:
        print(f"Error listing resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mcp/resources/{resource_path:path}")
async def get_resource(request: Request, resource_path: str):
    """MCP endpoint to get a resource from the MCP1 server"""
    client = await get_mcp1_client()
    try:
        # Extract query parameters
        params = dict(request.query_params)
        
        # Call the resource on MCP1 server
        result = await client.call_resource(
            server_url=MCP1_SERVER_URL,
            server_agent_id=MCP1_SERVER_AGENT_ID,
            resource_path=f"/{resource_path}",
            method="GET",
            params=params
        )
        
        # Return the result
        return result
    except Exception as e:
        print(f"Error getting resource: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mcp/tools")
async def list_tools(request: Request):
    """MCP endpoint to list available tools by proxying to MCP1 server"""
    client = await get_mcp1_client()
    try:
        # List tools from MCP1 server
        tools = await client.list_tools(
            server_url=MCP1_SERVER_URL,
            server_agent_id=MCP1_SERVER_AGENT_ID
        )
        
        # Return tools to Cursor
        return tools
    except Exception as e:
        print(f"Error listing tools: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/{tool_id}")
async def call_tool(request: Request, tool_id: str):
    """MCP endpoint to call a tool on the MCP1 server"""
    client = await get_mcp1_client()
    try:
        # Get the request body
        data = await request.json()
        
        # Call the tool on MCP1 server
        result = await client.call_tool(
            server_url=MCP1_SERVER_URL,
            server_agent_id=MCP1_SERVER_AGENT_ID,
            tool_id=tool_id,
            params=data
        )
        
        # Return the result
        return result
    except Exception as e:
        print(f"Error calling tool: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Additional endpoints for usability

@app.get("/")
async def root():
    """Root endpoint for health check"""
    return {
        "status": "ok", 
        "service": "MCP2 Middleware", 
        "connected_to": f"{MCP1_SERVER_URL} (agent: {MCP1_SERVER_AGENT_ID})"
    }

# SSE stream for Cursor using the MCP protocol
@app.get("/mcp/sse")
async def sse(request: Request):
    """Server-Sent Events endpoint for MCP streaming"""
    
    async def event_stream():
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connection', 'status': 'connected'})}\n\n"
            
            # Keep the connection alive
            while True:
                await asyncio.sleep(30)
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                
        except asyncio.CancelledError:
            # Connection closed
            yield f"data: {json.dumps({'type': 'connection', 'status': 'disconnected'})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# Main function
async def main():
    """Main function"""
    import uvicorn
    
    # Initialize the MCP1 client
    client = await get_mcp1_client()
    
    # Check connection to MCP1 server
    try:
        resources = await client.list_resources(
            server_url=MCP1_SERVER_URL,
            server_agent_id=MCP1_SERVER_AGENT_ID
        )
        print(f"Connected to MCP1 server at {MCP1_SERVER_URL}")
        print(f"Available resources: {resources}")
    except Exception as e:
        print(f"Error connecting to MCP1 server: {str(e)}")
        print("Please check your configuration and make sure the MCP1 server is running.")
    
    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8080)

if __name__ == "__main__":
    asyncio.run(main())
