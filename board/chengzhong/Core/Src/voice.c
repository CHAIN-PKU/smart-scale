/**
  ******************************************************************************
  * @file    voice.c
  * @brief   CN-TTS 模块：走 USART2，9600 8N1，直接发 GBK 文本。
  *
  *          GBK 字节是用 PC 上的 Python 算好写死的（"香蕉".encode("gbk") 等），
  *          运行时不查码表。数字和标点走 ASCII（GBK 兼容 ASCII）。
  ******************************************************************************
  */

#include "voice.h"
#include "main.h"
#include "config.h"
#include "protocol.h"
#include <stdio.h>
#include <string.h>

UART_HandleTypeDef huart2;

/* 欢迎使用智能电子秤 */
static const uint8_t GBK_HELLO[] =
{
    0xBB, 0xB6, 0xD3, 0xAD, 0xCA, 0xB9, 0xD3, 0xC3, 0xD6, 0xC7,
    0xC4, 0xDC, 0xB5, 0xE7, 0xD7, 0xD3, 0xB3, 0xD3
};

static const uint8_t GBK_BANANA[] = { 0xCF, 0xE3, 0xBD, 0xB6 };   /* 香蕉 */
static const uint8_t GBK_APPLE[]  = { 0xC6, 0xBB, 0xB9, 0xFB };   /* 苹果 */
static const uint8_t GBK_ORANGE[] = { 0xB3, 0xC8, 0xD7, 0xD3 };   /* 橙子 */
static const uint8_t GBK_GRAPE[]  = { 0xC6, 0xCF, 0xCC, 0xD1 };   /* 葡萄 */
static const uint8_t GBK_KE[]     = { 0xBF, 0xCB };               /* 克 */
static const uint8_t GBK_YUAN[]   = { 0xD4, 0xAA };               /* 元 */
static const uint8_t GBK_COMMA[]  = { 0xA3, 0xAC };               /* ， */

/* 数字读法：把 326.4 念成"三百二十六点四"，而不是"三二六" */
static const uint8_t GBK_DIGIT[10][2] =
{
    { 0xC1, 0xE3 },   /* 零 */
    { 0xD2, 0xBB },   /* 一 */
    { 0xB6, 0xFE },   /* 二 */
    { 0xC8, 0xFD },   /* 三 */
    { 0xCB, 0xC4 },   /* 四 */
    { 0xCE, 0xE5 },   /* 五 */
    { 0xC1, 0xF9 },   /* 六 */
    { 0xC6, 0xDF },   /* 七 */
    { 0xB0, 0xCB },   /* 八 */
    { 0xBE, 0xC5 }    /* 九 */
};
static const uint8_t GBK_SHI[]    = { 0xCA, 0xAE };               /* 十 */
static const uint8_t GBK_BAI[]    = { 0xB0, 0xD9 };               /* 百 */
static const uint8_t GBK_QIAN[]   = { 0xC7, 0xA7 };               /* 千 */
static const uint8_t GBK_DIAN[]   = { 0xB5, 0xE3 };               /* 点 */
static const uint8_t GBK_FU[]     = { 0xB8, 0xBA };               /* 负 */

/**
  * @brief  往缓冲区里追加一个 GBK 汉字（2 字节）
  */
static uint16_t voice_put2(uint8_t *dst, uint16_t n, const uint8_t *b)
{
    dst[n]      = b[0];
    dst[n + 1U] = b[1];
    return (uint16_t)(n + 2U);
}

/**
  * @brief  整数转中文：326 -> 三百二十六
  */
static uint16_t voice_put_cn_int(uint8_t *dst, uint16_t value)
{
    static const uint16_t divs[4] = { 1000U, 100U, 10U, 1U };
    uint16_t n         = 0U;
    uint8_t  started   = 0U;
    uint8_t  need_zero = 0U;
    uint8_t  i;

    if (value > 9999U)
    {
        value = 9999U;
    }
    if (value == 0U)
    {
        return voice_put2(dst, 0U, GBK_DIGIT[0]);
    }

    for (i = 0U; i < 4U; i++)
    {
        uint8_t digit = (uint8_t)((value / divs[i]) % 10U);

        if (digit != 0U)
        {
            if (need_zero != 0U)
            {
                n = voice_put2(dst, n, GBK_DIGIT[0]);
                need_zero = 0U;
            }

            if ((started == 0U) && (i == 2U) && (digit == 1U))
            {
                /* 十几：念"十"，不是"一十" */
            }
            else
            {
                n = voice_put2(dst, n, GBK_DIGIT[digit]);
            }

            if (i == 0U)      { n = voice_put2(dst, n, GBK_QIAN); }
            else if (i == 1U) { n = voice_put2(dst, n, GBK_BAI); }
            else if (i == 2U) { n = voice_put2(dst, n, GBK_SHI); }
            else              { /* 个位不带单位 */ }

            started = 1U;
        }
        else if (started != 0U)
        {
            need_zero = 1U;
        }
    }

    return n;
}

/**
  * @brief  浮点数转中文：326.4 -> 三百二十六点四，3.92 -> 三点九二
  */
static uint16_t voice_put_cn_number(uint8_t *dst, float v, uint8_t decimals)
{
    uint16_t n     = 0U;
    int32_t  scale = (decimals == 2U) ? 100 : 10;
    int32_t  s     = (int32_t)(v * (float)scale + ((v >= 0.0f) ? 0.5f : -0.5f));
    int32_t  a     = (s < 0) ? -s : s;
    int32_t  ip    = a / scale;
    int32_t  fp    = a % scale;

    if (s < 0)
    {
        n = voice_put2(dst, n, GBK_FU);
    }

    n = (uint16_t)(n + voice_put_cn_int(&dst[n], (uint16_t)ip));

    /* 小数部分是 0 就不念"点零"：12.00 -> 十二元，5000.0 -> 五千克 */
    if ((decimals >= 1U) && (fp != 0))
    {
        n = voice_put2(dst, n, GBK_DIAN);

        if (decimals == 2U)
        {
            n = voice_put2(dst, n, GBK_DIGIT[(fp / 10) % 10]);
            n = voice_put2(dst, n, GBK_DIGIT[fp % 10]);
        }
        else
        {
            n = voice_put2(dst, n, GBK_DIGIT[fp % 10]);
        }
    }

    return n;
}

/**
  * @brief  商品英文名 -> 中文名的 GBK 字节
  */
static const uint8_t *voice_name_lookup(const char *product, uint8_t *len)
{
    *len = 0U;

    if (product == NULL)
    {
        return NULL;
    }
    if (strcmp(product, "banana") == 0)
    {
        *len = (uint8_t)sizeof(GBK_BANANA);
        return GBK_BANANA;
    }
    if (strcmp(product, "apple") == 0)
    {
        *len = (uint8_t)sizeof(GBK_APPLE);
        return GBK_APPLE;
    }
    if (strcmp(product, "orange") == 0)
    {
        *len = (uint8_t)sizeof(GBK_ORANGE);
        return GBK_ORANGE;
    }
    if (strcmp(product, "grape") == 0)
    {
        *len = (uint8_t)sizeof(GBK_GRAPE);
        return GBK_GRAPE;
    }
    return NULL;
}

void Voice_Init(void)
{
    huart2.Instance          = USART2;
    huart2.Init.BaudRate     = 9600U;
    huart2.Init.WordLength   = UART_WORDLENGTH_8B;
    huart2.Init.StopBits     = UART_STOPBITS_1;
    huart2.Init.Parity       = UART_PARITY_NONE;
    huart2.Init.Mode         = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;

    if (HAL_UART_Init(&huart2) != HAL_OK)
    {
        Error_Handler();
    }
}

void Voice_Say(const uint8_t *data, uint16_t len)
{
    if ((data == NULL) || (len == 0U))
    {
        return;
    }
    (void)HAL_UART_Transmit(&huart2, (uint8_t *)data, len, 500U);
}

void Voice_SayTest(void)
{
    char buf[96];
    int  p = 0;
    uint16_t i;

    p += sprintf(buf + p, "VOICE TX(%u):", (unsigned)sizeof(GBK_HELLO));
    for (i = 0U; (i < sizeof(GBK_HELLO)) && (p < 78); i++)
    {
        p += sprintf(buf + p, " %02X", GBK_HELLO[i]);
    }
    Proto_SendDebugLine(buf);

    Voice_Say(GBK_HELLO, (uint16_t)sizeof(GBK_HELLO));
}

/**
  * @brief  只念重量：三百二十六点四克
  */
void Voice_SayWeight(float weight_g)
{
    uint8_t  buf[48];
    uint16_t n = 0U;

    n = voice_put_cn_number(&buf[n], weight_g, 1U);

    memcpy(&buf[n], GBK_KE, sizeof(GBK_KE));
    n = (uint16_t)(n + sizeof(GBK_KE));

    Proto_SendDebugLine("VOICE: weight sentence");
    Voice_Say(buf, n);
}

/**
  * @brief  调试用：把模块 TX 回传的内容打到主串口
  *         模块会回 TTS-V... / Playing / End
  */
void Voice_Poll(void)
{
    uint8_t raw[16];
    uint8_t n = 0U;
    char    buf[96];
    int     p = 0;
    uint8_t i;

    while ((__HAL_UART_GET_FLAG(&huart2, UART_FLAG_RXNE) != RESET) &&
           (n < (uint8_t)sizeof(raw)))
    {
        raw[n++] = (uint8_t)(huart2.Instance->DR & 0xFFU);
    }

    if (n > 0U)
    {
        p += sprintf(buf + p, "VOICE RX(%u):", (unsigned)n);
        for (i = 0U; i < n; i++)
        {
            p += sprintf(buf + p, " %02X", raw[i]);
        }
        Proto_SendDebugLine(buf);
    }
}

void Voice_SetVolume(uint8_t vol)
{
    uint8_t buf[8];

    if (vol < 1U) { vol = 1U; }
    if (vol > 4U) { vol = 4U; }
    (void)sprintf((char *)buf, "<V>%u", (unsigned)vol);
    Voice_Say(buf, (uint16_t)strlen((char *)buf));
}

void Voice_SetSpeed(uint8_t spd)
{
    uint8_t buf[8];

    if (spd < 1U) { spd = 1U; }
    if (spd > 3U) { spd = 3U; }
    (void)sprintf((char *)buf, "<S>%u", (unsigned)spd);
    Voice_Say(buf, (uint16_t)strlen((char *)buf));
}

/**
  * @brief  关闭模块自己的上电提示音（<I>0）。
  *         上电默认音量为 4 级，那一声提示音电流最大，容易把板子的 5V 拉垮，
  *         所以在它响之前先把提示音关掉。
  */
void Voice_DisablePrompt(void)
{
    static const uint8_t cmd[] = { '<', 'I', '>', '0' };

    Voice_Say(cmd, (uint16_t)sizeof(cmd));
}

/**
  * @brief  念一句：商品名 + 克数 + 克 + 金额 + 元
  *         例如：香蕉，326.4 克，3.92 元（热量和碳水不念）
  */
void Voice_SayPrice(const char *product_ascii, float weight_g, float price)
{
    uint8_t        buf[96];
    uint16_t       n = 0U;
    uint8_t        name_len = 0U;
    const uint8_t *name;
    const char    *p;

    name = voice_name_lookup(product_ascii, &name_len);
    if (name != NULL)
    {
        memcpy(&buf[n], name, name_len);
        n = (uint16_t)(n + name_len);
    }
    else
    {
        /* 不认识的商品：直接把英文名念出来（模块支持英文字母） */
        p = product_ascii;
        while ((p != NULL) && (*p != '\0') && (n < 24U))
        {
            buf[n++] = (uint8_t)(*p++);
        }
    }

    memcpy(&buf[n], GBK_COMMA, sizeof(GBK_COMMA));
    n = (uint16_t)(n + sizeof(GBK_COMMA));

    n = (uint16_t)(n + voice_put_cn_number(&buf[n], weight_g, 1U));

    memcpy(&buf[n], GBK_KE, sizeof(GBK_KE));
    n = (uint16_t)(n + sizeof(GBK_KE));

    memcpy(&buf[n], GBK_COMMA, sizeof(GBK_COMMA));
    n = (uint16_t)(n + sizeof(GBK_COMMA));

    n = (uint16_t)(n + voice_put_cn_number(&buf[n], price, 2U));

    memcpy(&buf[n], GBK_YUAN, sizeof(GBK_YUAN));
    n = (uint16_t)(n + sizeof(GBK_YUAN));

    Voice_Say(buf, n);
}

void Voice_SayTared(void)
{
    static const uint8_t gbk[] = { 0xD2, 0xD1, 0xC8, 0xA5, 0xC6, 0xA4 }; /* 已去皮 */

    Voice_Say(gbk, (uint16_t)sizeof(gbk));
}

void Voice_SaySaved(void)
{
    static const uint8_t gbk[] = { 0xD2, 0xD1, 0xB1, 0xA3, 0xB4, 0xE6 }; /* 已保存 */

    Voice_Say(gbk, (uint16_t)sizeof(gbk));
}

void Voice_SayCleared(void)
{
    static const uint8_t gbk[] = { 0xD2, 0xD1, 0xC7, 0xE5, 0xBF, 0xD5 }; /* 已清空 */

    Voice_Say(gbk, (uint16_t)sizeof(gbk));
}

void Voice_SayReset(void)
{
    static const uint8_t gbk[] = { 0xD2, 0xD1, 0xB8, 0xB4, 0xCE, 0xBB }; /* 已复位 */

    Voice_Say(gbk, (uint16_t)sizeof(gbk));
}
