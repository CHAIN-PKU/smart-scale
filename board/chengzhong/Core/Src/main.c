/**
  ******************************************************************************
  * @file    main.c
  * @brief   智能电子秤 - 称重固件（STM32F107VC + HAL）
  *
  *          这块板子只负责一件事：把重量称准，按协议从串口报给电脑。
  *          认商品、查单价、算钱，全是电脑那边做的，这里不管。
  *
  *          上电顺序：初始化 -> 报 BOOT -> HX711 就绪 -> 报 READY -> 开始称重。
  *          上电不做自动去皮。
  *          要改接线、量程、标定系数，只改 Core/Inc/config.h 就行。
  ******************************************************************************
  */

#include "main.h"
#include "config.h"
#include "hx711.h"
#include "key.h"
#include "voice.h"
#include "protocol.h"
#include "scale.h"
#include "tft.h"
#include "wifi.h"

UART_HandleTypeDef huart1;

static void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART1_UART_Init(void);

int main(void)
{
    /* 1. HAL 初始化：开中断、启动 1ms 滴答 */
    HAL_Init();

    /* 2. 配主频 */
    SystemClock_Config();

    /* 3. 引脚和串口 */
    MX_GPIO_Init();
    MX_USART1_UART_Init();

    /* 4. 协议层准备好，开始收电脑发来的命令。
     *    先报 BOOT，再开 WiFi。WiFi 串口如果卡住，电脑上仍能看到这一行。 */
    Proto_Init();
    Proto_SendStatus("BOOT");
    Wifi_Init();

    /* 6. HX711 初始化，能读了就报 READY，然后开始称重 */
    Scale_Init();

    /* 7. 本地去皮按键 */
    Key_Init();

    /* 8. 语音模块（CN-TTS，USART2 9600 8N1） */
    Voice_Init();

    /* 9. TFT 屏（ILI9341，SPI2） */
    TFT_Init();
    TFT_PlaySplash(0U);

    /* 等语音模块启动完，设成正式参数；开屏页继续等待 K1。 */
    HAL_Delay(2000U);
    Voice_DisablePrompt();
    HAL_Delay(300U);
    Voice_SetVolume(VOICE_VOLUME);
    HAL_Delay(300U);
    Voice_SetSpeed(VOICE_SPEED);
    HAL_Delay(300U);

#if (VOICE_TEST_SENTENCE > 0)
    Voice_SayTest();
#endif

    /* 按 K1 后才离开开屏页；这次按键同时完成一次正式去皮。 */
    while (Key_TarePressed() == 0U)
    {
        Proto_Poll();
        Wifi_Poll();
        HAL_Delay(10U);
    }
    {
        uint8_t tare_ok = Scale_Tare();

        if (tare_ok != 0U)
        {
            Scale_SendCurrentStatus();
        }
        TFT_PlaySplash(tare_ok);
        TFT_ShowWeight(0.0f);
    }

    while (1)
    {
        Proto_Poll();   /* 收命令：去皮、显示结果 */
        Wifi_Poll();

        if (Key_SavePressed() != 0U)
        {
            Proto_SendCommand("save");
        }
        if (Key_ReceiptPressed() != 0U)
        {
            Proto_SendCommand("receipt");
        }
        if (Key_ClearPressed() != 0U)
        {
            Proto_SendCommand("clear");
        }

        /* 板子上的去皮键被按下：和收到电脑命令做同一件事 */
        if (Key_TarePressed() != 0U)
        {
            if (Scale_Tare() != 0U)
            {
                Scale_SendCurrentStatus();   /* 成功就报一次 ZERO */
            }
        }

        Scale_Loop();   /* 有新的重量样本就处理、就往外报 */
    }
}

/**
  * @brief  系统时钟配置
  *
  *          默认用内部 HSI：8MHz / 2 x 9 = 36MHz。
  *          不依赖外部晶振，什么板子都能先跑起来。
  *
  *          如果板上确实有 8MHz 晶振，把 config.h 里的
  *          USE_HSE_8M_CLOCK 改成 1，就能跑到 72MHz。
  */
static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

#if (USE_HSE_8M_CLOCK == 1)
    /* ---------- 外部 8MHz 晶振：8MHz x 9 = 72MHz ---------- */
    RCC_OscInitStruct.OscillatorType      = RCC_OSCILLATORTYPE_HSE;
    RCC_OscInitStruct.HSEState            = RCC_HSE_ON;
    RCC_OscInitStruct.HSEPredivValue      = RCC_HSE_PREDIV_DIV1;
    RCC_OscInitStruct.Prediv1Source       = RCC_PREDIV1_SOURCE_HSE;
    RCC_OscInitStruct.PLL.PLLState        = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource       = RCC_PLLSOURCE_HSE;
    RCC_OscInitStruct.PLL.PLLMUL          = RCC_PLL_MUL9;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
        Error_Handler();
    }
#else
    /* ---------- 内部 HSI：8MHz / 2 x 9 = 36MHz ---------- */
    RCC_OscInitStruct.OscillatorType      = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSIState            = RCC_HSI_ON;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLState        = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource       = RCC_PLLSOURCE_HSI_DIV2;
    RCC_OscInitStruct.PLL.PLLMUL          = RCC_PLL_MUL9;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
        Error_Handler();
    }
#endif

    /* SYSCLK 走 PLL；APB1 二分频，APB2 一分频 */
    RCC_ClkInitStruct.ClockType      = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                                       RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
    {
        Error_Handler();
    }
}

/**
  * @brief  串口 1：115200，8 数据位，无校验，1 停止位（文档规定的）
  */
static void MX_USART1_UART_Init(void)
{
    huart1.Instance          = USART1;
    huart1.Init.BaudRate     = 115200U;
    huart1.Init.WordLength   = UART_WORDLENGTH_8B;
    huart1.Init.StopBits     = UART_STOPBITS_1;
    huart1.Init.Parity       = UART_PARITY_NONE;
    huart1.Init.Mode         = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;

    if (HAL_UART_Init(&huart1) != HAL_OK)
    {
        Error_Handler();
    }
}

/**
  * @brief  把用到的 GPIO 时钟打开。
  *         HX711 那两个脚的时钟在 hx711.c 里按端口自动开，这里只管串口这边。
  */
static void MX_GPIO_Init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
}

/**
  * @brief  出错就停在这里，方便用调试器看死在哪
  */
void Error_Handler(void)
{
    __disable_irq();
    while (1)
    {
    }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line)
{
    (void)file;
    (void)line;
    while (1)
    {
    }
}
#endif
