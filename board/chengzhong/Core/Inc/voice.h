/**
  ******************************************************************************
  * @file    voice.h
  * @brief   CN-TTS 中文语音合成模块（USART2，9600 8N1）
  *          说明书：直接发 GBK 文本，模块自己合成语音（"发什么报什么"）
  ******************************************************************************
  */

#ifndef __VOICE_H
#define __VOICE_H

#include "stm32f1xx_hal.h"

void Voice_Init(void);
void Voice_Say(const uint8_t *data, uint16_t len);      /* 发 GBK/ASCII 字节去念 */
void Voice_Poll(void);                                   /* 把模块回传的内容打到串口上（调试用） */
void Voice_SayTest(void);                                /* 上电自检用：念一句固定话 */
void Voice_SayPrice(const char *product_ascii, float weight_g, float price);
void Voice_SayWeight(float weight_g);                    /* 只念"三百二十六点四克" */
void Voice_SetVolume(uint8_t vol);                       /* 1 ~ 4，默认 4 */
void Voice_SetSpeed(uint8_t spd);                        /* 1 ~ 3，默认 2 */
void Voice_DisablePrompt(void);                          /* 关闭模块上电提示音 */

#endif /* __VOICE_H */
