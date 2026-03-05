import asyncio
import os
import sys
import json
import httpx
import time
import hmac
import hashlib
from urllib.parse import urlencode

async def main():
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    
    if not api_key:
        print("Set BINANCE_API_KEY and BINANCE_API_SECRET")
        return
        
    symbol = "ETHUSDT"
    
    def generate_signature(query_string: str) -> str:
        return hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

    async with httpx.AsyncClient() as client:
        params_obj = {"timestamp": int(time.time() * 1000), "symbol": symbol}
        query_string = urlencode(params_obj)
        signature = generate_signature(query_string)
        url = f"https://fapi.binance.com/fapi/v2/positionRisk?{query_string}&signature={signature}"
        headers = {"X-MBX-APIKEY": api_key}
        response = await client.get(url, headers=headers)
        print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
