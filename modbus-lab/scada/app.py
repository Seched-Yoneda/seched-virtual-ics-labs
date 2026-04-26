from flask import Flask, render_template, jsonify, request
from pymodbus.client import ModbusTcpClient
import time
import traceback
import os

app = Flask(__name__)

# PLC Configuration (BPCS PLC)
PLC_IP = os.environ.get('PLC_IP')
if not PLC_IP:
    raise ValueError("PLC_IP environment variable is strictly required in docker-compose.yml")
PLC_PORT = 502

client = ModbusTcpClient(PLC_IP, port=PLC_PORT)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    try:
        # Pymodbus v3 compatibility
        if not hasattr(client, 'is_socket_open') or not client.is_socket_open():
            if hasattr(client, 'connected'):
                if not client.connected:
                    client.connect()
            else:
                client.connect()
        
        # Ensure connection is established
        if not client.connect():
             return jsonify({'error': f'Failed to connect to PLC at {PLC_IP}'})

        # Read Input Registers (IR 0-4)
        ir_result = client.read_input_registers(address=0, count=5)
        # Read Holding Registers (HR 0-2)
        hr_result = client.read_holding_registers(address=0, count=3)
        # Read Discrete Inputs (DI 0-11)
        di_result = client.read_discrete_inputs(address=0, count=12)
        
        if ir_result.isError():
             return jsonify({'error': f'Error reading IR: {str(ir_result)}'})
        if hr_result.isError():
             return jsonify({'error': f'Error reading HR: {str(hr_result)}'})
        if di_result.isError():
             return jsonify({'error': f'Error reading DI: {str(di_result)}'})
        
        data = {
            'pv': {
                'ir_0': ir_result.registers[0],
                'ir_1': ir_result.registers[1],
                'ir_2': ir_result.registers[2],
                'ir_3': ir_result.registers[3],
                'ir_4': ir_result.registers[4],
            },
            'sp_op': {
                'hr_0': hr_result.registers[0],
                'hr_1': hr_result.registers[1],
                'hr_2': hr_result.registers[2],
            },
            'alarms_states': {
                f'di_{i}': di_result.bits[i] for i in range(12)
            }
        }
        return jsonify(data)
    except Exception as e:
        error_msg = f"Exception: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({'error': error_msg})

@app.route('/api/write', methods=['POST'])
def write_data():
    try:
        if not hasattr(client, 'is_socket_open') or not client.is_socket_open():
            client.connect()
            
        req = request.json
        address = req.get('address')
        value = req.get('value')
        
        if address is None or value is None:
            return jsonify({'error': 'Invalid request'})
            
        result = client.write_register(address=address, value=value)
        if result.isError():
            return jsonify({'success': False, 'error': f'Failed to write register: {str(result)}'})
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
