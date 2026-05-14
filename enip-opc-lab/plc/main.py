import asyncio
import threading
import time
import subprocess
from cpppo.server.enip.get_attribute import proxy_simple
from asyncua import Client

def start_enip_server():
    print("Starting PLC ENIP Server via cpppo CLI...")
    subprocess.run(["python", "-m", "cpppo.server.enip", 
                    "-a", "0.0.0.0:44818", 
                    "HMI_Cmd=INT[1]", 
                    "HMI_Reset=INT[1]", 
                    "PLC_State=INT[1]", 
                    "Current_Count=INT[1]"])

enip_thread = threading.Thread(target=start_enip_server, daemon=True)
enip_thread.start()

async def main():
    print("Connecting to MES OPC UA Server...")
    mes_client = Client("opc.tcp://10.7.1.40:4840/freeopcua/server/")
    
    while True:
        try:
            await mes_client.connect()
            break
        except Exception as e:
            print(f"Waiting for MES... ({e})")
            await asyncio.sleep(2)
            
    # Get Nodes
    order_id_node = await mes_client.nodes.root.get_child(["0:Objects", "2:MES", "2:Order_ID"])
    target_qty_node = await mes_client.nodes.root.get_child(["0:Objects", "2:MES", "2:Target_Quantity"])
    prod_count_node = await mes_client.nodes.root.get_child(["0:Objects", "2:MES", "2:Production_Count"])
    status_node = await mes_client.nodes.root.get_child(["0:Objects", "2:MES", "2:Status"])

    print("Connected to MES. Starting control loop.")
    
    robot_ip = "10.7.1.43"
    
    # Wait for own server to start
    await asyncio.sleep(3)

    while True:
        await asyncio.sleep(0.5)
        
        try:
            with proxy_simple("127.0.0.1") as own_plc:
                res = list(own_plc.read(['HMI_Cmd', 'HMI_Reset', 'PLC_State', 'Current_Count']))
                if not res or not res[0]: continue
                hmi_cmd = res[0][0]
                hmi_reset = res[1][0]
                plc_state = res[2][0]
                current = res[3][0]

                if hmi_reset == 1:
                    try:
                        with proxy_simple(robot_ip) as robot:
                            list(robot.write(['Robot_Cmd=2']))
                    except Exception: pass
                    
                    list(own_plc.write(['PLC_State=0', 'HMI_Reset=0', 'HMI_Cmd=0', 'Current_Count=0']))
                    await status_node.set_value("Idle")
                    await prod_count_node.set_value(0)
                    print("PLC Reset applied.")
                    continue
                    
                if plc_state == 0 and hmi_cmd == 1:
                    target_qty = await target_qty_node.get_value()
                    if target_qty > 0:
                        list(own_plc.write(['PLC_State=1', 'Current_Count=0']))
                        await status_node.set_value("Running")
                        await prod_count_node.set_value(0)
                        print("Starting Production Loop...")
                        plc_state = 1
                        current = 0
                    else:
                        list(own_plc.write(['HMI_Cmd=0']))
                        
                if plc_state == 1: # Running
                    target_qty = await target_qty_node.get_value()
                    
                    if current >= target_qty:
                        list(own_plc.write(['PLC_State=2', 'HMI_Cmd=0']))
                        await status_node.set_value("Complete")
                        print("Production Complete.")
                        continue
                        
                    try:
                        with proxy_simple(robot_ip) as robot:
                            r_status_res = list(robot.read(['Robot_Status', 'Robot_Error']))
                            if not r_status_res[0]: continue
                            r_status = r_status_res[0][0]
                            r_error = r_status_res[1][0] if r_status_res[1] else 0
                            
                            if r_error == 1 or r_status == 3:
                                list(own_plc.write(['PLC_State=3']))
                                await status_node.set_value("Error")
                                print("PLC Detected Robot Error!")
                                continue
                                
                            if r_status == 0:
                                list(robot.write(['Robot_Cmd=1']))
                            elif r_status == 1:
                                pass
                            elif r_status == 2:
                                current += 1
                                list(own_plc.write([f'Current_Count={current}']))
                                await prod_count_node.set_value(current)
                                print(f"Cycle finished. Count: {current}/{target_qty}")
                                list(robot.write(['Robot_Cmd=0', 'Robot_Status=0']))
                    except Exception as e:
                        print(f"ENIP Comm Error to Robot: {e}")
        except Exception as e:
            print(f"Internal ENIP Comm Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
