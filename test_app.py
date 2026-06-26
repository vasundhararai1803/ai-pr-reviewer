import os
import asyncio
import pytest
from app.main import get_installation_access_token, async_client

@pytest.mark.anyio
async def test_handshake():
    installation_id = 139895444  
    
    print("Testing RSA Private Key & JWT Minting Engine...")
    try:
        token = await get_installation_access_token(installation_id)
        print("Cryptographic Handshake Complete.")
        print(f"Your temporary, secure Installation Token is: ghs_{token[:10]}...")
    except Exception as e:
        print("Authentication crashed.")
        print(f"Reason: {str(e)}")
        
    await async_client.aclose()

if __name__ == "__main__":
    asyncio.run(test_handshake())
