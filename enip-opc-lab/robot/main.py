import pybullet as p
import pybullet_data
import time
import threading
import sys
import random
import subprocess
import traceback
from cpppo.server.enip.get_attribute import proxy_simple

def start_enip_server():
    print("Starting Robot ENIP Server via CLI...")
    subprocess.run(["python", "-m", "cpppo.server.enip", 
                    "-a", "0.0.0.0:44818", 
                    "Robot_Cmd=INT[1]", 
                    "Robot_Status=INT[1]", 
                    "Robot_Error=INT[1]", 
                    "Target_X=REAL[1]", 
                    "Target_Y=REAL[1]",
                    "Intentional_Error=INT[1]"])

enip_thread = threading.Thread(target=start_enip_server, daemon=True)
enip_thread.start()

# --- ENIP Background Polling ---
# 共有状態 (Global State)
robot_moving = False # 追加: 動作中のポーリング停止用フラグ
robot_state = {
    "Robot_Cmd": 0,
    "Target_X": 0.615,
    "Target_Y": 0.0,
    "Intentional_Error": 0,
    "Robot_Status": 0,
    "Robot_Error": 0
}
state_lock = threading.Lock()
enip_lock = threading.Lock() # 追加: cpppoクライアントの同時実行を防ぐロック

def write_enip(tags):
    """ cpppo API経由でENIP書き込みを行う (subprocess排除で超軽量化) """
    with enip_lock:
        try:
            with proxy_simple("127.0.0.1") as own_robot:
                list(own_robot.write(tags))
        except Exception as e:
            print(f"ENIP Write Error: {e}")

def read_enip_state():
    """ cpppo API経由でENIP読み込みを行い、状態を更新する """
    global robot_state
    with enip_lock:
        try:
            with proxy_simple("127.0.0.1") as own_robot:
                res = list(own_robot.read(['Robot_Cmd', 'Target_X', 'Target_Y', 'Intentional_Error']))
                if res and res[0]:
                    new_state = {}
                    if res[0]: new_state["Robot_Cmd"] = res[0][0]
                    if len(res)>1 and res[1]: new_state["Target_X"] = res[1][0]
                    if len(res)>2 and res[2]: new_state["Target_Y"] = res[2][0]
                    if len(res)>3 and res[3]: new_state["Intentional_Error"] = res[3][0]
                    
                    with state_lock:
                        if "Robot_Cmd" in new_state: robot_state["Robot_Cmd"] = new_state["Robot_Cmd"]
                        if "Target_X" in new_state: robot_state["Target_X"] = new_state["Target_X"]
                        if "Target_Y" in new_state: robot_state["Target_Y"] = new_state["Target_Y"]
                        if "Intentional_Error" in new_state: robot_state["Intentional_Error"] = new_state["Intentional_Error"]
        except Exception as e:
            print(f"ENIP Read Error: {e}")

def enip_polling_loop():
    """ バックグラウンドでENIPサーバと通信するスレッド """
    global robot_moving
    time.sleep(4) # Server startup wait
    write_enip(['Target_X=0.615', 'Target_Y=0.0'])
    while True:
        if not robot_moving:
            read_enip_state()
        time.sleep(0.5) # ポーリング間隔（CPU負荷とGUIのフリーズを回避）

polling_thread = threading.Thread(target=enip_polling_loop, daemon=True)
polling_thread.start()

# ------ PyBullet 描画処理 ------
try:
    physicsClient = p.connect(p.GUI, options="--width=640 --height=480 --opengl2")
    if physicsClient < 0:
        raise p.error("physicsClient < 0")
except p.error as e:
    error_msg = (
        f"\n[CRITICAL ERROR] 描画の失敗・ディスプレイ接続に失敗しました: {e}\n"
        "【原因】X11ディスプレイ(Ubuntuのデスクトップ)にログインしていない、または画面サイズが小さすぎる等によりGUIが起動できません。\n"
        "【対処】ホスト側でGUIデスクトップを開いた状態で再度コンテナを起動してください。\n"
    )
    print(error_msg, file=sys.stderr)
    # GUI起動失敗時は強制終了させ、docker logsで見やすくする
    sys.exit(1)

p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
p.configureDebugVisualizer(p.COV_ENABLE_MOUSE_PICKING, 0)
p.configureDebugVisualizer(p.COV_ENABLE_KEYBOARD_SHORTCUTS, 0)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -10)
planeId = p.loadURDF("plane.urdf")
robotId = p.loadURDF("kuka_iiwa/model.urdf", [0, 0, 0], useFixedBase=True)

blocks_info = [
    {"pos": [0.615, -0.1, 0.05], "rgba": [0.8, 0.1, 0.1, 1]},
    {"pos": [0.615, 0.0, 0.05], "rgba": [0.1, 0.8, 0.1, 1]},
    {"pos": [0.615, 0.1, 0.05], "rgba": [0.1, 0.1, 0.8, 1]}
]
blocks = []
for info in blocks_info:
    b_id = p.loadURDF("cube_small.urdf", info["pos"])
    p.changeVisualShape(b_id, -1, rgbaColor=info["rgba"])
    blocks.append({"id": b_id, "start_pos": info["pos"]})

p.resetDebugVisualizerCamera(cameraDistance=1.2, cameraYaw=50, cameraPitch=-35, cameraTargetPosition=[0.3, 0, 0.2])

def move_arm_to_xyz(target_position):
    target_orientation = p.getQuaternionFromEuler([0, 3.14159, 0])
    current_poses = [p.getJointState(robotId, i)[0] for i in range(7)]
    rest_poses = [current_poses[0], current_poses[1], current_poses[2], -1.57, 0, 1.57, 0]
    
    joint_poses = p.calculateInverseKinematics(robotId, 6, target_position, target_orientation,
                                               lowerLimits=[-2.96, -2.09, -2.96, -2.09, -2.96, -2.09, -3.05],
                                               upperLimits=[2.96, 2.09, 2.96, 2.09, 2.96, 2.09, 3.05],
                                               jointRanges=[5.8, 4.0, 5.8, 4.0, 5.8, 4.0, 6.0],
                                               restPoses=rest_poses)
    for i in range(7):
        p.setJointMotorControl2(robotId, i, p.POSITION_CONTROL, targetPosition=joint_poses[i], force=200)

home_positions = [0, 0, 0, -1.57, 0, 1.57, 0]
for i in range(7):
    p.resetJointState(robotId, i, targetValue=home_positions[i])
    p.setJointMotorControl2(robotId, i, p.POSITION_CONTROL, targetPosition=home_positions[i], force=200)

for _ in range(50):
    try:
        p.stepSimulation()
    except Exception:
        pass

active_block_idx = 0

print("Robot simulator is running.")
last_cmd = 0 # 追加: 立ち上がりエッジ検出用フラグ

try:
    while True:
        try:
            with state_lock:
                cmd = robot_state["Robot_Cmd"]
                intentional_error = robot_state["Intentional_Error"]
                bx = robot_state["Target_X"]
                by = robot_state["Target_Y"]

            if cmd == 1 and last_cmd != 1: # Pick command (エッジ検出)
                last_cmd = 1
                robot_moving = True
                
                # アームが一番上（静止中）のときに同期的に書き込む（動作中のカクつきを完全に防ぐため）
                write_enip(['Robot_Status=1'])
                
                # 前の動作の完了（HMIのカウント更新）から次の下降までに「間」を作るための静止時間
                # ここを短くしてもシステム上の不安定さは一切生じません。サクサク動かすため0.25秒待機にします。
                def safe_step(steps):
                    for _ in range(steps):
                        p.stepSimulation()
                        time.sleep(0.016)
                safe_step(15)
                
                if intentional_error == 1 and random.random() < 0.05:
                    print("Robot Error Occurred!")
                    write_enip(['Robot_Error=1', 'Robot_Status=3', 'Robot_Cmd=0'])
                    with state_lock:
                        robot_state["Robot_Cmd"] = 0
                    robot_moving = False
                else:
                    block = blocks[active_block_idx % len(blocks)]
                    b_pos, _ = p.getBasePositionAndOrientation(block['id'])
                    
                    current_pos = p.getLinkState(robotId, 6)[0]
                    
                    move_arm_to_xyz([current_pos[0], current_pos[1], 0.4])
                    safe_step(20)
                    
                    move_arm_to_xyz([b_pos[0], b_pos[1], 0.3])
                    safe_step(20)
                    
                    move_arm_to_xyz([b_pos[0], b_pos[1], 0.15])
                    safe_step(20)
                    
                    move_arm_to_xyz([b_pos[0], b_pos[1], 0.4])
                    safe_step(20)
                    
                    for i in range(7):
                        p.setJointMotorControl2(robotId, i, p.POSITION_CONTROL, targetPosition=home_positions[i], force=200)
                    safe_step(30)
                    
                    active_block_idx += 1
                    
                    # 動作完了後、アームが一番上に戻ってから同期的に状態を送信する
                    write_enip(['Robot_Status=2', 'Robot_Cmd=0'])
                    with state_lock:
                        robot_state["Robot_Cmd"] = 0
                    print("Robot action complete. Waiting for ENIP sync...")
                    
                    robot_moving = False
            
            elif cmd == 2 and last_cmd != 2: # Error Reset / Stop
                last_cmd = 2
                write_enip(['Robot_Error=0', 'Robot_Status=0', 'Robot_Cmd=0'])
                with state_lock:
                    robot_state["Robot_Cmd"] = 0
                print("Robot Reset")
                
            elif cmd == 0:
                last_cmd = 0
                
            p.stepSimulation()
            time.sleep(0.1) # X11バッファ詰まり防止のため、待機時間を増やして描画頻度を下げる
            
        except p.error as pe:
            # PyBulletのGUI切断エラーなどを検知して安全に終了
            print(f"PyBullet Error (Display lost?): {pe}")
            break
        except Exception as e:
            print(f"Unexpected Error in Main Loop: {e}")
            time.sleep(0.1)

except KeyboardInterrupt:
    print("Shutting down...")
finally:
    try:
        p.disconnect()
    except:
        pass
    sys.exit(0)
