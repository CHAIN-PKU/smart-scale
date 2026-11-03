/**
  ******************************************************************************
  * @file    key.h
  * @brief   本地按键：去皮、保存、清单、清空。
  ******************************************************************************
  */

#ifndef __KEY_H
#define __KEY_H

#include "stm32f1xx_hal.h"

void    Key_Init(void);

/* 消抖后，在"按下"的那一刻返回 1（读一次就自动清掉，不会重复触发） */
uint8_t Key_TarePressed(void);
uint8_t Key_SavePressed(void);
uint8_t Key_ReceiptPressed(void);
uint8_t Key_ClearPressed(void);

#endif /* __KEY_H */
