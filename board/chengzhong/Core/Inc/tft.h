/**
  ******************************************************************************
  * @file    tft.h
  * @brief   3.2 寸 TFT（ILI9341，SPI2 240x320）
  *
  *          接线与已经验证过的 QD-TFT 测试工程一致：
  *            VCC   -> 5V 或 3.3V
  *            GND   -> GND
  *            CS    -> PB11
  *            RESET -> PB12
  *            DC    -> PB10
  *            SDI   -> PB15 (SPI2_MOSI)
  *            SCK   -> PB13 (SPI2_SCK)
  *            LED   -> PB9
  *            SDO   -> PB14 (SPI2_MISO)
  *
  *          不占用：PA9/PA10（电脑串口）、PA2/PA3（语音）、PB0/PB1（HX711）
  ******************************************************************************
  */

#ifndef __TFT_H
#define __TFT_H

#include "stm32f1xx_hal.h"

#define TFT_CS_PORT      GPIOB
#define TFT_CS_PIN       GPIO_PIN_11
#define TFT_DC_PORT      GPIOB
#define TFT_DC_PIN       GPIO_PIN_10
#define TFT_RST_PORT     GPIOB
#define TFT_RST_PIN      GPIO_PIN_12
#define TFT_LED_PORT     GPIOB
#define TFT_LED_PIN      GPIO_PIN_9

#define TFT_W            240U
#define TFT_H            320U

#define TFT_BLACK        0x0000U
#define TFT_WHITE        0xFFFFU
#define TFT_RED          0xF800U
#define TFT_BLUE         0x001FU
#define TFT_GREEN        0x07E0U
#define TFT_GRAY         0x8410U

#define TFT_INFO_KCAL    0x01U
#define TFT_INFO_CARB    0x02U
#define TFT_INFO_FIBER   0x04U

#define TFT_RECEIPT_MAX_ITEMS 8U

typedef struct
{
    uint16_t n;
    char     product[20];
    float    price_per_kg;
    float    weight_g;
    float    price;
} TFT_ReceiptItem;

void TFT_Init(void);
void TFT_Fill(uint16_t color);
void TFT_ShowWeight(float weight_g);
void TFT_ShowResult(const char *product_ascii,
                    float price_per_kg,
                    float weight_g,
                    float price,
                    float kcal,
                    float carb_g,
                    float fiber_g,
                    uint8_t info_flags);
void TFT_ShowReceipt(const TFT_ReceiptItem *items, uint8_t count, float total);
void TFT_ShowSaved(void);
void TFT_ShowCleared(void);
void TFT_ShowLastPrice(void);
void TFT_PlaySplash(uint8_t tare_applied);

#endif /* __TFT_H */
