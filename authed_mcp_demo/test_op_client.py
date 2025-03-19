#!/usr/bin/env python3
"""Test script to check OnePasswordClient functionality."""

import asyncio
import os
from dotenv import load_dotenv
from mcp1_server.op_client import OnePasswordClient

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize 1Password client
    print("Initializing 1Password client...")
    op_client = OnePasswordClient()
    
    # Connect to 1Password
    print("Connecting to 1Password...")
    await op_client.connect()
    
    # List all vaults
    print("\nListing all vaults:")
    vaults = await op_client.list_vaults()
    for vault in vaults:
        print(f"- {vault['id']}: {vault['name']}")
    
    # Find the authed vault
    authed_vault = next((v for v in vaults if v['name'].lower() == 'authed'), None)
    
    if not authed_vault:
        print("\nNo vault named 'authed' found!")
        return
    
    # List all items in the authed vault
    vault_id = authed_vault['id']
    print(f"\nListing items in 'authed' vault (ID: {vault_id}):")
    items = await op_client.list_items(vault_id)
    
    if not items:
        print("No items found in the vault!")
        return
    
    for item in items:
        print(f"- {item['id']}: {item['title']}")
    
    # Get the first item's secrets
    item_id = items[0]['id']
    item_title = items[0]['title']
    
    print(f"\nRetrieving secret '{item_title}' (ID: {item_id}):")
    secret = await op_client.get_secret(vault_id, item_id)
    
    print("\nSecret details:")
    if hasattr(secret, 'fields'):
        for field in secret.fields:
            field_value = field.value
            # Truncate long values for display
            if field_value and len(str(field_value)) > 50:
                field_value = str(field_value)[:47] + "..."
            print(f"- {field.label}: {field_value}")
    else:
        print(f"Retrieved: {secret}")

if __name__ == "__main__":
    asyncio.run(main()) 