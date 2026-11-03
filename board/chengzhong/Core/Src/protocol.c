/**
  ******************************************************************************
  * @file    protocol.c
  * @brief   串口协议：一行一个 JSON，115200 8N1，换行结束，一行不超过 512 字节。
  *
  *          发出去的三行共用一个 seq，每发一条加 1：
  *            {"v":1,"type":"weight",...}
  *            {"v":1,"type":"status",...}
  *            {"v":1,"type":"ack",...}
  *
  *          收进来：
  *            {"v":1,"type":"command","command":"tare"}
  *            {"v":1,"type":"display_result",...}
  *          其它内容整行不理，也不用重启。
  ******************************************************************************
  */

#include "protocol.h"
#include "config.h"
#include "scale.h"
#include "voice.h"
#include "tft.h"
#include "wifi.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern UART_HandleTypeDef huart1;

#define PROTO_RX_RING_SIZE   1024U
#define PROTO_LINE_MAX       512U          /* 文档规定：一行最多 512 字节 */
#define PROTO_FIELD_MAX      32U

/* ---------- 接收 ---------- */
static volatile uint8_t  s_rx_ring[PROTO_RX_RING_SIZE];
static volatile uint16_t s_rx_head = 0U;
static volatile uint16_t s_rx_tail = 0U;

/* 统计用：收了多少字节、错了几次、发了多少字节 */
static volatile uint32_t s_rx_total = 0U;
static volatile uint32_t s_rx_err   = 0U;
static uint32_t          s_tx_total = 0U;
#if (DEBUG_RX_COUNTER == 1)
static uint32_t          s_last_hb  = 0U;
#endif

static char     s_line[PROTO_LINE_MAX + 1U];
static uint16_t s_line_len      = 0U;
static uint8_t  s_line_overflow = 0U;

/* ---------- 发送 ---------- */
static uint32_t s_seq = 0U;                 /* weight / status / ack 共用 */

/* ---------- 最近一次收到的显示结果 ---------- */
static char  s_display_product[PROTO_FIELD_MAX];
static float s_display_price_per_kg = 0.0f;
static float s_display_weight       = 0.0f;
static float s_display_price        = 0.0f;
static float s_display_kcal         = 0.0f;
static float s_display_carb         = 0.0f;
static float s_display_fiber        = 0.0f;

static void proto_send_line(const char *s);
static void proto_fmt_fixed(char *out, float v, uint8_t decimals);
static uint8_t proto_json_get(const char *json, const char *key, char *out, uint16_t out_size);
static uint8_t proto_parse_receipt(const char *json,
                                   TFT_ReceiptItem *items,
                                   uint8_t *count,
                                   float *total);
static void proto_handle_line(char *line);

/*============================================================================*/

/**
  * @brief  发一整行，自动补换行
  */
static void proto_send_line(const char *s)
{
    uint16_t n = (uint16_t)strlen(s);

    s_tx_total += (uint32_t)n + 1U;
    HAL_UART_Transmit(&huart1, (uint8_t *)s, n, 200U);
    HAL_UART_Transmit(&huart1, (uint8_t *)"\n", 1U, 200U);
}

void Proto_SendLine(const char *s)
{
    proto_send_line(s);
}

/**
  * @brief  把浮点数格式化成定点字符串。
  *         故意不用 printf 的 %f：标准库和 microlib 对 %f 的支持不一样，
  *         自己算整数和小数部分最稳。
  */
static void proto_fmt_fixed(char *out, float v, uint8_t decimals)
{
    int32_t scale = (decimals == 2U) ? 100 : 10;
    float   fv    = v * (float)scale;
    int32_t s     = (int32_t)(fv + ((v >= 0.0f) ? 0.5f : -0.5f));
    int32_t a     = (s < 0) ? -s : s;
    int32_t ip    = a / scale;
    int32_t fp    = a % scale;

    if (decimals == 2U)
    {
        sprintf(out, "%s%ld.%02ld", (s < 0) ? "-" : "", (long)ip, (long)fp);
    }
    else
    {
        sprintf(out, "%s%ld.%01ld", (s < 0) ? "-" : "", (long)ip, (long)fp);
    }
}

/**
  * @brief  从 JSON 里取一个字段的值（字符串或数字都行）
  * @retval 1 = 找到了
  */
static uint8_t proto_json_get(const char *json, const char *key, char *out, uint16_t out_size)
{
    char        pattern[PROTO_FIELD_MAX + 4U];
    const char *p;
    uint16_t    n = 0U;

    if (out_size == 0U)
    {
        return 0U;
    }

    sprintf(pattern, "\"%s\"", key);

    /* 关键：要找的是"键"，不是"值"。
     * 例如 {"type":"command","command":"tare"} 里 "command" 出现了两次，
     * 第一次是 type 的值。所以引号后面必须再跟一个冒号，才算真的键；
     * 否则继续往后找下一个。 */
    p = strstr(json, pattern);
    while (p != NULL)
    {
        const char *q = p + strlen(pattern);

        while ((*q == ' ') || (*q == '\t'))
        {
            q++;
        }
        if (*q == ':')
        {
            break;                          /* 这个才是键 */
        }
        p = strstr(p + 1, pattern);         /* 是值，继续往后找 */
    }

    if (p == NULL)
    {
        return 0U;
    }

    p += strlen(pattern);
    while ((*p == ' ') || (*p == '\t') || (*p == ':'))
    {
        p++;
    }

    if (*p == '"')
    {
        p++;
        while ((*p != '\0') && (*p != '"') && (n < (uint16_t)(out_size - 1U)))
        {
            out[n++] = *p++;
        }
    }
    else
    {
        while ((*p != '\0') && (*p != ',') && (*p != '}') && (*p != ' ') &&
               (n < (uint16_t)(out_size - 1U)))
        {
            out[n++] = *p++;
        }
    }

    out[n] = '\0';
    return (n > 0U) ? 1U : 0U;
}

static uint8_t proto_parse_receipt(const char *json,
                                   TFT_ReceiptItem *items,
                                   uint8_t *count,
                                   float *total)
{
    const char *p;
    char tmp[PROTO_FIELD_MAX];

    *count = 0U;
    *total = 0.0f;

    p = strstr(json, "\"items\"");
    if (p == NULL)
    {
        return 0U;
    }
    p = strchr(p, '[');
    if (p == NULL)
    {
        return 0U;
    }

    while ((p = strchr(p, '{')) != NULL)
    {
        const char *end = strchr(p, '}');
        static char object[192];
        size_t object_len;

        if (end == NULL)
        {
            return 0U;
        }
        object_len = (size_t)(end - p + 1);
        if (object_len >= sizeof(object))
        {
            return 0U;
        }
        memcpy(object, p, object_len);
        object[object_len] = '\0';

        tmp[0] = '\0';
        (void)proto_json_get(object, "n", tmp, sizeof(tmp));
        items[*count].n = (uint16_t)atoi(tmp);

        tmp[0] = '\0';
        (void)proto_json_get(object, "product", tmp, sizeof(tmp));
        strncpy(items[*count].product, tmp, sizeof(items[*count].product) - 1U);
        items[*count].product[sizeof(items[*count].product) - 1U] = '\0';

        tmp[0] = '\0';
        (void)proto_json_get(object, "price_per_kg", tmp, sizeof(tmp));
        items[*count].price_per_kg = (float)atof(tmp);

        tmp[0] = '\0';
        (void)proto_json_get(object, "weight_g", tmp, sizeof(tmp));
        items[*count].weight_g = (float)atof(tmp);

        tmp[0] = '\0';
        (void)proto_json_get(object, "price", tmp, sizeof(tmp));
        items[*count].price = (float)atof(tmp);

        (*count)++;
        if (*count >= TFT_RECEIPT_MAX_ITEMS)
        {
            break;
        }
        p = end + 1;
    }

    tmp[0] = '\0';
    if (proto_json_get(json, "total", tmp, sizeof(tmp)) != 0U)
    {
        *total = (float)atof(tmp);
    }

    return 1U;
}

/**
  * @brief  发一条非 JSON 的调试行。电脑会自动丢掉这种行，不影响协议。
  */
static void proto_send_debug(const char *s)
{
    char buf[160];

    sprintf(buf, "# %s", s);
    proto_send_line(buf);
}

/**
  * @brief  给其它模块用的调试输出接口（一样以 # 开头，电脑会自动忽略）
  */
void Proto_SendDebugLine(const char *text)
{
    proto_send_debug(text);
}

/*============================================================================*/
/*                              对外发送接口                                   */
/*============================================================================*/

void Proto_SendStatus(const char *state)
{
    char buf[128];

    s_seq++;
    sprintf(buf,
            "{\"v\":1,\"type\":\"status\",\"seq\":%lu,\"timestamp_ms\":%lu,\"state\":\"%s\"}",
            (unsigned long)s_seq, (unsigned long)HAL_GetTick(), state);
    proto_send_line(buf);
}

void Proto_SendWeight(float weight_g, uint8_t stable, float tare_g, const char *status)
{
    char buf[192];
    char w[24];
    char t[24];

    if (status == NULL)
    {
        status = "ok";
    }

    proto_fmt_fixed(w, weight_g, 1U);
    proto_fmt_fixed(t, tare_g, 1U);

    s_seq++;
    sprintf(buf,
            "{\"v\":1,\"type\":\"weight\",\"seq\":%lu,\"timestamp_ms\":%lu,"
            "\"weight_g\":%s,\"stable\":%s,\"tare_g\":%s,\"status\":\"%s\"}",
            (unsigned long)s_seq, (unsigned long)HAL_GetTick(),
            w, (stable != 0U) ? "true" : "false", t, status);
    proto_send_line(buf);
}

void Proto_SendTareAck(uint8_t ok)
{
    char buf[160];

    s_seq++;
    sprintf(buf,
            "{\"v\":1,\"type\":\"ack\",\"seq\":%lu,\"timestamp_ms\":%lu,"
            "\"command\":\"tare\",\"status\":\"%s\"}",
            (unsigned long)s_seq, (unsigned long)HAL_GetTick(),
            (ok != 0U) ? "ok" : "error");
    proto_send_line(buf);
}

void Proto_SendCommand(const char *command)
{
    char buf[96];

    if ((command == NULL) || (strlen(command) > 16U))
    {
        return;
    }

    sprintf(buf, "{\"v\":1,\"type\":\"command\",\"command\":\"%s\"}", command);
    proto_send_line(buf);
}

uint8_t Proto_PressTare(void)
{
    if (Scale_Tare() == 0U)
    {
        return 0U;
    }

    Scale_SendCurrentStatus();
    Voice_SayTared();
    TFT_Mark(TFT_VIEW_WEIGHT);
    return 1U;
}

void Proto_PressSave(void)
{
    Proto_SendCommand("save");
    Voice_SaySaved();
    TFT_Mark(TFT_VIEW_SAVED);
}

void Proto_PressClear(void)
{
    Proto_SendCommand("clear");
    Voice_SayCleared();
    TFT_Mark(TFT_VIEW_CLEARED);
}

void Proto_PressReceipt(void)
{
    Proto_SendCommand("receipt");
}

void Proto_PressReset(void)
{
    Voice_SayReset();
}

void Proto_SendRawDebug(int32_t raw, float grams)
{
    char buf[96];
    char g[24];

    proto_fmt_fixed(g, grams, 1U);
    sprintf(buf, "RAW=%ld g=%s", (long)raw, g);
    proto_send_debug(buf);
}

/*============================================================================*/
/*                              接收与解析                                     */
/*============================================================================*/

/**
  * @brief  处理一条完整的行
  */
static void proto_handle_line(char *line)
{
    char type[PROTO_FIELD_MAX];
    char cmd[PROTO_FIELD_MAX];

#if (DEBUG_ECHO_RX == 1)
    /* 调试用：收到什么就回显什么，用来验证接收通路 */
    {
        static char echo_buf[PROTO_LINE_MAX + 32U];

        sprintf(echo_buf, "# RX %u bytes: %s", (unsigned)s_line_len, line);
        proto_send_line(echo_buf);
    }
#endif

    Wifi_OnPcLine(line);

    if (line[0] != '{')
    {
        return;                     /* 不是 JSON，整行不理 */
    }

    if (proto_json_get(line, "type", type, sizeof(type)) == 0U)
    {
        return;                     /* 连 type 都没有，不理 */
    }

    if (strcmp(type, "command") == 0)
    {
        if (proto_json_get(line, "command", cmd, sizeof(cmd)) == 0U)
        {
            return;
        }

        if (strcmp(cmd, "tare") == 0)
        {
            uint8_t ok = Scale_Tare();

            Proto_SendTareAck(ok);      /* 先回成功/失败 */
            if (ok != 0U)
            {
                Scale_SendCurrentStatus();  /* 再报一次 ZERO */
            }
        }
        /* 其它命令：整行不理，不重启 */
    }
    else if (strcmp(type, "display_result") == 0)
    {
        char tmp[PROTO_FIELD_MAX];
        uint8_t info_flags = 0U;

        tmp[0] = '\0';
        (void)proto_json_get(line, "product", tmp, sizeof(tmp));
        strncpy(s_display_product, tmp, sizeof(s_display_product) - 1U);
        s_display_product[sizeof(s_display_product) - 1U] = '\0';

        tmp[0] = '\0';
        if (proto_json_get(line, "weight_g", tmp, sizeof(tmp)) != 0U)
        {
            s_display_weight = (float)atof(tmp);
        }

        tmp[0] = '\0';
        if (proto_json_get(line, "price", tmp, sizeof(tmp)) != 0U)
        {
            s_display_price = (float)atof(tmp);
        }

        tmp[0] = '\0';
        if (proto_json_get(line, "price_per_kg", tmp, sizeof(tmp)) != 0U)
        {
            s_display_price_per_kg = (float)atof(tmp);
        }
        else if (s_display_weight > 0.0f)
        {
            s_display_price_per_kg = s_display_price * 1000.0f / s_display_weight;
        }

        s_display_kcal = 0.0f;
        tmp[0] = '\0';
        if (proto_json_get(line, "portion_kcal", tmp, sizeof(tmp)) != 0U)
        {
            s_display_kcal = (float)atof(tmp);
            info_flags |= TFT_INFO_KCAL;
        }

        s_display_carb = 0.0f;
        tmp[0] = '\0';
        if (proto_json_get(line, "portion_carb_g", tmp, sizeof(tmp)) != 0U)
        {
            s_display_carb = (float)atof(tmp);
            info_flags |= TFT_INFO_CARB;
        }

        s_display_fiber = 0.0f;
        tmp[0] = '\0';
        if (proto_json_get(line, "portion_fiber_g", tmp, sizeof(tmp)) != 0U)
        {
            s_display_fiber = (float)atof(tmp);
            info_flags |= TFT_INFO_FIBER;
        }

        /* 价格回来了，用语音念一遍：商品名 + 克数 + 金额（不念热量碳水） */
        Voice_SayPrice(s_display_product, s_display_weight, s_display_price);

        TFT_ShowResult(s_display_product,
                       s_display_price_per_kg,
                       s_display_weight,
                       s_display_price,
                       s_display_kcal,
                       s_display_carb,
                       s_display_fiber,
                       info_flags);
    }
    else if (strcmp(type, "receipt_result") == 0)
    {
        static TFT_ReceiptItem items[TFT_RECEIPT_MAX_ITEMS];
        uint8_t count;
        float total;

        if ((Wifi_Busy() == 0U) && (proto_parse_receipt(line, items, &count, &total) != 0U))
        {
            if (count == 0U)
            {
                TFT_ShowCleared();
            }
            else
            {
                TFT_ShowReceipt(items, count, total);
            }
        }
    }
    else if (strcmp(type, "ack") == 0)
    {
        char status[PROTO_FIELD_MAX];

        if (proto_json_get(line, "command", cmd, sizeof(cmd)) != 0U)
        {
            status[0] = '\0';
            (void)proto_json_get(line, "status", status, sizeof(status));
            if ((strcmp(cmd, "save") == 0) && (strcmp(status, "ok") == 0))
            {
                if (Wifi_Busy() == 0U)
                {
                    TFT_ShowSaved();
                }
            }
            else if (strcmp(cmd, "save") == 0)
            {
                Wifi_CancelPaint();
                TFT_ShowLastPrice();
            }
        }
    }
    else
    {
        /* 不认识的内容：忽略 */
    }
}

/**
  * @brief  串口中断收到一个字节，丢进环形缓冲
  */
void Proto_RxByteFromIsr(uint8_t b)
{
    uint16_t next = (uint16_t)((s_rx_head + 1U) % PROTO_RX_RING_SIZE);

    if (next != s_rx_tail)
    {
        s_rx_ring[s_rx_head] = b;
        s_rx_head            = next;
    }
    /* 缓冲满了就丢这个字节，不阻塞中断 */
}

/**
  * @brief  USART1 中断服务。
  *         不走 HAL 的 UART 状态机，直接读寄存器：简单、少一层出错的可能。
  *         在 STM32F1 上，读 SR 再读 DR 会同时清掉 RXNE 和 ORE/FE/NE/PE。
  */
void Proto_Usart1Isr(void)
{
    uint32_t sr = huart1.Instance->SR;

    if ((sr & USART_SR_RXNE) != 0U)
    {
        uint8_t b = (uint8_t)(huart1.Instance->DR & 0xFFU);

        s_rx_total++;
        Proto_RxByteFromIsr(b);
    }
    else if ((sr & (USART_SR_ORE | USART_SR_FE | USART_SR_NE | USART_SR_PE)) != 0U)
    {
        /* 有错误标志但没有有效数据：读一下 DR 把标志清掉 */
        (void)huart1.Instance->DR;
        s_rx_err++;
    }
    else
    {
        /* 其它中断源，本工程没用到 */
    }
}

/**
  * @brief  主循环里反复调用：把收到的字节拼成行，再解析
  */
void Proto_Poll(void)
{
    while (s_rx_tail != s_rx_head)
    {
        uint8_t b = s_rx_ring[s_rx_tail];
        s_rx_tail = (uint16_t)((s_rx_tail + 1U) % PROTO_RX_RING_SIZE);

        if (b == (uint8_t)'\n')
        {
            if (s_line_overflow == 0U)
            {
                s_line[s_line_len] = '\0';
                if (s_line_len > 0U)
                {
                    proto_handle_line(s_line);
                }
            }
            /* 超过 512 字节的行直接丢掉，后面的行照常处理 */
            s_line_len      = 0U;
            s_line_overflow = 0U;
        }
        else if (b != (uint8_t)'\r')
        {
            if (s_line_len < PROTO_LINE_MAX)
            {
                s_line[s_line_len] = (char)b;
                s_line_len++;
            }
            else
            {
                s_line_overflow = 1U;
            }
        }
        else
        {
            /* 忽略 '\r' */
        }
    }

#if (DEBUG_RX_COUNTER == 1)
    /* 每秒打一行心跳：一眼看出有没有收到数据 */
    if ((HAL_GetTick() - s_last_hb) >= 1000U)
    {
        char hb[80];

        s_last_hb = HAL_GetTick();
        sprintf(hb, "HB rx=%lu err=%lu tx=%lu",
                (unsigned long)s_rx_total, (unsigned long)s_rx_err, (unsigned long)s_tx_total);
        proto_send_debug(hb);
    }
#endif
}

void Proto_Init(void)
{
    s_rx_head       = 0U;
    s_rx_tail       = 0U;
    s_line_len      = 0U;
    s_line_overflow = 0U;
    s_seq           = 0U;
    s_rx_total      = 0U;
    s_rx_err        = 0U;
    s_tx_total      = 0U;
#if (DEBUG_RX_COUNTER == 1)
    s_last_hb       = HAL_GetTick();
#endif
    s_display_product[0] = '\0';

    /* 先把残留的标志清干净，再直接开接收中断 */
    (void)huart1.Instance->SR;
    (void)huart1.Instance->DR;
    __HAL_UART_ENABLE_IT(&huart1, UART_IT_RXNE);
}

const char *Proto_GetDisplayProduct(void) { return s_display_product; }
float       Proto_GetDisplayWeightG(void) { return s_display_weight;  }
float       Proto_GetDisplayPrice(void)   { return s_display_price;   }
