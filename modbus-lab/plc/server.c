#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <modbus.h>

int main(int argc, char *argv[])
{
    modbus_t *ctx;
    modbus_mapping_t *mb_mapping;
    int s = -1;
    uint8_t *query;

    /*
     * Modbus TCP 接続の準備
     * デフォルトでは 502 番ポートで待機。
     */
    ctx = modbus_new_tcp("0.0.0.0", 502);
    if (ctx == NULL) {
        fprintf(stderr, "Unable to allocate libmodbus context\n");
        return -1;
    }

    query = malloc(MODBUS_TCP_MAX_ADU_LENGTH);

    /*
     * データのマッピング（確保）
     * 100個のコイル、100個のディスクリート入力、
     * 100個の保持レジスタ、100個の入力レジスタを確保します
     */
    mb_mapping = modbus_mapping_new(100, 100, 100, 100);
    if (mb_mapping == NULL) {
        fprintf(stderr, "Failed to allocate the mapping: %s\n", modbus_strerror(errno));
        modbus_free(ctx);
        return -1;
    }

    /*
     * Modbus Register Definition for BPCS PLC
     */

    // 1. Input Registers (Read-only Analog Values - PVs/Deviations)
    mb_mapping->tab_input_registers[0] = 2500; // IR 0: LNG受入流量 (PV)
    mb_mapping->tab_input_registers[1] = 50;   // IR 1: LNGタンク 液位 (PV)
    mb_mapping->tab_input_registers[2] = 100;  // IR 2: LNGタンク 圧力 (PV)
    mb_mapping->tab_input_registers[3] = 1000; // IR 3: ポンプ送出流量 (PV)
    mb_mapping->tab_input_registers[4] = 0;    // IR 4: PID制御偏差

    // 2. Holding Registers (Read/Write Analog Values - SPs/OPs)
    mb_mapping->tab_registers[0] = 50;   // HR 0: 流量制御弁 (FCV) 開度 (OP)
    mb_mapping->tab_registers[1] = 2500; // HR 1: LNG受入流量 設定値 (SP)
    mb_mapping->tab_registers[2] = 50;   // HR 2: VFD 周波数/回転数 (OP)

    // 3. Discrete Inputs (Read-only Boolean Values - Alarms/States)
    mb_mapping->tab_input_bits[0] = 0; // DI 0: 受入配管 高流量警報 (HA)
    mb_mapping->tab_input_bits[1] = 0; // DI 1: 受入配管 低流量警報 (LA)
    mb_mapping->tab_input_bits[2] = 0; // DI 2: LNGタンク 高々液位警報 (HH)
    mb_mapping->tab_input_bits[3] = 0; // DI 3: LNGタンク 高液位警報 (HA)
    mb_mapping->tab_input_bits[4] = 0; // DI 4: LNGタンク 低々液位警報 (LLA)
    mb_mapping->tab_input_bits[5] = 0; // DI 5: LNGタンク 高圧警報 (HA)
    mb_mapping->tab_input_bits[6] = 0; // DI 6: LNGタンク 低圧警報 (LA)
    mb_mapping->tab_input_bits[7] = 1; // DI 7: BOGコンプレッサー 運転状態
    mb_mapping->tab_input_bits[8] = 1; // DI 8: インタンクポンプ 運転状態
    mb_mapping->tab_input_bits[9] = 0; // DI 9: VFD 故障警報
    mb_mapping->tab_input_bits[10] = 1; // DI 10: PLC自己診断状態
    mb_mapping->tab_input_bits[11] = 1; // DI 11: フィールド機器通信状態

    /* リッスン開始 */
    printf("Starting Modbus TCP server on port 502...\n");
    s = modbus_tcp_listen(ctx, 1);
    
    while (1) {
        printf("Waiting for connection...\n");
        modbus_tcp_accept(ctx, &s);
        printf("Client connected.\n");

        for (;;) {
            int rc = modbus_receive(ctx, query);
            if (rc > 0) {
                /* リクエストを処理して自動的に返信 */
                modbus_reply(ctx, query, rc, mb_mapping);
                
                /*
                 * ここに、レジスタが書き換えられた時のシミュレーションロジック
                 * （例えばバルブ開閉状態に応じて圧力を変動させるなど）
                 * を追記していくことができます。
                 */
            } else if (rc == -1) {
                /* コネクション切れ・エラー */
                printf("Connection closed by client or error.\n");
                break;
            }
        }
    }

    printf("Server stopped.\n");
    modbus_mapping_free(mb_mapping);
    modbus_close(ctx);
    modbus_free(ctx);
    free(query);

    return 0;
}
