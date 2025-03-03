import asyncio
import argparse
from kademlia.network import Server
from kademlia.storage import ForgetfulStorage
import os

async def run_node(port, bootstrap_ip=None, bootstrap_port=None):
    node = Server(storage=ForgetfulStorage())
    await node.listen(port)
    
    
        
    if bootstrap_ip and bootstrap_port:
        res =await node.bootstrap([(bootstrap_ip, bootstrap_port)])
        
        node.health_check_loop= asyncio.create_task(node._health_check())
        print(f"Node started on port {port} and connected to {bootstrap_ip}:{bootstrap_port}")
        print("Bootstrap response:", res)
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