import asyncio
import random
from asyncua import Server, ua

async def main():
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")
    server.set_server_name("FA MES Server")

    uri = "http://factory.mes"
    idx = await server.register_namespace(uri)
    
    objects = server.nodes.objects
    mes_obj = await objects.add_object(idx, "MES")

    # Variables
    order_id = await mes_obj.add_variable(idx, "Order_ID", "---")
    await order_id.set_writable()
    
    target_qty = await mes_obj.add_variable(idx, "Target_Quantity", 0)
    await target_qty.set_writable()
    
    prod_count = await mes_obj.add_variable(idx, "Production_Count", 0)
    await prod_count.set_writable()
    
    status = await mes_obj.add_variable(idx, "Status", "Idle")
    await status.set_writable()
    
    # Method to request order
    @uamethod
    def request_order(parent):
        # mock generating a new order
        return f"ORD-{random.randint(1000, 9999)}"

    await mes_obj.add_method(idx, "RequestOrder", request_order, [], [ua.VariantType.String])
    
    print("MES OPC UA Server starting at opc.tcp://0.0.0.0:4840/freeopcua/server/")
    async with server:
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    from asyncua import uamethod
    asyncio.run(main())
