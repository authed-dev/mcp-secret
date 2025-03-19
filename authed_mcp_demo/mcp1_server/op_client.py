import os
from onepassword.client import Client
from typing import Dict, List, Optional, Any

class OnePasswordClient:
    """Wrapper around 1Password SDK to retrieve secrets."""
    
    def __init__(self):
        """Initialize the 1Password client using environment variables."""
        # These should be set in .env or provided securely
        self.op_token = os.getenv("OP_SERVICE_ACCOUNT_TOKEN")
        self.client = None
        
    async def connect(self):
        """Create connection to 1Password."""
        if not self.op_token:
            raise ValueError("OP_SERVICE_ACCOUNT_TOKEN environment variable is not set")
        
        # Initialize the 1Password client
        self.client = await Client.authenticate(
            auth=self.op_token, 
            integration_name="Authed MCP 1Password Integration", 
            integration_version="v1.0.0"
        )
        return self.client
    
    async def get_secret(self, vault_id: str, item_id: str, field_name: Optional[str] = None) -> Any:
        """
        Retrieve a secret from 1Password.
        
        Args:
            vault_id (str): The ID or name of the vault containing the secret
            item_id (str): The ID or title of the item containing the secret
            field_name (str, optional): The specific field to retrieve
            
        Returns:
            The secret value or the entire item if field_name is None
        """
        if not self.client:
            await self.connect()
        
        # Create the secret reference
        if field_name:
            secret_ref = f"op://{vault_id}/{item_id}/{field_name}"
        else:
            secret_ref = f"op://{vault_id}/{item_id}"
        
        # Resolve the secret
        try:
            return await self.client.secrets.resolve(secret_ref)
        except Exception as e:
            # If we couldn't resolve it with the simple format, try to get the item and field directly
            if field_name:
                # This is a fallback in case the reference doesn't work
                item = await self.client.items.get(item_id, vault=vault_id)
                for field in item.fields:
                    if field.label.lower() == field_name.lower() or field.id.lower() == field_name.lower():
                        return field.value
                raise ValueError(f"Field '{field_name}' not found in item '{item_id}'")
            raise e
    
    async def list_vaults(self) -> List[Dict[str, str]]:
        """List all available vaults."""
        if not self.client:
            await self.connect()
        
        vaults = await self.client.vaults.list()
        return [{"id": vault.id, "name": vault.name} for vault in vaults]
    
    async def list_items(self, vault_id: str) -> List[Dict[str, str]]:
        """List all items in a vault."""
        if not self.client:
            await self.connect()
        
        items = await self.client.items.list(vault=vault_id)
        return [{"id": item.id, "title": item.title} for item in items]
