from cpppo.server.enip.get_attribute import proxy_simple
import os
import time
import logging

# cpppoの通信ログを詳細(DEBUGレベル)に出力させる設定
logging.basicConfig(level=logging.DEBUG)

PLC_IP = os.environ.get('PLC_IP', '127.0.0.1')

print("MESシステム起動。PLCに接続します...")
try:
    with proxy_simple(PLC_IP) as plc:
        # 3つのブロックの座標リストをもって順に指示を出す
        targets = [
            (0.615, 0.0),
            (0.515, 0.0),
            (0.415, 0.0)
        ]
        
        for idx, (tx, ty) in enumerate(targets):
            print(f"[{idx+1}/3] 座標 ({tx}, {ty}) へのPick指令を送信します...")
            
            # 積み木の目標座標を書き込む
            list(plc.write([f'Target_X={tx}', f'Target_Y={ty}']))
            
            # Pick指令(1)を書き込む
            list(plc.write(['Robot_Cmd=1']))
            
            # ステータスが完了(2)になるまで監視（ポーリング）
            while True:
                try:
                    status_data = list(plc.read(['Robot_Status']))
                    status = status_data[0][0] if status_data and status_data[0] else 0
                except Exception:
                    status = 0
                    
                if status == 2:
                    print(f"[{idx+1}/3] ロボットの完了ステータスを受信しました。")
                    # ステータスを待機(0)に戻す
                    list(plc.write(['Robot_Status=0']))
                    break
                time.sleep(0.5)
            
            # 次の処理へ行く前に少し待機
            time.sleep(1.0)
            
        print("すべてのMESタスクが完了しました！")
except Exception as e:
    print(f"通信エラー: PLC(cpppo)が起動しているか確認してください。詳細: {e}")
