import pybullet as p
import pybullet_data
import time
import os
from cpppo.server.enip.get_attribute import proxy_simple

# PyBulletのGUI起動と初期設定 (フリーズ対策のため、GUIを出さないDIRECTモードに変更)
# GPUがない環境での描画速度向上のため、解像度を下げ、古いOpenGL(opengl2)を使用するオプションを追加
physicsClient = p.connect(p.GUI, options="--width=640 --height=480 --opengl2")
p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 0)
# その他の不要な描画オプションも無効化
p.configureDebugVisualizer(p.COV_ENABLE_RGB_BUFFER_PREVIEW, 0)
p.configureDebugVisualizer(p.COV_ENABLE_DEPTH_BUFFER_PREVIEW, 0)
p.configureDebugVisualizer(p.COV_ENABLE_SEGMENTATION_MARK_PREVIEW, 0)

p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -10)
planeId = p.loadURDF("plane.urdf")
robotId = p.loadURDF("kuka_iiwa/model.urdf", [0, 0, 0], useFixedBase=True)

# ブロックを3つ直線上に配置する (遠い順: 黒, 白, 黒)
blocks_info = [
    {"pos": [0.615, 0, 0.05], "expected_color": "black", "rgba": [0, 0, 0, 1]},
    {"pos": [0.515, 0, 0.05], "expected_color": "white", "rgba": [1, 1, 1, 1]},
    {"pos": [0.415, 0, 0.05], "expected_color": "black", "rgba": [0, 0, 0, 1]}
]
blocks = []
for info in blocks_info:
    b_id = p.loadURDF("cube_small.urdf", info["pos"])
    p.changeVisualShape(b_id, -1, rgbaColor=info["rgba"])
    p.changeDynamics(b_id, -1, mass=0.1, lateralFriction=1.0)
    blocks.append({"id": b_id, "start_pos": info["pos"]})

# カメラ位置を調整してロボットと積み木全体を見やすくする
p.resetDebugVisualizerCamera(cameraDistance=1.2, cameraYaw=50, cameraPitch=-35, cameraTargetPosition=[0.3, 0, 0.2])

def move_arm_to_xyz(target_position):
    """逆運動学(IK)を使って指定座標へアームの関節角度を計算し、動かす"""
    # エンドエフェクタ(リンク7)の向きは常に下向き(垂直)にする
    target_orientation = p.getQuaternionFromEuler([0, 3.14159, 0])
    
    # 逆運動学の初期姿勢（シード値）として、あらかじめ「下を向いている状態」の値を与える
    # パスが極端にジャンプしないように、現在角度を取得してrestPoseのベースにする
    current_poses = [p.getJointState(robotId, i)[0] for i in range(7)]
    
    # 手首の関節(J4, J5)が不自然な方向に曲がりっぱなしになるのを防ぐため、
    # 常に「下向き(J4=0, J5=1.57)」に近くなるようなrestPosesを指定
    rest_poses = [current_poses[0], current_poses[1], current_poses[2], -1.57, 0, 1.57, 0]
    
    # 逆運動学で7つの関節角度を計算
    joint_poses = p.calculateInverseKinematics(robotId, 6, target_position, target_orientation,
                                               lowerLimits=[-2.96, -2.09, -2.96, -2.09, -2.96, -2.09, -3.05],
                                               upperLimits=[2.96, 2.09, 2.96, 2.09, 2.96, 2.09, 3.05],
                                               jointRanges=[5.8, 4.0, 5.8, 4.0, 5.8, 4.0, 6.0],
                                               restPoses=rest_poses,
                                               maxNumIterations=100,
                                               residualThreshold=1e-5)
    
    # 計算された角度を各関節(0~6)に適用
    for i in range(7):
        p.setJointMotorControl2(robotId, i, p.POSITION_CONTROL, targetPosition=joint_poses[i], force=200)

def control_gripper(open_gripper=True):
    """(指なし吸着モデルのため何もしない)"""
    pass

# 起動直後に「アームをまっすぐ伸ばした変な姿勢(オール0)」からスタートさせないよう、初期姿勢(Home)にリセット
home_positions = [0, 0, 0, -1.57, 0, 1.57, 0]
for i in range(7):
    p.resetJointState(robotId, i, targetValue=home_positions[i])
    p.setJointMotorControl2(robotId, i, p.POSITION_CONTROL, targetPosition=home_positions[i], force=200)

for _ in range(50):
    p.stepSimulation()


PLC_IP = os.environ.get('PLC_IP', '127.0.0.1')

print("ロボットシミュレータ起動。PLCに接続します...")
with proxy_simple(PLC_IP) as plc:
    while True:
        try:
            # 1. PLCから指令を読み取る
            try:
                cmd_data = list(plc.read(['Robot_Cmd', 'Target_X', 'Target_Y']))
                cmd = cmd_data[0][0] if cmd_data and cmd_data[0] else 0
                target_x = cmd_data[1][0] if len(cmd_data)>1 and cmd_data[1] else 0.0
                target_y = cmd_data[2][0] if len(cmd_data)>2 and cmd_data[2] else 0.0
            except Exception:
                cmd = 0
            
            if cmd == 1: # Pick指令が来たら
                print(f"Pick指令を受信(Target={target_x}, {target_y})。動作を開始します...")
                # PLCのステータスを「動作中(1)」にする
                list(plc.write(['Robot_Status=1'])) 
                
                # --- 指定された座標に最も近いブロックを探す ---
                closest_block_id = None
                min_dist = 999
                for block in blocks:
                    b_pos, _ = p.getBasePositionAndOrientation(block["id"])
                    dist = (b_pos[0] - target_x)**2 + (b_pos[1] - target_y)**2
                    if dist < min_dist and dist < 0.05: # 判定対象
                        min_dist = dist
                        closest_block_id = block["id"]
                
                if closest_block_id is None:
                    print("指定された座標にブロックが見つかりませんでした。スキップします。")
                    list(plc.write(['Robot_Status=2', 'Robot_Cmd=0']))
                    continue
                
                # インデント維持のためのダミーブロック
                if True:
                    idx = 0
                    block_id = closest_block_id
                    bx, by, bz = target_x, target_y, 0.05
                    
                    print(f"[{idx+1}/3] ブロック({bx}, {by})へ移動し、ビジョンセンサで色を判定します...")
                    
                    # 1. ブロックの真上(Z=0.4)の安全な高い位置へまず移動 (他のブロックをなぎ払わないため)
                    # 現在のX,YからZだけ上げる動作を挟む
                    current_pos = p.getLinkState(robotId, 6)[0]
                    move_arm_to_xyz([current_pos[0], current_pos[1], 0.4])
                    for _ in range(20):
                        p.stepSimulation()
                        time.sleep(0.016)
                    
                    # その後、目的のブロックの上空(Z=0.3)へ水平移動 (ビジョンセンサ・ポジション)
                    move_arm_to_xyz([bx, by, 0.3])
                    control_gripper(open_gripper=True)
                    for _ in range(20): # 少し長めに停止してカメラ撮影を演出
                        p.stepSimulation()
                        time.sleep(0.016)
                        
                    # --- ビジョンセンサ処理 (PyBulletから色情報を取得) ---
                    visual_shape_data = p.getVisualShapeData(block_id)
                    rgba = visual_shape_data[0][7] # RGBAカラー情報
                    
                    # 黒か白か判定 (Redの値で簡易判定. 1なら白, 0なら黒)
                    if rgba[0] > 0.5:
                        detected_color = "white"
                        print(f"  -> ビジョンセンサ結果: 【白】であることを認識しました。")
                    else:
                        detected_color = "black"
                        print(f"  -> ビジョンセンサ結果: 【黒】であることを認識しました。")
                    # ----------------------------------------------------
                        
                    # 2. ブロックの位置(Z=0.125)まで下降 (吸着位置)
                    # ブロック上面(Z=0.10)にギリギリまで近づくことで引き寄せ時のブレを抑える
                    print(f"[{idx+1}/3] ハンドを下降させ、吸着します...")
                    move_arm_to_xyz([bx, by, 0.125])
                    for _ in range(20):
                        p.stepSimulation()
                        time.sleep(0.016)
                        
                    # 3. 吸着ハンドをONにする (拘束を作成)
                    # 吸着型モデル（アーム先端 link 6）とブロックを固定
                    # IKによってアーム先端(link 6)がわずかに回転していても、ブロックがワールド座標系に対して
                    # 真っ直ぐ（平行）な状態を維持して吸い付くように、相対的な回転差分を計算して拘束します。
                    link_state = p.getLinkState(robotId, 6)
                    link_pos = link_state[4] # link world position
                    link_orn = link_state[5] # link world orientation
                    block_pos, block_orn = p.getBasePositionAndOrientation(block_id)
                    
                    # リンク座標からワールド座標への変換の逆変換を計算
                    inv_link_pos, inv_link_orn = p.invertTransform(link_pos, link_orn)
                    # それをブロックのワールド座標にかけることで、リンク座標系から見たブロックの相対位置・姿勢を求める
                    rel_pos, rel_orn = p.multiplyTransforms(inv_link_pos, inv_link_orn, block_pos, block_orn)
                    
                    suction_constraint = p.createConstraint(
                        parentBodyUniqueId=robotId,
                        parentLinkIndex=6, # アーム先端(エンドエフェクタ)
                        childBodyUniqueId=block_id,
                        childLinkIndex=-1, # base link
                        jointType=p.JOINT_FIXED,
                        jointAxis=[0, 0, 0],
                        parentFramePosition=[0, 0, 0.04], # 先端からのオフセット
                        childFramePosition=[0, 0, 0],
                        parentFrameOrientation=rel_orn, # 先端に対するブロックの相対的な姿勢
                        childFrameOrientation=[0, 0, 0, 1] # ブロック側はそのままローカルのまま
                    )
                    
                    print(f"[{idx+1}/3] 吸着完了。持ち上げて配置場所へ移動中...")
                    
                    # 4. 上空(Z=0.4)へ大きく持ち上げる。
                    move_arm_to_xyz([bx, by, 0.4])
                    for _ in range(30):
                        p.stepSimulation()
                        time.sleep(0.016)
                        
                    # 5. 配置場所を決定し、そこへ移動
                    # 色が黒ならY=0.1, 白ならY=-0.1
                    place_y = 0.1 if detected_color == "black" else -0.1
                    
                    move_arm_to_xyz([bx, place_y, 0.4])
                    for _ in range(40): # 遠いので少し移動待機時間を長めにする
                        p.stepSimulation()
                        time.sleep(0.016)
                        
                    # 6. 配置場所(Z=0.075)へ下降
                    # 床(Z=0.05)に当たるギリギリまで下げてから離すことで転がりを防止
                    move_arm_to_xyz([bx, place_y, 0.075])
                    for _ in range(20):
                        p.stepSimulation()
                        time.sleep(0.016)
                        
                    # 7. 吸着をOFFにして離す (拘束を削除)
                    print(f"[{idx+1}/3] ブロックを接地させ、吸着を解除します。")
                    p.removeConstraint(suction_constraint)
                    control_gripper(open_gripper=True)
                    
                    # 完全に離れて安定するまで待つ
                    for _ in range(30):
                        p.stepSimulation()
                        time.sleep(0.016)
                        
                    # 8. アームを少し上げる（退避）
                    move_arm_to_xyz([bx, place_y, 0.3])
                    for _ in range(20):
                        p.stepSimulation()
                        time.sleep(0.016)

                # -----------------------------------------------------------------
                print("Pick&Place動作完了。初期姿勢へ戻ります...")
                
                # 帰る前に再度安全な高さへ退避
                current_pos = p.getLinkState(robotId, 6)[0]
                move_arm_to_xyz([current_pos[0], current_pos[1], 0.4])
                for _ in range(20):
                    p.stepSimulation()
                    time.sleep(0.016)
                
                # 最後にHomeポジション(初期姿勢)に戻る
                home_positions = [0, 0, 0, -1.57, 0, 1.57, 0]
                for i in range(7):
                    p.setJointMotorControl2(robotId, i, p.POSITION_CONTROL, targetPosition=home_positions[i], force=200)
                for _ in range(30):
                    p.stepSimulation()
                    time.sleep(0.016)
                    
                print("シーケンス完了。")
                
                # 完了したらステータスを「完了(2)」にして指令をリセット
                list(plc.write(['Robot_Status=2', 'Robot_Cmd=0']))

        except Exception as e:
            # cpppoサーバーが立ち上がっていない場合などのエラー回避
            print(f"PLC通信待機中... ({e})")
            time.sleep(1)

        # 常に画面を更新
        p.stepSimulation()
        time.sleep(0.033)
