import os
import asyncio
from app.main import get_installation_access_token, async_client

async def test_handshake():
    # Grab the installation ID from your app settings or previous logs
    # If you don't know it, look at your GitHub App Settings -> Install App -> The number in the URL!
    installation_id = 139895444  #  REPLACE THIS with your actual installation ID number
    
    print("Testing RSA Private Key & JWT Minting Engine...")
    try:
        token = await get_installation_access_token(installation_id)
        print("🟢 SUCCESS! Cryptographic Handshake Complete.")
        print(f"Your temporary, secure Installation Token is: ghs_{token[:10]}...")
    except Exception as e:
        print("❌ FAILURE! Authentication crashed.")
        print(f"Reason: {str(e)}")
        
    await async_client.aclose()

asyncio.run(test_handshake())
