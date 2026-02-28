import httpx
import asyncio
from datetime import datetime
import sys

# Quick and dirty hackathon script to seed Nessie accounts for demo
NESSIE_BASE_URL = "http://api.nessieisreal.com"
# You MUST put a working API key here or the real demo fails
NESSIE_API_KEY = "3799e69bc86e6dd1aa9fb6fd9df80a14"

async def main():
    if NESSIE_API_KEY == "YOUR_API_KEY":
        print("WARNING: Using dummy API key for Nessie. Unless you have a live server with this key, it will fail.")
        print("Consider setting NESSIE_API_KEY in this script during the actual hackathon.")
    
    async with httpx.AsyncClient() as client:
        # Helper to make requests
        async def make_post(path, data):
            url = f"{NESSIE_BASE_URL}{path}?key={NESSIE_API_KEY}"
            resp = await client.post(url, json=data)
            try:
                resp.raise_for_status()
                return resp.json()["objectCreated"]
            except Exception as e:
                print(f"FAILED {path}: {resp.text}")
                return None

        print("1. Creating Alex (Payee/Freelancer)")
        alex = await make_post("/customers", {
            "first_name": "Alex", "last_name": "Payee",
            "address": { "street_number": "123", "street_name": "Main St", "city": "Chicago", "state": "IL", "zip": "60601" }
        })
        if not alex: return
        alex_id = alex["_id"]
        
        print("2. Creating Alex's Checking Account")
        alex_acc = await make_post(f"/customers/{alex_id}/accounts", {
            "type": "Checking", "nickname": "Alex Main", "rewards": 0, "balance": 0
        })
        
        print("3. Creating Jordan (Payer/Client)")
        jordan = await make_post("/customers", {
            "first_name": "Jordan", "last_name": "Payer",
            "address": { "street_number": "456", "street_name": "Second St", "city": "Chicago", "state": "IL", "zip": "60601" }
        })
        jordan_id = jordan["_id"]
        
        print("4. Creating Jordan's Checking Account")
        jordan_acc = await make_post(f"/customers/{jordan_id}/accounts", {
            "type": "Checking", "nickname": "Jordan Main", "rewards": 0, "balance": 0
        })
        jordan_acc_id = jordan_acc["_id"]
        
        print("5. Depositing seed funds for Jordan ($500.00)")
        await make_post(f"/accounts/{jordan_acc_id}/deposits", {
            "medium": "balance", "transaction_date": datetime.now().strftime("%Y-%m-%d"),
            "amount": 50000, "description": "Seed funds for demo"
        })
        
        print("\n=== DEMO ACCOUNTS CREATED ===")
        print(f"Alex (Payee) Account ID: {alex_acc['_id']}")
        print(f"Jordan (Payer) Account ID: {jordan_acc_id}")
        
if __name__ == "__main__":
    asyncio.run(main())
