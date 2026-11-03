/**
  ******************************************************************************
  * @file    protocol.h
  * @brief   串口协议：一行一个 JSON。
  *          发出去：status / weight / ack
  *          收进来：command(tare) / display_result
  ******************************************************************************
  */

#ifndef __PROTOCOL_H
#define __PROTOCOL_H

#include "stm32f1xx_hal.h"

void Proto_Init(void);
void Proto_Poll(void);                                   /* 主循环里反复调用，处理收到的行 */

void Proto_SendStatus(const char *state);                /* {"type":"status",...} */
/* status: "ok" / "overload" / "error" —— 按软件同学的要求带在 weight 行里 */
void Proto_SendWeight(float weight_g, uint8_t stable, float tare_g, const char *status);
void Proto_SendTareAck(uint8_t ok);
void Proto_SendCommand(const char *command);
uint8_t Proto_PressTare(void);                           /* 成功才去皮、播报并回到重量屏 */
void Proto_PressSave(void);                             /* 保存，并立刻画出已保存 */
void Proto_PressClear(void);                            /* 清空，并立刻画出已清空 */
void Proto_PressReceipt(void);                          /* 向电脑要清单，回来后再画 */
void Proto_PressReset(void);                            /* 只播报已复位 */
void Proto_SendRawDebug(int32_t raw, float grams);       /* 标定用的非 JSON 调试行 */
void Proto_SendDebugLine(const char *text);              /* 任意一行 "# ..." 调试输出 */
void Proto_SendLine(const char *s);                       /* 原样发一行给电脑，用于 WiFi 查询 */

void Proto_RxByteFromIsr(uint8_t b);                     /* 串口中断里调用 */
void Proto_Usart1Isr(void);                              /* USART1 中断服务，由 stm32f1xx_it.c 调用 */

/* 最近一次收到的显示结果（电脑算完钱发过来的），以后接屏幕就用这里的数据 */
const char *Proto_GetDisplayProduct(void);
float       Proto_GetDisplayWeightG(void);
float       Proto_GetDisplayPrice(void);

#endif /* __PROTOCOL_H */
