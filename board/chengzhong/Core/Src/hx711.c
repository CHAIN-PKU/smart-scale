/**
  ******************************************************************************
  * @file    hx711.c
  * @brief   HX711 读数。
  *          HX711 的时序很简单：DT 变低表示数据好了，然后 SCK 打 24 个脉冲
  *          把 24 位数据读出来，再补 1 个脉冲选择 通道A / 增益128。
  *          和参考工程不同的是：这里所有等待都有超时，传感器没接好不会卡死。
  ******************************************************************************
  */

#include "hx711.h"
#include "config.h"

static void hx711_delay(void);
static void hx711_enable_port_clock(GPIO_TypeDef *port);

/**
  * @brief  SCK 高/低电平的持续时间。
  *         HX711 要求 SCK 高电平、低电平都不少于 0.2us，慢一点没关系，
  *         只要 25 个脉冲在 60ms 内打完就行。这里的循环在 36MHz/72MHz 下
  *         大约 1~2us，绰绰有余。
  */
static void hx711_delay(void)
{
    volatile uint32_t i;

    for (i = 0U; i < 20U; i++)
    {
        __NOP();
    }
}

/**
  * @brief  按端口自动打开对应 GPIO 的时钟。
  *         这样你改 config.h 里的端口时，不用再惦记时钟那行。
  */
static void hx711_enable_port_clock(GPIO_TypeDef *port)
{
    if (port == GPIOA)
    {
        __HAL_RCC_GPIOA_CLK_ENABLE();
    }
    else if (port == GPIOB)
    {
        __HAL_RCC_GPIOB_CLK_ENABLE();
    }
    else if (port == GPIOC)
    {
        __HAL_RCC_GPIOC_CLK_ENABLE();
    }
    else if (port == GPIOD)
    {
        __HAL_RCC_GPIOD_CLK_ENABLE();
    }
    else if (port == GPIOE)
    {
        __HAL_RCC_GPIOE_CLK_ENABLE();
    }
    else
    {
        /* 其它端口不用管 */
    }
}

/**
  * @brief  初始化 HX711 用到的两个引脚。
  */
void HX711_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    hx711_enable_port_clock(HX711_SCK_PORT);
    hx711_enable_port_clock(HX711_DT_PORT);

    /* SCK：单片机输出，平时拉低 */
    HAL_GPIO_WritePin(HX711_SCK_PORT, HX711_SCK_PIN, GPIO_PIN_RESET);
    GPIO_InitStruct.Pin   = HX711_SCK_PIN;
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull  = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(HX711_SCK_PORT, &GPIO_InitStruct);

    /* DT：单片机输入。开上拉，这样 HX711 没接的时候读到的是高电平，
     *     也就是"一直没数据"，最后会变成 ERROR，而不是随机跳数。 */
    GPIO_InitStruct.Pin  = HX711_DT_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(HX711_DT_PORT, &GPIO_InitStruct);
}

/**
  * @brief  HX711 是否已经把数据准备好（DT 被拉低）
  */
uint8_t HX711_IsReady(void)
{
    return (HAL_GPIO_ReadPin(HX711_DT_PORT, HX711_DT_PIN) == GPIO_PIN_RESET) ? 1U : 0U;
}

/**
  * @brief  读一次原始数据（24 位有符号）
  * @param  raw  读到的原始值
  * @retval 0 = 成功，-1 = 超时或者参数不对
  */
int8_t HX711_ReadRaw(int32_t *raw)
{
    uint32_t value = 0U;
    uint32_t start;
    uint8_t  i;

    if (raw == NULL)
    {
        return -1;
    }

    /* 等 DT 变低。超过 HX711_TIMEOUT_MS 还没等到就报失败，
     * 交给上层切到 ERROR，绝不在这里死等。 */
    start = HAL_GetTick();
    while (HAL_GPIO_ReadPin(HX711_DT_PORT, HX711_DT_PIN) == GPIO_PIN_SET)
    {
        if ((HAL_GetTick() - start) >= HX711_TIMEOUT_MS)
        {
            return -1;
        }
    }

    /* 24 位数据，最高位先出来 */
    for (i = 0U; i < 24U; i++)
    {
        HAL_GPIO_WritePin(HX711_SCK_PORT, HX711_SCK_PIN, GPIO_PIN_SET);
        hx711_delay();

        value <<= 1;
        if (HAL_GPIO_ReadPin(HX711_DT_PORT, HX711_DT_PIN) == GPIO_PIN_SET)
        {
            value |= 1U;
        }

        HAL_GPIO_WritePin(HX711_SCK_PORT, HX711_SCK_PIN, GPIO_PIN_RESET);
        hx711_delay();
    }

    /* 第 25 个脉冲：告诉 HX711 下一次还走 通道A / 增益128 */
    HAL_GPIO_WritePin(HX711_SCK_PORT, HX711_SCK_PIN, GPIO_PIN_SET);
    hx711_delay();
    HAL_GPIO_WritePin(HX711_SCK_PORT, HX711_SCK_PIN, GPIO_PIN_RESET);
    hx711_delay();

    /* 24 位补码补成 32 位有符号数 */
    if ((value & 0x00800000U) != 0U)
    {
        value |= 0xFF000000U;
    }

    *raw = (int32_t)value;
    return 0;
}
