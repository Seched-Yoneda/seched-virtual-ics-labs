from flask import Flask, render_template, jsonify, request
import asyncio
import threading
import time
from asyncua import Client
from cpppo.server.enip.get_attribute import proxy_simple

app = Flask(__name__)

# Cache of status
status_cache = {
    "plc_state": "Disconnected",
    "plc_count": 0,
    "mes_status": "Disconnected",
    "mes_target": 0,
    "mes_order": "---"
}

MES_IP = "10.7.1.40"
PLC_IP = "10.7.1.42"

def poll_services():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(background_poll())

async def background_poll():
    await asyncio.sleep(2)
    mes_client = Client(f"opc.tcp://{MES_IP}:4840/freeopcua/server/")
    mes_connected = False
    
    while True:
        try:
            # Poll PLC via ENIP
            try:
                with proxy_simple(PLC_IP) as plc:
                    res = list(plc.read(['PLC_State', 'Current_Count']))
                    if res and res[0]:
                        state_val = res[0][0]
                        count_val = res[1][0] if len(res)>1 else 0
                        state_map = {0:"Idle", 1:"Running", 2:"Complete", 3:"Error"}
                        status_cache["plc_state"] = state_map.get(state_val, "Unknown")
                        status_cache["plc_count"] = count_val
            except Exception as e:
                status_cache["plc_state"] = "Error Comm"
                
            # Poll MES via OPC UA
            try:
                if not mes_connected:
                    await mes_client.connect()
                    mes_connected = True
                
                order_node = await mes_client.nodes.root.get_child(["0:Objects", "2:MES", "2:Order_ID"])
                target_node = await mes_client.nodes.root.get_child(["0:Objects", "2:MES", "2:Target_Quantity"])
                status_node = await mes_client.nodes.root.get_child(["0:Objects", "2:MES", "2:Status"])
                
                status_cache["mes_order"] = await order_node.get_value()
                status_cache["mes_target"] = await target_node.get_value()
                status_cache["mes_status"] = await status_node.get_value()
            except Exception as e:
                print(f"MES OPC UA Comm Error: {e}", flush=True)
                status_cache["mes_status"] = "Error Comm"
                mes_connected = False
                try:
                    await mes_client.disconnect()
                except:
                    pass
                mes_client = Client(f"opc.tcp://{MES_IP}:4840/freeopcua/server/")
                
        except Exception as e:
            print("Background polling outer loop error:", e, flush=True)
        await asyncio.sleep(1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def status():
    return jsonify(status_cache)

@app.route('/api/command', methods=['POST'])
def command():
    cmd = request.json.get('command')
    
    if cmd == 'order':
        # Request order via OPC UA to MES
        async def req_order():
            try:
                async with Client(f"opc.tcp://{MES_IP}:4840/freeopcua/server/") as client:
                    mes_obj = await client.nodes.root.get_child(["0:Objects", "2:MES"])
                    target_node = await mes_obj.get_child("2:Target_Quantity")
                    res = await mes_obj.call_method("2:RequestOrder")
                    # Set arbitrary target
                    await target_node.set_value(5) 
                    order_node = await mes_obj.get_child("2:Order_ID")
                    await order_node.set_value(res)
            except Exception as e:
                print(e)
        asyncio.run(req_order())
        return jsonify({"success": True})
        
    elif cmd == 'start':
        try:
            with proxy_simple(PLC_IP) as plc:
                list(plc.write(['HMI_Cmd=1']))
        except: pass
        return jsonify({"success": True})
        
    elif cmd == 'reset':
        try:
            with proxy_simple(PLC_IP) as plc:
                list(plc.write(['HMI_Reset=1', 'HMI_Cmd=0']))
        except: pass
        return jsonify({"success": True})
        
    elif cmd == 'toggle_error':
        error_state = request.json.get('state')
        try:
            # 10.7.1.43 is ROBOT_IP
            with proxy_simple("10.7.1.43") as robot:
                list(robot.write([f'Intentional_Error={1 if error_state else 0}']))
        except Exception as e:
            print("Toggle Error Comm Error:", e)
        return jsonify({"success": True})
        
    return jsonify({"success": False, "error": "Unknown command"})

if __name__ == '__main__':
    t = threading.Thread(target=poll_services, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=8080)
