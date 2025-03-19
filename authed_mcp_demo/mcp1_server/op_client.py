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
        
        # If field_name is provided, create a secret reference
        if field_name:
            # Format: op://<vault>/<item>/[section/]<field>
            secret_ref = f"op://{vault_id}/{item_id}/{field_name}"
            try:
                # Validate and resolve the secret reference
                try:
                    await self.client.secrets.validate_secret_reference(secret_ref)
                except Exception as e:
                    print(f"Warning: Invalid secret reference format: {e}")
                
                # Resolve the secret
                return await self.client.secrets.resolve(secret_ref)
            except Exception as e:
                print(f"Error resolving secret reference '{secret_ref}': {e}")
                # Continue to fallback method
        
        # Fallback: get the item directly
        try:
            # Get the item - note the positional parameters
            item = await self.client.items.get(item_id, vault_id)
            
            if field_name:
                # Look for the specific field
                for field in item.fields:
                    if field.label.lower() == field_name.lower() or field.id.lower() == field_name.lower():
                        return field.value
                raise ValueError(f"Field '{field_name}' not found in item '{item_id}'")
            return item
        except Exception as e:
            raise ValueError(f"Error getting item: {e}")
    
    async def list_vaults(self) -> List[Dict[str, str]]:
        """List all available vaults."""
        if not self.client:
            await self.connect()
        
        result = []
        vaults = await self.client.vaults.list_all()
        async for vault in vaults:
            result.append({"id": vault.id, "name": vault.title})
        return result
    
    async def list_items(self, vault_id: str) -> List[Dict[str, str]]:
        """List all items in a vault."""
        if not self.client:
            await self.connect()
        
        result = []
        # Pass the vault_id as a positional parameter
        items = await self.client.items.list_all(vault_id)
        async for item in items:
            result.append({"id": item.id, "title": item.title})
        return result
