import asyncio
import argparse
import os
from kademlia.network import Server
from kademlia.storage import ForgetfulStorage

async def store_data(node, key, value):
    await node.set(key, value)

async def retrieve_data(node, key):
    value = await node.get(key)
    return value

async def run_node(port, bootstrap_ip=None, bootstrap_port=None):
    node = Server(storage=ForgetfulStorage())
    await node.listen(port)

    

    if bootstrap_ip and bootstrap_port:
        await node.bootstrap([(bootstrap_ip, bootstrap_port)])
        
        node.health_check_loop= asyncio.create_task(node._health_check())
        
        print(f"Node started on port {port} and connected to {bootstrap_ip}:{bootstrap_port}")
        # Store and retrieve data
        
        while True:
            command = input("> ").strip()
            if command.lower() == "exit":
                break

            parts = command.split(" ", 2)
            if len(parts) < 2:
                print("Invalid command. Use 'set <key> <value>' or 'get <key>'.")
                continue

            action, key = parts[0], parts[1]

            if action == "set" and len(parts) == 3:
                value = parts[2]
                await node.set(key , value.encode())
                print(f"Stored: {key} = {value}")
            elif action == "get":
                result = await node.get(key)
                print(f"Retrieved: {key} = {result}")
            else:
                print("Invalid command. Use 'set <key> <value>' or 'get <key>'.")


    else:
        node.health_check_loop= asyncio.create_task(node._health_check())
        print(f"Node started on port {port} (standalone)")
        
        

    await asyncio.Future()  # Keeps the node running

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True, help="Port to run the node")
    parser.add_argument("--bootstrap_ip", type=str, help="Bootstrap node IP")
    parser.add_argument("--bootstrap_port", type=int, help="Bootstrap node Port")

    args = parser.parse_args()
    print(args,"ARGUMENTOSSS")
    asyncio.run(run_node(args.port, args.bootstrap_ip, args.bootstrap_port))