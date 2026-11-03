/**
  ******************************************************************************
  * @file    scale.h
  * @brief   称重本体：滤波、换算成克、八个状态切换、去皮。
  ******************************************************************************
  */

#ifndef __SCALE_H
#define __SCALE_H

#include "stm32f1xx_hal.h"

/* 八个状态，名字和文档里给的一模一样，别改 */
typedef enum
{
  SCALE_BOOT = 0,
  SCALE_READY,
  SCALE_ZERO,
  SCALE_WEIGHT_CHANGED,
  SCALE_WEIGHT_STABLE,
  SCALE_WEIGHT_REMOVED,
  SCALE_OVERLOAD,
  SCALE_ERROR
} ScaleState_t;

void          Scale_Init(void);              /* 初始化 HX711，并报一次 READY */
void          Scale_Loop(void);              /* 主循环里反复调用 */

ScaleState_t  Scale_GetState(void);
const char   *Scale_StateName(ScaleState_t st);
void          Scale_SendCurrentStatus(void); /* 把当前状态再报一次 */

float         Scale_GetWeightG(void);        /* 当前净重（克） */
float         Scale_GetTareG(void);          /* 当前减掉的皮重（克） */
uint8_t       Scale_IsStable(void);          /* 1 = 读数稳住了 */

uint8_t       Scale_Tare(void);              /* 去皮：1 = 成功，0 = 失败（零点不变） */

#endif /* __SCALE_H */
