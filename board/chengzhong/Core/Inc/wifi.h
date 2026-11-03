/**
  ******************************************************************************
  * @file    wifi.h
  * @brief   ESP-01：自己开热点，把手机的查询交给电脑，再把回答送回手机。
  ******************************************************************************
  */

#ifndef __WIFI_H
#define __WIFI_H

#include "stm32f1xx_hal.h"

void Wifi_Init(void);
void Wifi_Poll(void);
void Wifi_OnPcLine(const char *line);
void Wifi_Uart4Isr(void);

#endif /* __WIFI_H */
