/**
  ******************************************************************************
  * @file    tft.c
  * @brief   ILI9341 3.2 寸屏驱动（SPI2，软件片选/数据命令脚）
  ******************************************************************************
  */

#include "tft.h"
#include "tft_font.h"
#include "protocol.h"
#include <stdio.h>
#include <string.h>

static SPI_HandleTypeDef hspi2;

typedef struct
{
    char     product[20];
    float    price_per_kg;
    float    weight_g;
    float    price;
    float    kcal;
    float    carb_g;
    float    fiber_g;
    uint8_t  info_flags;
    uint8_t  valid;
} TftLastPrice_t;

static TftLastPrice_t s_last_price;

/*---------------------------------------------------------------------------*/
/* 底层：命令 / 数据                                                          */
/*---------------------------------------------------------------------------*/

/* 与已验证的 QD-TFT 工程一致：每个命令/数据字节单独拉一次 CS。 */
static uint8_t tft_write_byte(uint8_t tx)
{
    uint8_t rx = 0U;

    (void)HAL_SPI_TransmitReceive(&hspi2, &tx, &rx, 1U, 100U);
    return rx;
}

static void tft_wr_reg(uint8_t cmd)
{
    HAL_GPIO_WritePin(TFT_CS_PORT, TFT_CS_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(TFT_DC_PORT, TFT_DC_PIN, GPIO_PIN_RESET);
    (void)tft_write_byte(cmd);
    HAL_GPIO_WritePin(TFT_CS_PORT, TFT_CS_PIN, GPIO_PIN_SET);
}

static void tft_wr_data(uint8_t data)
{
    HAL_GPIO_WritePin(TFT_CS_PORT, TFT_CS_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(TFT_DC_PORT, TFT_DC_PIN, GPIO_PIN_SET);
    (void)tft_write_byte(data);
    HAL_GPIO_WritePin(TFT_CS_PORT, TFT_CS_PIN, GPIO_PIN_SET);
}

static void tft_cmd(uint8_t cmd, const uint8_t *data, uint8_t len)
{
    uint8_t i;

    tft_wr_reg(cmd);
    for (i = 0U; i < len; i++)
    {
        tft_wr_data(data[i]);
    }
}

static void tft_set_window(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1)
{
    uint8_t b[4];

    b[0] = (uint8_t)(x0 >> 8); b[1] = (uint8_t)x0;
    b[2] = (uint8_t)(x1 >> 8); b[3] = (uint8_t)x1;
    tft_cmd(0x2AU, b, 4U);

    b[0] = (uint8_t)(y0 >> 8); b[1] = (uint8_t)y0;
    b[2] = (uint8_t)(y1 >> 8); b[3] = (uint8_t)y1;
    tft_cmd(0x2BU, b, 4U);

    tft_cmd(0x2CU, NULL, 0U);
}

/*---------------------------------------------------------------------------*/
/* 初始化                                                                     */
/*---------------------------------------------------------------------------*/

void TFT_Init(void)
{
    GPIO_InitTypeDef g = {0};

    static const uint8_t p_cf[] = { 0x00, 0xD9, 0x30 };
    static const uint8_t p_ed[] = { 0x64, 0x03, 0x12, 0x81 };
    static const uint8_t p_e8[] = { 0x85, 0x10, 0x7A };
    static const uint8_t p_cb[] = { 0x39, 0x2C, 0x00, 0x34, 0x02 };
    static const uint8_t p_f7[] = { 0x20 };
    static const uint8_t p_ea[] = { 0x00, 0x00 };
    static const uint8_t p_c0[] = { 0x1B };
    static const uint8_t p_c1[] = { 0x12 };
    static const uint8_t p_c5[] = { 0x26, 0x26 };
    static const uint8_t p_c7[] = { 0xB0 };
    static const uint8_t p_36[] = { 0x08 };          /* MADCTL：竖屏 */
    static const uint8_t p_3a[] = { 0x55 };          /* 16 位色 */
    static const uint8_t p_b1[] = { 0x00, 0x1A };
    static const uint8_t p_b6[] = { 0x0A, 0xA2 };
    static const uint8_t p_f2[] = { 0x00 };
    static const uint8_t p_26[] = { 0x01 };
    static const uint8_t p_e0[] = { 0x1F,0x24,0x24,0x0D,0x12,0x09,0x52,0xB7,
                                    0x3F,0x0C,0x15,0x06,0x0E,0x08,0x00 };
    static const uint8_t p_e1[] = { 0x00,0x1B,0x1B,0x02,0x0E,0x06,0x2E,0x48,
                                    0x3F,0x03,0x0A,0x09,0x31,0x37,0x1F };
    static const uint8_t p_full_y[] = { 0x00, 0x00, 0x01, 0x3F };
    static const uint8_t p_full_x[] = { 0x00, 0x00, 0x00, 0xEF };

    __HAL_RCC_SPI2_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    /* SCK = PB13, MOSI = PB15 */
    g.Pin   = GPIO_PIN_13 | GPIO_PIN_15;
    g.Mode  = GPIO_MODE_AF_PP;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOB, &g);

    /* MISO = PB14 */
    g.Pin  = GPIO_PIN_14;
    g.Mode = GPIO_MODE_INPUT;
    g.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOB, &g);

    /* CS = PB11, DC = PB10, RST = PB12, LED = PB9 */
    g.Pin   = TFT_CS_PIN | TFT_DC_PIN | TFT_RST_PIN | TFT_LED_PIN;
    g.Mode  = GPIO_MODE_OUTPUT_PP;
    g.Pull  = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOB, &g);

    HAL_GPIO_WritePin(TFT_CS_PORT, TFT_CS_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(TFT_DC_PORT, TFT_DC_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(TFT_RST_PORT, TFT_RST_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(TFT_LED_PORT, TFT_LED_PIN, GPIO_PIN_RESET);

    hspi2.Instance               = SPI2;
    hspi2.Init.Mode              = SPI_MODE_MASTER;
    hspi2.Init.Direction         = SPI_DIRECTION_2LINES;
    hspi2.Init.DataSize          = SPI_DATASIZE_8BIT;
    hspi2.Init.CLKPolarity       = SPI_POLARITY_LOW;
    hspi2.Init.CLKPhase          = SPI_PHASE_1EDGE;
    hspi2.Init.NSS               = SPI_NSS_SOFT;
    hspi2.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_2;   /* 与测试工程一致 */
    hspi2.Init.FirstBit          = SPI_FIRSTBIT_MSB;
    hspi2.Init.TIMode            = SPI_TIMODE_DISABLE;
    hspi2.Init.CRCCalculation    = SPI_CRCCALCULATION_DISABLE;
    hspi2.Init.CRCPolynomial     = 10U;
    (void)HAL_SPI_Init(&hspi2);

    /* 硬复位 */
    HAL_GPIO_WritePin(TFT_RST_PORT, TFT_RST_PIN, GPIO_PIN_RESET);
    HAL_Delay(100U);
    HAL_GPIO_WritePin(TFT_RST_PORT, TFT_RST_PIN, GPIO_PIN_SET);
    HAL_Delay(50U);

    /* 完全采用已验证工程里的 3.2 寸 ILI9341 初始化参数。 */
    tft_cmd(0xCFU, p_cf, sizeof(p_cf));
    tft_cmd(0xEDU, p_ed, sizeof(p_ed));
    tft_cmd(0xE8U, p_e8, sizeof(p_e8));
    tft_cmd(0xCBU, p_cb, sizeof(p_cb));
    tft_cmd(0xF7U, p_f7, sizeof(p_f7));
    tft_cmd(0xEAU, p_ea, sizeof(p_ea));
    tft_cmd(0xC0U, p_c0, sizeof(p_c0));
    tft_cmd(0xC1U, p_c1, sizeof(p_c1));
    tft_cmd(0xC5U, p_c5, sizeof(p_c5));
    tft_cmd(0xC7U, p_c7, sizeof(p_c7));
    tft_cmd(0x36U, p_36, sizeof(p_36));
    tft_cmd(0x3AU, p_3a, sizeof(p_3a));
    tft_cmd(0xB1U, p_b1, sizeof(p_b1));
    tft_cmd(0xB6U, p_b6, sizeof(p_b6));
    tft_cmd(0xF2U, p_f2, sizeof(p_f2));
    tft_cmd(0x26U, p_26, sizeof(p_26));
    tft_cmd(0xE0U, p_e0, sizeof(p_e0));
    tft_cmd(0xE1U, p_e1, sizeof(p_e1));
    tft_cmd(0x2BU, p_full_y, sizeof(p_full_y));
    tft_cmd(0x2AU, p_full_x, sizeof(p_full_x));

    tft_cmd(0x11U, NULL, 0U);        /* Sleep out */
    HAL_Delay(120U);
    tft_cmd(0x29U, NULL, 0U);        /* Display on */
    HAL_GPIO_WritePin(TFT_LED_PORT, TFT_LED_PIN, GPIO_PIN_SET);
}

/*---------------------------------------------------------------------------*/
/* 画图                                                                       */
/*---------------------------------------------------------------------------*/

#define UI_BG          0x08C4U
#define UI_HEADER      0x0967U
#define UI_CARD        0x19A7U
#define UI_PRICE_CARD  0x2185U
#define UI_EDGE        0x2A8BU
#define UI_CREAM       0xFFBCU
#define UI_MUTED       0xAE59U
#define UI_ORANGE      0xFC45U
#define UI_ORANGE_DARK 0xD2E2U
#define UI_GREEN       0x45AEU
#define UI_BANANA      0xFEC9U

static void tft_fill_rect(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t color)
{
    static uint8_t buf[480];
    uint16_t i;
    uint32_t remaining;

    if ((x1 < x0) || (y1 < y0) || (x1 < 0) || (y1 < 0) ||
        (x0 >= (int16_t)TFT_W) || (y0 >= (int16_t)TFT_H))
    {
        return;
    }

    if (x0 < 0) { x0 = 0; }
    if (y0 < 0) { y0 = 0; }
    if (x1 >= (int16_t)TFT_W) { x1 = (int16_t)TFT_W - 1; }
    if (y1 >= (int16_t)TFT_H) { y1 = (int16_t)TFT_H - 1; }

    for (i = 0U; i < sizeof(buf); i = (uint16_t)(i + 2U))
    {
        buf[i]      = (uint8_t)(color >> 8);
        buf[i + 1U] = (uint8_t)(color & 0xFFU);
    }

    tft_set_window((uint16_t)x0, (uint16_t)y0, (uint16_t)x1, (uint16_t)y1);
    HAL_GPIO_WritePin(TFT_DC_PORT, TFT_DC_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(TFT_CS_PORT, TFT_CS_PIN, GPIO_PIN_RESET);

    remaining = (uint32_t)(x1 - x0 + 1) * (uint32_t)(y1 - y0 + 1) * 2U;
    while (remaining > 0U)
    {
        uint16_t n = (remaining > sizeof(buf)) ? (uint16_t)sizeof(buf) : (uint16_t)remaining;
        (void)HAL_SPI_Transmit(&hspi2, buf, n, 1000U);
        remaining -= n;
    }

    HAL_GPIO_WritePin(TFT_CS_PORT, TFT_CS_PIN, GPIO_PIN_SET);
}

static void tft_fill_circle(int16_t cx, int16_t cy, int16_t radius, uint16_t color)
{
    int16_t dy;
    int16_t r2 = (int16_t)(radius * radius);

    for (dy = (int16_t)-radius; dy <= radius; dy++)
    {
        int16_t dx = 0;
        while ((int16_t)((dx + 1) * (dx + 1)) <= (int16_t)(r2 - dy * dy))
        {
            dx++;
        }
        tft_fill_rect((int16_t)(cx - dx), (int16_t)(cy + dy),
                      (int16_t)(cx + dx), (int16_t)(cy + dy), color);
    }
}

static void tft_fill_round_rect(int16_t x0, int16_t y0, int16_t x1, int16_t y1,
                                int16_t radius, uint16_t color)
{
    tft_fill_rect((int16_t)(x0 + radius), y0, (int16_t)(x1 - radius), y1, color);
    tft_fill_rect(x0, (int16_t)(y0 + radius), x1, (int16_t)(y1 - radius), color);
    tft_fill_circle((int16_t)(x0 + radius), (int16_t)(y0 + radius), radius, color);
    tft_fill_circle((int16_t)(x1 - radius), (int16_t)(y0 + radius), radius, color);
    tft_fill_circle((int16_t)(x0 + radius), (int16_t)(y1 - radius), radius, color);
    tft_fill_circle((int16_t)(x1 - radius), (int16_t)(y1 - radius), radius, color);
}

void TFT_Fill(uint16_t color)
{
    static uint8_t buf[128];
    uint16_t i;
    uint32_t chunks;

    for (i = 0U; i < sizeof(buf); i = (uint16_t)(i + 2U))
    {
        buf[i]      = (uint8_t)(color >> 8);
        buf[i + 1U] = (uint8_t)(color & 0xFFU);
    }

    tft_set_window(0U, 0U, TFT_W - 1U, TFT_H - 1U);
    HAL_GPIO_WritePin(TFT_DC_PORT, TFT_DC_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(TFT_CS_PORT, TFT_CS_PIN, GPIO_PIN_RESET);

    chunks = ((uint32_t)TFT_W * TFT_H * 2U) / sizeof(buf);
    while (chunks-- > 0U)
    {
        (void)HAL_SPI_Transmit(&hspi2, buf, (uint16_t)sizeof(buf), 1000U);
    }

    HAL_GPIO_WritePin(TFT_CS_PORT, TFT_CS_PIN, GPIO_PIN_SET);
}

/**
  * @brief  把一个位图字形放大 scale 倍画出来
  *         bits 每行 w 位，高位在前；行数 h
  */
static void tft_blit(const uint8_t *bits, uint8_t w, uint8_t h,
                     uint16_t x, uint16_t y, uint8_t scale,
                     uint16_t fg, uint16_t bg)
{
    static uint8_t buf[256];
    uint8_t  bpr = (uint8_t)(w / 8U);
    uint16_t width = (uint16_t)w * scale;
    uint8_t  r, c, sx, sy;

    tft_set_window(x, y, (uint16_t)(x + width - 1U), (uint16_t)(y + (uint16_t)h * scale - 1U));
    HAL_GPIO_WritePin(TFT_DC_PORT, TFT_DC_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(TFT_CS_PORT, TFT_CS_PIN, GPIO_PIN_RESET);

    for (r = 0U; r < h; r++)
    {
        uint16_t n = 0U;

        for (c = 0U; c < w; c++)
        {
            uint8_t bit = (uint8_t)((bits[r * bpr + (c >> 3)] >> (7U - (c & 7U))) & 1U);
            uint16_t col = (bit != 0U) ? fg : bg;

            for (sx = 0U; sx < scale; sx++)
            {
                buf[n++] = (uint8_t)(col >> 8);
                buf[n++] = (uint8_t)(col & 0xFFU);
            }
        }

        for (sy = 0U; sy < scale; sy++)
        {
            (void)HAL_SPI_Transmit(&hspi2, buf, n, 1000U);
        }
    }

    HAL_GPIO_WritePin(TFT_CS_PORT, TFT_CS_PIN, GPIO_PIN_SET);
}

static void tft_char(uint16_t x, uint16_t y, char ch, uint8_t scale, uint16_t fg, uint16_t bg)
{
    uint8_t idx;

    if ((ch < 32) || (ch > 126))
    {
        ch = '?';
    }
    idx = (uint8_t)(ch - 32);
    tft_blit(TFT_ASCII[idx], 8U, 16U, x, y, scale, fg, bg);
}

static void tft_cn(uint16_t x, uint16_t y, uint8_t idx, uint8_t scale, uint16_t fg, uint16_t bg)
{
    if (idx >= TFT_CN_COUNT)
    {
        return;
    }
    tft_blit(TFT_CN[idx], 16U, 16U, x, y, scale, fg, bg);
}

static uint16_t tft_str(const char *s, uint16_t x, uint16_t y, uint8_t scale,
                        uint16_t fg, uint16_t bg)
{
    uint16_t cx = x;

    while (*s != '\0')
    {
        tft_char(cx, y, *s, scale, fg, bg);
        cx = (uint16_t)(cx + 8U * scale);
        s++;
    }
    return cx;
}

/* 浮点转字符串（不依赖 %f） */
static void tft_fmt(char *out, float v, uint8_t decimals)
{
    int32_t scale = (decimals == 2U) ? 100 : 10;
    int32_t s = (int32_t)(v * (float)scale + ((v >= 0.0f) ? 0.5f : -0.5f));
    int32_t a = (s < 0) ? -s : s;
    int32_t ip = a / scale;
    int32_t fp = a % scale;

    if (decimals == 2U)
    {
        sprintf(out, "%s%ld.%02ld", (s < 0) ? "-" : "", (long)ip, (long)fp);
    }
    else
    {
        sprintf(out, "%s%ld.%01ld", (s < 0) ? "-" : "", (long)ip, (long)fp);
    }
}

static void tft_fmt_compact(char *out, float value)
{
    size_t length;

    tft_fmt(out, value, 1U);
    length = strlen(out);
    if ((length >= 2U) && (out[length - 1U] == '0') && (out[length - 2U] == '.'))
    {
        out[length - 2U] = '\0';
    }
}

static uint8_t tft_product_glyphs(const char *p, uint8_t *idx)
{
    if (strcmp(p, "banana") == 0) { idx[0] = 0U; idx[1] = 1U; return 2U; }
    if (strcmp(p, "apple")  == 0) { idx[0] = 2U; idx[1] = 3U; return 2U; }
    if (strcmp(p, "orange") == 0) { idx[0] = 4U; idx[1] = 5U; return 2U; }
    if (strcmp(p, "grape")  == 0) { idx[0] = 6U; idx[1] = 7U; return 2U; }
    return 0U;
}

static uint16_t tft_utf8_ascii_width(const char *s, uint8_t scale)
{
    return (uint16_t)(strlen(s) * 8U * scale);
}

static uint16_t tft_product_width(const char *product, uint8_t scale)
{
    uint8_t glyphs[2];
    uint8_t count = tft_product_glyphs(product, glyphs);

    return (count > 0U) ? (uint16_t)(count * 16U * scale)
                        : tft_utf8_ascii_width(product, scale);
}

static void tft_product_at(const char *product, uint16_t x, uint16_t y,
                           uint8_t scale, uint16_t fg, uint16_t bg)
{
    uint8_t glyphs[2];
    uint8_t count = tft_product_glyphs(product, glyphs);
    uint8_t i;

    if (count > 0U)
    {
        for (i = 0U; i < count; i++)
        {
            tft_cn((uint16_t)(x + i * 16U * scale), y, glyphs[i], scale, fg, bg);
        }
    }
    else
    {
        tft_str(product, x, y, scale, fg, bg);
    }
}

static void tft_product_center(const char *product, uint16_t y, uint8_t scale,
                               uint16_t fg, uint16_t bg)
{
    uint16_t width = tft_product_width(product, scale);
    tft_product_at(product, (uint16_t)((TFT_W - width) / 2U), y, scale, fg, bg);
}

static void tft_ascii_right(const char *text, uint16_t right, uint16_t y,
                            uint8_t scale, uint16_t fg, uint16_t bg)
{
    uint16_t width = tft_utf8_ascii_width(text, scale);
    tft_str(text, (uint16_t)(right - width + 1U), y, scale, fg, bg);
}

static void tft_number_center(const char *number, uint8_t unit_glyph,
                              uint16_t y, uint8_t scale, uint16_t fg, uint16_t bg)
{
    uint16_t width = (uint16_t)(strlen(number) * 8U * scale + 16U * scale);
    uint16_t x = (uint16_t)((TFT_W - width) / 2U);

    tft_str(number, x, y, scale, fg, bg);
    tft_cn((uint16_t)(x + strlen(number) * 8U * scale), y,
           unit_glyph, scale, fg, bg);
}

static void tft_number_unit_suffix_center(const char *number, uint8_t unit_glyph,
                                          const char *suffix, uint16_t y,
                                          uint16_t fg, uint16_t bg)
{
    uint16_t width = (uint16_t)(strlen(number) * 8U + 16U + tft_utf8_ascii_width(suffix, 1U));
    uint16_t x = (uint16_t)((TFT_W - width) / 2U);

    tft_str(number, x, y, 1U, fg, bg);
    x = (uint16_t)(x + strlen(number) * 8U);
    tft_cn(x, y, unit_glyph, 1U, fg, bg);
    x = (uint16_t)(x + 16U);
    tft_str(suffix, x, y, 1U, fg, bg);
}

static void tft_number_two_units_center(const char *number,
                                        uint8_t unit1, uint8_t unit2,
                                        uint16_t y, uint16_t fg, uint16_t bg)
{
    uint16_t width = (uint16_t)(strlen(number) * 8U + 32U);
    uint16_t x = (uint16_t)((TFT_W - width) / 2U);

    tft_str(number, x, y, 1U, fg, bg);
    x = (uint16_t)(x + strlen(number) * 8U);
    tft_cn(x, y, unit1, 1U, fg, bg);
    tft_cn((uint16_t)(x + 16U), y, unit2, 1U, fg, bg);
}

static void tft_number_unit_right(const char *number, uint8_t unit_glyph,
                                  const char *suffix, uint16_t right, uint16_t y,
                                  uint16_t fg, uint16_t bg)
{
    uint16_t width = (uint16_t)(strlen(number) * 8U + 16U + tft_utf8_ascii_width(suffix, 1U));
    uint16_t x = (uint16_t)(right - width + 1U);

    tft_str(number, x, y, 1U, fg, bg);
    x = (uint16_t)(x + strlen(number) * 8U);
    tft_cn(x, y, unit_glyph, 1U, fg, bg);
    x = (uint16_t)(x + 16U);
    tft_str(suffix, x, y, 1U, fg, bg);
}

static void tft_draw_thick_line(int16_t x0, int16_t y0, int16_t x1, int16_t y1,
                                int16_t width, uint16_t color)
{
    int16_t dx = (x1 > x0) ? (int16_t)(x1 - x0) : (int16_t)(x0 - x1);
    int16_t sx = (x0 < x1) ? 1 : -1;
    int16_t dy = (y1 > y0) ? (int16_t)(y0 - y1) : (int16_t)(y1 - y0);
    int16_t sy = (y0 < y1) ? 1 : -1;
    int16_t error = (int16_t)(dx + dy);
    int16_t half = (int16_t)(width / 2);

    while (1)
    {
        tft_fill_rect((int16_t)(x0 - half), (int16_t)(y0 - half),
                      (int16_t)(x0 + half), (int16_t)(y0 + half), color);
        if ((x0 == x1) && (y0 == y1))
        {
            break;
        }
        {
            int16_t e2 = (int16_t)(error * 2);
            if (e2 >= dy)
            {
                error = (int16_t)(error + dy);
                x0 = (int16_t)(x0 + sx);
            }
            if (e2 <= dx)
            {
                error = (int16_t)(error + dx);
                y0 = (int16_t)(y0 + sy);
            }
        }
    }
}

static void tft_draw_header(uint16_t accent)
{
    tft_fill_round_rect(12, 10, 228, 30, 9, UI_HEADER);
    tft_fill_circle(20, 20, 4, UI_GREEN);
    tft_str("SMART SCALE", 30U, 12U, 1U, UI_CREAM, UI_HEADER);
    tft_str("READY", 181U, 12U, 1U, UI_MUTED, UI_HEADER);
    tft_fill_rect(16, 33, 224, 34, accent);
}

static void tft_draw_orange_icon(uint16_t accent)
{
    tft_fill_circle(120, 58, 18, accent);
    tft_fill_circle(114, 53, 5, UI_ORANGE);
    tft_fill_circle(125, 64, 5, UI_ORANGE_DARK);
    tft_fill_circle(111, 41, 5, UI_GREEN);
    tft_fill_rect(116, 39, 129, 42, UI_GREEN);
}

static void tft_draw_banana_icon(uint16_t accent)
{
    int16_t x;
    int16_t y;

    for (y = 34; y <= 73; y++)
    {
        for (x = 92; x <= 145; x++)
        {
            int16_t nx = (int16_t)((x - 118) / 24);
            int16_t ny = (int16_t)((y - 54) / 15);
            int16_t outer = (int16_t)(nx * nx + ny * ny);
            int16_t ix = (int16_t)((x - 130) / 24);
            int16_t iy = (int16_t)((y - 47) / 14);
            int16_t inner = (int16_t)(ix * ix + iy * iy);
            if ((outer <= 1) && (inner > 1) && (x < 141))
            {
                tft_fill_rect(x, y, x, y, accent);
            }
        }
    }
    tft_fill_rect(92, 68, 98, 71, UI_ORANGE_DARK);
    tft_fill_rect(139, 37, 145, 40, UI_GREEN);
}

static void tft_draw_product_icon(const char *product, uint16_t accent)
{
    if (strcmp(product, "banana") == 0)
    {
        tft_draw_banana_icon(accent);
    }
    else
    {
        tft_draw_orange_icon(accent);
    }
}

static void tft_draw_check_mark(void)
{
    tft_fill_circle(120, 55, 18, UI_GREEN);
    tft_draw_thick_line(110, 55, 117, 63, 4, UI_CREAM);
    tft_draw_thick_line(117, 63, 131, 46, 4, UI_CREAM);
}

static void tft_draw_basket(int16_t cx, int16_t y, uint16_t color, uint8_t filled,
                            const char *product)
{
    int16_t i;

    tft_draw_thick_line((int16_t)(cx - 52), y, (int16_t)(cx + 52), y, 4, color);
    tft_draw_thick_line((int16_t)(cx - 52), y, (int16_t)(cx - 36), (int16_t)(y + 56), 3, color);
    tft_draw_thick_line((int16_t)(cx + 52), y, (int16_t)(cx + 36), (int16_t)(y + 56), 3, color);
    tft_draw_thick_line((int16_t)(cx - 36), (int16_t)(y + 56),
                        (int16_t)(cx + 36), (int16_t)(y + 56), 3, color);
    for (i = -24; i <= 24; i = (int16_t)(i + 24))
    {
        tft_draw_thick_line((int16_t)(cx + i / 3), (int16_t)(y + 8),
                            (int16_t)(cx + i), (int16_t)(y + 56), 1, color);
    }
    tft_draw_thick_line((int16_t)(cx - 30), (int16_t)(y + 28),
                        (int16_t)(cx + 30), (int16_t)(y + 28), 2, color);

    if (filled != 0U)
    {
        if (strcmp(product, "banana") == 0)
        {
            tft_fill_rect(85, 227, 155, 231, UI_GREEN);
            tft_fill_circle(120, 251, 19, UI_BANANA);
            tft_fill_circle(130, 246, 13, UI_BG);
        }
        else
        {
            tft_fill_circle(120, 245, 23, UI_ORANGE);
            tft_fill_circle(112, 238, 7, UI_ORANGE);
            tft_fill_rect(116, 220, 127, 225, UI_GREEN);
        }
    }
}

static void tft_draw_mini_product(const char *product, int16_t cx, int16_t cy)
{
    if (strcmp(product, "banana") == 0)
    {
        tft_fill_circle(cx, cy, 16, UI_BANANA);
        tft_fill_circle((int16_t)(cx + 10), (int16_t)(cy - 5), 12, UI_BG);
        tft_fill_rect((int16_t)(cx - 18), (int16_t)(cy + 10), (int16_t)(cx - 12), (int16_t)(cy + 13),
                      UI_ORANGE_DARK);
    }
    else
    {
        tft_fill_circle(cx, cy, 17, UI_ORANGE);
        tft_fill_circle((int16_t)(cx - 6), (int16_t)(cy - 6), 5, UI_ORANGE);
        tft_fill_rect((int16_t)(cx - 3), (int16_t)(cy - 23), (int16_t)(cx + 8), (int16_t)(cy - 19),
                      UI_GREEN);
    }
}

static void tft_draw_product_name(const char *product_ascii, uint16_t accent)
{
    (void)accent;
    tft_product_center(product_ascii, 79U, 2U, UI_CREAM, UI_BG);
}

static void tft_draw_weight_card(float weight_g, uint16_t accent)
{
    char buf[16];

    tft_fill_round_rect(16, 138, 224, 180, 12, UI_CARD);
    tft_fill_rect(16, 138, 224, 139, UI_EDGE);
    tft_cn(28U, 143U, 10U, 1U, UI_MUTED, UI_CARD);
    tft_cn(44U, 143U, 11U, 1U, UI_MUTED, UI_CARD);

    tft_fmt(buf, weight_g, 1U);
    tft_number_center(buf, 8U, 161U, 1U, UI_CREAM, UI_CARD);
    tft_fill_rect(28, 176, 212, 177, accent);
}

static void tft_draw_price_card(float price, uint16_t accent)
{
    char buf[16];

    tft_fill_round_rect(16, 188, 224, 248, 12, UI_PRICE_CARD);
    tft_fill_rect(16, 188, 224, 189, UI_EDGE);
    tft_cn(28U, 194U, 12U, 1U, UI_MUTED, UI_PRICE_CARD);
    tft_cn(44U, 194U, 13U, 1U, UI_MUTED, UI_PRICE_CARD);

    tft_fmt(buf, price, 2U);
    tft_number_center(buf, 9U, 213U, 2U, accent, UI_PRICE_CARD);
}

static void tft_draw_base(uint16_t accent)
{
    TFT_Fill(UI_BG);
    tft_fill_circle(-18, -10, 82, UI_HEADER);
    tft_fill_circle(260, 340, 112, UI_HEADER);
    tft_draw_header(accent);
    tft_fill_rect(52, 130, 188, 132, accent);
}

/**
  * @brief  开机显示等待状态
  */
void TFT_ShowWeight(float weight_g)
{
    tft_draw_base(UI_ORANGE);
    tft_draw_orange_icon(UI_ORANGE);
    tft_str("READY", 80U, 79U, 2U, UI_CREAM, UI_BG);
    tft_draw_weight_card(weight_g, UI_ORANGE);
}

/**
  * @brief  显示商品名、单价、重量、金额和可选营养信息
  */
void TFT_ShowResult(const char *product_ascii,
                    float price_per_kg,
                    float weight_g,
                    float price,
                    float kcal,
                    float carb_g,
                    float fiber_g,
                    uint8_t info_flags)
{
    uint16_t accent = UI_ORANGE;
    char unit_price[20];
    char nutrition[24];
    uint16_t y = 254U;

    if (strcmp(product_ascii, "banana") == 0)
    {
        accent = UI_BANANA;
    }

    strncpy(s_last_price.product, product_ascii, sizeof(s_last_price.product) - 1U);
    s_last_price.product[sizeof(s_last_price.product) - 1U] = '\0';
    s_last_price.price_per_kg = price_per_kg;
    s_last_price.weight_g = weight_g;
    s_last_price.price = price;
    s_last_price.kcal = kcal;
    s_last_price.carb_g = carb_g;
    s_last_price.fiber_g = fiber_g;
    s_last_price.info_flags = info_flags;
    s_last_price.valid = 1U;

    tft_draw_base(accent);
    tft_draw_product_icon(product_ascii, accent);
    tft_draw_product_name(product_ascii, accent);

    tft_fmt_compact(unit_price, price_per_kg);
    tft_number_unit_suffix_center(unit_price, 9U, "/kg", 113U, UI_MUTED, UI_BG);

    tft_draw_weight_card(weight_g, accent);
    tft_draw_price_card(price, accent);

    if ((info_flags & TFT_INFO_KCAL) != 0U)
    {
        sprintf(nutrition, "%ld", (long)(kcal + 0.5f));
        tft_number_two_units_center(nutrition, 23U, 24U, y, UI_CREAM, UI_BG);
        y = (uint16_t)(y + 18U);
    }
    if ((info_flags & TFT_INFO_CARB) != 0U)
    {
        tft_cn(18U, y, 25U, 1U, UI_MUTED, UI_BG);
        tft_cn(34U, y, 26U, 1U, UI_MUTED, UI_BG);
        tft_fmt(nutrition, carb_g, 1U);
        tft_number_center(nutrition, 8U, y, 1U, UI_CREAM, UI_BG);
        y = (uint16_t)(y + 18U);
    }
    if ((info_flags & TFT_INFO_FIBER) != 0U)
    {
        tft_cn(8U, y, 27U, 1U, UI_MUTED, UI_BG);
        tft_cn(24U, y, 28U, 1U, UI_MUTED, UI_BG);
        tft_cn(40U, y, 29U, 1U, UI_MUTED, UI_BG);
        tft_cn(56U, y, 30U, 1U, UI_MUTED, UI_BG);
        tft_fmt(nutrition, fiber_g, 1U);
        tft_number_center(nutrition, 8U, y, 1U, UI_CREAM, UI_BG);
    }
}

/**
  * @brief  显示电脑返回的清单
  */
void TFT_ShowReceipt(const TFT_ReceiptItem *items, uint8_t count, float total)
{
    char text[24];
    char unit_price[20];
    uint8_t i;
    uint16_t y = 94U;

    TFT_Fill(UI_BG);
    tft_fill_circle(-20, -10, 84, UI_HEADER);
    tft_draw_header(UI_ORANGE);
    tft_cn(96U, 38U, 14U, 2U, UI_CREAM, UI_BG);
    tft_cn(128U, 38U, 15U, 2U, UI_CREAM, UI_BG);

    if (count > 0U)
    {
        tft_cn(2U, 72U, 16U, 1U, UI_MUTED, UI_BG);
        tft_cn(18U, 72U, 17U, 1U, UI_MUTED, UI_BG);
        tft_cn(40U, 72U, 18U, 1U, UI_MUTED, UI_BG);
        tft_cn(56U, 72U, 19U, 1U, UI_MUTED, UI_BG);
        tft_cn(82U, 72U, 15U, 1U, UI_MUTED, UI_BG);
        tft_cn(98U, 72U, 20U, 1U, UI_MUTED, UI_BG);
        tft_cn(136U, 72U, 10U, 1U, UI_MUTED, UI_BG);
        tft_cn(152U, 72U, 11U, 1U, UI_MUTED, UI_BG);
        tft_cn(190U, 72U, 20U, 1U, UI_MUTED, UI_BG);
        tft_cn(206U, 72U, 31U, 1U, UI_MUTED, UI_BG);
        tft_fill_rect(4, 90, 236, 91, UI_EDGE);

        if (count > TFT_RECEIPT_MAX_ITEMS)
        {
            count = TFT_RECEIPT_MAX_ITEMS;
        }

        for (i = 0U; i < count; i++)
        {
            uint16_t row_y = (uint16_t)(y + i * 21U);
            uint16_t bg = ((i & 1U) == 0U) ? UI_CARD : UI_BG;

            tft_fill_rect(2, row_y, 237, (uint16_t)(row_y + 19U), bg);
            sprintf(text, "%u", (unsigned)items[i].n);
            tft_ascii_right(text, 20U, row_y, 1U, UI_CREAM, bg);
            tft_product_at(items[i].product, 40U, row_y, 1U, UI_CREAM, bg);

            tft_fmt_compact(unit_price, items[i].price_per_kg);
            tft_number_unit_right(unit_price, 9U, "/kg", 124U, row_y, UI_CREAM, bg);

            tft_fmt(text, items[i].weight_g, 1U);
            tft_number_unit_right(text, 8U, "", 184U, row_y, UI_CREAM, bg);

            tft_fmt(text, items[i].price, 2U);
            tft_number_unit_right(text, 9U, "", 236U, row_y, UI_ORANGE, bg);
        }
    }

    tft_fill_rect(4, 270, 236, 271, UI_EDGE);
    tft_cn(100U, 286U, 21U, 1U, UI_MUTED, UI_BG);
    tft_cn(116U, 286U, 22U, 1U, UI_MUTED, UI_BG);
    tft_fmt(text, total, 2U);
    tft_number_unit_right(text, 9U, "", 236U, 286U, UI_ORANGE, UI_BG);
}

void TFT_ShowLastPrice(void)
{
    if (s_last_price.valid == 0U)
    {
        TFT_ShowWeight(0.0f);
        return;
    }

    TFT_ShowResult(s_last_price.product,
                   s_last_price.price_per_kg,
                   s_last_price.weight_g,
                   s_last_price.price,
                   s_last_price.kcal,
                   s_last_price.carb_g,
                   s_last_price.fiber_g,
                   s_last_price.info_flags);
}

void TFT_ShowSaved(void)
{
    char value[24];
    const char *product = (s_last_price.valid != 0U) ? s_last_price.product : "banana";

    TFT_Fill(UI_BG);
    tft_draw_header(UI_GREEN);
    tft_draw_check_mark();
    tft_cn(72U, 82U, 40U, 2U, UI_GREEN, UI_BG);
    tft_cn(104U, 82U, 41U, 2U, UI_GREEN, UI_BG);
    tft_cn(136U, 82U, 42U, 2U, UI_GREEN, UI_BG);

    tft_draw_mini_product(product, 120, 143);
    tft_fill_rect(118, 161, 122, 181, UI_GREEN);
    tft_fill_rect(113, 178, 127, 185, UI_GREEN);
    tft_draw_basket(120, 200, UI_ORANGE, 0U, product);

    tft_product_center(product, 262U, 1U, UI_CREAM, UI_BG);
    if (s_last_price.valid != 0U)
    {
        tft_fmt(value, s_last_price.weight_g, 1U);
        tft_str(value, 28U, 292U, 1U, UI_CREAM, UI_BG);
        tft_cn((uint16_t)(28U + strlen(value) * 8U), 292U, 8U, 1U, UI_CREAM, UI_BG);
        tft_fmt(value, s_last_price.price, 2U);
        tft_number_unit_right(value, 9U, "", 236U, 292U, UI_ORANGE, UI_BG);
    }
}

void TFT_ShowCleared(void)
{
    TFT_Fill(UI_BG);
    tft_draw_header(UI_MUTED);
    tft_cn(40U, 72U, 14U, 2U, UI_CREAM, UI_BG);
    tft_cn(72U, 72U, 15U, 2U, UI_CREAM, UI_BG);
    tft_cn(104U, 72U, 40U, 2U, UI_CREAM, UI_BG);
    tft_cn(136U, 72U, 14U, 2U, UI_CREAM, UI_BG);
    tft_cn(168U, 72U, 45U, 2U, UI_CREAM, UI_BG);
    tft_draw_basket(120, 171, UI_MUTED, 0U, "orange");
    tft_str("EMPTY BASKET", 56U, 246U, 1U, UI_MUTED, UI_BG);
    tft_cn(76U, 282U, 21U, 1U, UI_MUTED, UI_BG);
    tft_cn(92U, 282U, 22U, 1U, UI_MUTED, UI_BG);
    tft_number_unit_right("0.00", 9U, "", 202U, 282U, UI_CREAM, UI_BG);
}

void TFT_PlaySplash(uint8_t tare_applied)
{
    uint8_t phase;
    uint16_t accent = (tare_applied != 0U) ? UI_GREEN : UI_ORANGE;

    TFT_Fill(UI_BG);
    tft_fill_circle(-15, -5, 74, UI_HEADER);
    tft_fill_circle(255, 330, 95, UI_HEADER);
    tft_draw_header(accent);

    tft_cn(40U, 65U, 32U, 2U, UI_CREAM, UI_BG);
    tft_cn(72U, 65U, 33U, 2U, UI_CREAM, UI_BG);
    tft_cn(104U, 65U, 34U, 2U, UI_CREAM, UI_BG);
    tft_cn(136U, 65U, 5U, 2U, UI_CREAM, UI_BG);
    tft_cn(168U, 65U, 35U, 2U, UI_CREAM, UI_BG);

    tft_fill_round_rect(66, 126, 174, 202, 14, UI_CARD);
    tft_fill_round_rect(80, 143, 160, 174, 8, UI_HEADER);
    tft_str("0.0", 95U, 146U, 1U, UI_CREAM, UI_HEADER);
    tft_cn(128U, 146U, 8U, 1U, UI_MUTED, UI_HEADER);
    tft_fill_round_rect(54, 204, 186, 218, 7, UI_EDGE);

    tft_cn(76U, 224U, 36U, 1U, UI_CREAM, UI_BG);
    tft_cn(92U, 224U, 37U, 1U, UI_CREAM, UI_BG);
    tft_cn(108U, 224U, 38U, 1U, UI_CREAM, UI_BG);
    tft_cn(124U, 224U, 39U, 1U, UI_CREAM, UI_BG);

    if (tare_applied != 0U)
    {
        tft_cn(84U, 246U, 40U, 1U, accent, UI_BG);
        tft_cn(100U, 246U, 47U, 1U, accent, UI_BG);
        tft_cn(116U, 246U, 48U, 1U, accent, UI_BG);
    }
    else
    {
        tft_cn(76U, 246U, 49U, 1U, accent, UI_BG);
        tft_cn(92U, 246U, 47U, 1U, accent, UI_BG);
        tft_cn(108U, 246U, 48U, 1U, accent, UI_BG);
    }

    tft_str("PRESS TARE", 68U, 272U, 1U, UI_MUTED, UI_BG);
    tft_fill_round_rect(40, 298, 200, 306, 4, UI_EDGE);
    for (phase = 0U; phase < 8U; phase++)
    {
        tft_fill_round_rect(40, 298, (int16_t)(60 + phase * 20), 306, 4, accent);
        HAL_Delay(90U);
    }
}
