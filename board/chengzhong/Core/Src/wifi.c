/**
  ******************************************************************************
  * @file    wifi.c
 * @brief   ESP-01 走 USART3，PD8 发送、PD9 接收。手机连热点 SmartScale 后打开
 *          http://192.168.4.1/ ，页面跟屏幕同一套深色计价画面，下面可以
 *          复位、去皮、保存、清空。/records 和 /receipt 仍向电脑要记录。
  ******************************************************************************
  */

#include "wifi.h"
#include "config.h"
#include "protocol.h"
#include "scale.h"
#include "tft.h"
#include <stdio.h>
#include <string.h>

#if (WIFI_ENABLE == 1)

#define WIFI_RING    2048U
#define WIFI_LINE    600U
#define WIFI_PAGE    3072U

/* Setup, then run. UDP link 4 answers the phone's "does this Wi-Fi have internet" check. */
#define WIFI_PHASE_AT      0U
#define WIFI_PHASE_MODE    1U
#define WIFI_PHASE_SLEEP   2U
#define WIFI_PHASE_SAP     3U
#define WIFI_PHASE_MUX     4U
#define WIFI_PHASE_DINFO   5U
#define WIFI_PHASE_SRVOFF  6U
#define WIFI_PHASE_UDP     7U
#define WIFI_PHASE_SERVER  8U
#define WIFI_PHASE_STO     9U
#define WIFI_PHASE_RUN     10U
#define WIFI_PHASE_SEND    11U
#define WIFI_PHASE_DEAD    12U

static UART_HandleTypeDef huart4;
static volatile uint8_t  s_ring[WIFI_RING];
static volatile uint16_t s_head;
static volatile uint16_t s_tail;

static char     s_line[WIFI_LINE];
static uint16_t s_line_len;
static char     s_page[WIFI_PAGE];
static uint16_t s_page_len;
static uint8_t  s_phase;
static uint8_t  s_link;
static uint8_t  s_seen;
static uint8_t  s_kind;
static uint8_t  s_pending;
static uint8_t  s_drop;
static uint8_t  s_hold;
static uint8_t  s_at_wait;
static uint8_t  s_prompted;
static uint8_t  s_next_ok;
static uint8_t  s_next_id;
static uint8_t  s_next_kind;
static uint32_t s_deadline;
static uint32_t s_pending_at;
static uint32_t s_at_due;
static uint8_t  s_udp;
static uint8_t  s_udp_try;
static uint8_t  s_keep;
static uint8_t  s_probe_on;
static uint8_t  s_probe_id;
static uint8_t  s_probe_kind;
static uint16_t s_raw_left;
static uint8_t  s_raw_tcp;
static uint8_t  s_raw_bad;
static uint8_t  s_get_len;
static uint8_t  s_get_on;
static uint8_t  s_get_id;
static char     s_get[80];
static uint8_t  s_notice;
static uint8_t  s_reset_arm;
static uint8_t  s_paint;
static uint8_t  s_paint_ready;
static uint8_t  s_sync_receipt;
static uint8_t  s_http;

static void wifi_send(const char *text);
static void wifi_arm(uint32_t wait_ms);
static void wifi_next_setup(void);
static void wifi_on_esp_line(char *line);
static void wifi_ask(const char *query);
static void wifi_begin_send(const char *body);
static void wifi_begin_screen(void);
static void wifi_run_kind(uint8_t kind);
static void wifi_begin_bytes(const uint8_t *data, uint16_t len);
static void wifi_maybe_reset(void);
static void wifi_service_side(void);
static void wifi_queue_close(uint8_t id);
static uint8_t wifi_take(uint8_t *out);

static void wifi_note(const char *text)
{
    char line[80];

    sprintf(line, "wifi:%.60s", text);
    Proto_SendLine(line);
}

static void wifi_send(const char *text)
{
    uint16_t n = (uint16_t)strlen(text);

    wifi_note(text);
    HAL_UART_Transmit(&huart4, (uint8_t *)text, n, 200U);
    HAL_UART_Transmit(&huart4, (uint8_t *)"\r\n", 2U, 200U);
}

static void wifi_arm(uint32_t wait_ms)
{
    s_deadline = HAL_GetTick() + wait_ms;
}

static void wifi_enable_rx(void)
{
    (void)huart4.Instance->SR;
    (void)huart4.Instance->DR;
    __HAL_UART_ENABLE_IT(&huart4, UART_IT_RXNE);
}

static void wifi_open(uint32_t baud)
{
    huart4.Instance          = USART3;
    huart4.Init.BaudRate     = baud;
    huart4.Init.WordLength   = UART_WORDLENGTH_8B;
    huart4.Init.StopBits     = UART_STOPBITS_1;
    huart4.Init.Parity       = UART_PARITY_NONE;
    huart4.Init.Mode         = UART_MODE_TX_RX;
    huart4.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart4.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart4) != HAL_OK)
    {
        s_phase = WIFI_PHASE_DEAD;
        return;
    }
    wifi_enable_rx();
}

static void wifi_next_setup(void)
{
    char sap[80];

    if (s_phase == WIFI_PHASE_AT)
    {
        wifi_send("AT");
    }
    else if (s_phase == WIFI_PHASE_MODE)
    {
        wifi_send("AT+CWMODE=2");
    }
    else if (s_phase == WIFI_PHASE_SLEEP)
    {
        /* After AP mode. Soft AP otherwise sleeps: the phone stays associated, but new TCP never arrives. */
        wifi_send("AT+SLEEP=0");
    }
    else if (s_phase == WIFI_PHASE_SAP)
    {
        sprintf(sap, "AT+CWSAP=\"%s\",\"%s\",5,3", WIFI_AP_NAME, WIFI_AP_PASS);
        wifi_send(sap);
    }
    else if (s_phase == WIFI_PHASE_MUX)
    {
        wifi_send("AT+CIPMUX=1");
    }
    else if (s_phase == WIFI_PHASE_DINFO)
    {
        wifi_send("AT+CIPDINFO=1");
    }
    else if (s_phase == WIFI_PHASE_SRVOFF)
    {
        /* Once at boot. The module keeps a stale server across MCU reset ("no change"). */
        wifi_send("AT+CIPSERVER=0");
    }
    else if (s_phase == WIFI_PHASE_UDP)
    {
        /* Do not answer DNS. An A record of 192.168.4.1 makes the phone open
         * TLS to this scale for every name and fills links 0-3. */
        wifi_send("AT");
    }
    else if (s_phase == WIFI_PHASE_SERVER)
    {
        wifi_send("AT+CIPSERVER=1,80");
    }
    else if (s_phase == WIFI_PHASE_STO)
    {
        wifi_send("AT+CIPSTO=5");
    }
    else
    {
        return;
    }
    wifi_arm(2000U);
}

static uint8_t wifi_setup_accepted(const char *line)
{
    if (strstr(line, "OK") != NULL)
    {
        return 1U;
    }
    /* These may fail on older AT firmware. Keep booting either way. */
    if ((s_phase == WIFI_PHASE_SLEEP) || (s_phase == WIFI_PHASE_DINFO) ||
        (s_phase == WIFI_PHASE_SRVOFF) || (s_phase == WIFI_PHASE_STO))
    {
        if ((strncmp(line, "ERROR", 5) == 0) || (strstr(line, "FAIL") != NULL))
        {
            return 1U;
        }
    }
    return 0U;
}

static void wifi_enter_run(void)
{
    s_phase   = WIFI_PHASE_RUN;
    s_at_wait = 0U;
    wifi_note("up");
}

static void wifi_begin_bytes(const uint8_t *data, uint16_t len)
{
    char cmd[28];

    if ((len == 0U) || (len >= WIFI_PAGE))
    {
        return;
    }
    if (data != (const uint8_t *)s_page)
    {
        memcpy(s_page, data, len);
    }
    s_page_len = len;
    s_keep = 0U;
    sprintf(cmd, "AT+CIPSEND=%u,%u", (unsigned)s_link, (unsigned)len);
    wifi_send(cmd);
    wifi_arm(3000U);
    s_prompted = 0U;
    s_pending  = 0U;
    s_phase    = WIFI_PHASE_SEND;
}

static uint8_t wifi_dns_header(void)
{
    char    *p;
    unsigned len = 0U;
    uint16_t i;
    uint8_t  id;

    /* +IPD,<link>,<len>[,ip,port]:<payload>. Count the payload so binary
     * TLS does not sit in the text line and hold a web link open. */
    if ((s_line_len < 7U) || (memcmp(s_line, "+IPD,", 5) != 0) ||
        (s_line[5] < '0') || (s_line[5] > '4'))
    {
        return 0U;
    }
    id = (uint8_t)(s_line[5] - '0');
    for (i = 0U; i < s_line_len; i++)
    {
        if (s_line[i] == ':')
        {
            break;
        }
    }
    if (i >= s_line_len)
    {
        return 0U;
    }
    s_line[i] = '\0';
    p = s_line + 7;
    while ((*p >= '0') && (*p <= '9'))
    {
        len = (len * 10U) + (unsigned)(*p - '0');
        p++;
    }
    s_line_len = 0U;
    s_seen     = id;
    s_raw_tcp  = (id < 4U) ? 1U : 0U;
    if (s_raw_tcp != 0U)
    {
        s_raw_bad = 0U;
        if ((s_get_on == 0U) || (s_get_id != id))
        {
            if ((s_get_on != 0U) && (s_get_id < 4U))
            {
                wifi_queue_close(s_get_id);
            }
            s_get_len = 0U;
            s_get_on  = 0U;
        }
    }
    if ((len == 0U) || (len > 65535U))
    {
        s_raw_left = 0U;
        if (s_raw_tcp != 0U)
        {
            wifi_queue_close(id);
        }
        return 1U;
    }
    s_raw_left = (uint16_t)len;
    return 1U;
}

static uint16_t wifi_put(uint16_t n, const char *text)
{
    if (text == NULL)
    {
        return n;
    }
    while ((*text != '\0') && ((n + 1U) < WIFI_PAGE))
    {
        s_page[n] = *text;
        n++;
        text++;
    }
    return n;
}

static uint16_t wifi_span(uint16_t n, const char *start, const char *end)
{
    while ((start < end) && ((n + 1U) < WIFI_PAGE))
    {
        s_page[n] = *start;
        n++;
        start++;
    }
    return n;
}

static uint16_t wifi_row(uint16_t n, const char *start, const char *end)
{
    const char *bar1 = NULL;
    const char *bar2 = NULL;
    const char *cursor;

    for (cursor = start; cursor < end; cursor++)
    {
        if (*cursor == '|')
        {
            if (bar1 == NULL)
            {
                bar1 = cursor;
            }
            else
            {
                bar2 = cursor;
                break;
            }
        }
    }
    if ((bar1 == NULL) || (bar2 == NULL))
    {
        n = wifi_put(n, "<p class=c>");
        n = wifi_span(n, start, end);
        return wifi_put(n, "</p>");
    }
    n = wifi_put(n, "<li><b>");
    n = wifi_span(n, start, bar1);
    n = wifi_put(n, "</b><span>");
    n = wifi_span(n, bar1 + 1, bar2);
    n = wifi_put(n, "\xe5\x85\x8b</span><em>");
    n = wifi_span(n, bar2 + 1, end);
    return wifi_put(n, "\xe5\x85\x83</em></li>");
}

static const char WIFI_CSS[] =
    "body{margin:0;padding:8px;background:#081821;color:#fff7e6}"
    ".h,.t,a{background:#082c3a}.h{display:flex;padding:10px}"
    ".n{font-size:40px}.m{color:#42b673;font-size:28px}.u,span{color:#adcace}"
    ".c,li{background:#19353a}.p{background:#213129}.c,.p,li{padding:10px;margin:8px 0}"
    ".v{font-size:34px}.p .v{color:#ff8a29;font-size:42px}.p .y{color:#ffda4a}"
    ".t,li,.g{display:flex}"
    "a{display:inline-block;width:42%;margin:6px;padding:14px 0;color:#fff7e6}"
    "ul{padding:0;list-style:none}b{flex:1}em,.t b{color:#ff8a29}";

static void wifi_fmt(char *out, float v, uint8_t decimals)
{
    int32_t scale = (decimals == 2U) ? 100 : 10;
    int32_t s = (int32_t)(v * (float)scale + ((v >= 0.0f) ? 0.5f : -0.5f));
    int32_t a = (s < 0) ? -s : s;

    if (decimals == 2U)
    {
        sprintf(out, "%s%ld.%02ld", (s < 0) ? "-" : "", (long)(a / scale), (long)(a % scale));
    }
    else
    {
        sprintf(out, "%s%ld.%01ld", (s < 0) ? "-" : "", (long)(a / scale), (long)(a % scale));
    }
}

static uint16_t wifi_name(uint16_t n, const char *product)
{
    if ((product == NULL) || (product[0] == '\0'))
    {
        return wifi_put(n, "READY");
    }
    if (strcmp(product, "banana") == 0)
    {
        return wifi_put(n, "\xe9\xa6\x99\xe8\x95\x89");
    }
    if (strcmp(product, "apple") == 0)
    {
        return wifi_put(n, "\xe8\x8b\xb9\xe6\x9e\x9c");
    }
    if (strcmp(product, "orange") == 0)
    {
        return wifi_put(n, "\xe6\xa9\x99\xe5\xad\x90");
    }
    if (strcmp(product, "grape") == 0)
    {
        return wifi_put(n, "\xe8\x91\xa1\xe8\x90\x84");
    }
    return wifi_put(n, product);
}

static uint16_t wifi_page_open(void)
{
    uint16_t n = 0U;

    n = wifi_put(n,
                 "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n"
                 "<html><head><meta charset=utf-8>"
                 "<meta name=viewport content=\"width=device-width,initial-scale=1\"><style>");
    n = wifi_put(n, WIFI_CSS);
    return wifi_put(n,
                    "</style></head><body>"
                    "<div class=h><span>SMART SCALE</span><span>READY</span></div>");
}

static uint16_t wifi_keys(uint16_t n, uint8_t which)
{
    (void)which;
    return wifi_put(n,
                    "<p><a href=/do/reset>\xe5\xa4\x8d\xe4\xbd\x8d</a>"
                    "<a href=/do/tare>\xe5\x8e\xbb\xe7\x9a\xae</a>"
                    "<a href=/do/save>\xe4\xbf\x9d\xe5\xad\x98</a>"
                    "<a href=/do/clear>\xe6\xb8\x85\xe7\xa9\xba</a>"
                    "<a href=/records>\xe8\xae\xb0\xe5\xbd\x95</a>"
                    "<a href=/receipt>\xe6\xb8\x85\xe5\x8d\x95</a></p></body></html>");
}

static void wifi_ship(uint16_t n, uint8_t which)
{
    n = wifi_keys(n, which);
    if ((n + 1U) >= WIFI_PAGE)
    {
        return;
    }
    s_page[n] = '\0';
    s_page_len = n;
    s_keep = 0U;
    wifi_begin_bytes((const uint8_t *)s_page, n);
}

static uint16_t wifi_weight_card(uint16_t n, float grams)
{
    char num[16];

    wifi_fmt(num, grams, 1U);
    n = wifi_put(n, "<div class=c><div class=u>");
    n = wifi_put(n, "\xe9\x87\x8d\xe9\x87\x8f");
    n = wifi_put(n, "</div><div class=v>");
    n = wifi_put(n, num);
    return wifi_put(n, "\xe5\x85\x8b</div></div>");
}

static uint16_t wifi_price_card(uint16_t n, float price, uint8_t banana)
{
    char num[16];

    wifi_fmt(num, price, 2U);
    n = wifi_put(n, "<div class=p><div class=u>");
    n = wifi_put(n, "\xe9\x87\x91\xe9\xa2\x9d");
    n = wifi_put(n, (banana != 0U) ? "</div><div class=\"v y\">" : "</div><div class=v>");
    n = wifi_put(n, num);
    return wifi_put(n, "\xe5\x85\x83</div></div>");
}

static uint16_t wifi_nut(uint16_t n, const TFT_Snap *snap)
{
    char num[16];

    if ((snap->info_flags & (TFT_INFO_KCAL | TFT_INFO_CARB | TFT_INFO_FIBER)) == 0U)
    {
        return n;
    }
    n = wifi_put(n, "<p class=g>");
    if ((snap->info_flags & TFT_INFO_KCAL) != 0U)
    {
        sprintf(num, "%ld", (long)(snap->kcal + 0.5f));
        n = wifi_put(n, "<span>");
        n = wifi_put(n, num);
        n = wifi_put(n, "\xe5\x8d\x83\xe5\x8d\xa1</span>");
    }
    if ((snap->info_flags & TFT_INFO_CARB) != 0U)
    {
        wifi_fmt(num, snap->carb_g, 1U);
        n = wifi_put(n, "<span>");
        n = wifi_put(n, "\xe7\xa2\xb3\xe6\xb0\xb4");
        n = wifi_put(n, num);
        n = wifi_put(n, "\xe5\x85\x8b</span>");
    }
    if ((snap->info_flags & TFT_INFO_FIBER) != 0U)
    {
        wifi_fmt(num, snap->fiber_g, 1U);
        n = wifi_put(n, "<span>");
        n = wifi_put(n, "\xe7\xba\xa4\xe7\xbb\xb4");
        n = wifi_put(n, num);
        n = wifi_put(n, "\xe5\x85\x8b</span>");
    }
    return wifi_put(n, "</p>");
}

static void wifi_begin_screen(void)
{
    TFT_Snap snap;
    uint16_t n;
    char num[16];

    TFT_GetSnap(&snap);
    n = wifi_page_open();
    if (s_notice == 1U)
    {
        n = wifi_put(n, "<p class=m>\xe5\xb7\xb2\xe5\x8e\xbb\xe7\x9a\xae</p>");
    }
    else if (s_notice == 4U)
    {
        n = wifi_put(n, "<p class=m>\xe5\xb7\xb2\xe5\xa4\x8d\xe4\xbd\x8d</p>");
    }
    s_notice = 0U;

    if (snap.view == TFT_VIEW_SAVED)
    {
        n = wifi_put(n, "<p class=m>\xe5\xb7\xb2\xe4\xbf\x9d\xe5\xad\x98</p><p class=n>");
        n = wifi_name(n, snap.product);
        n = wifi_put(n, "</p>");
        if (snap.valid != 0U)
        {
            n = wifi_weight_card(n, snap.weight_g);
            n = wifi_price_card(n, snap.price, (uint8_t)(strcmp(snap.product, "banana") == 0));
        }
    }
    else if (snap.view == TFT_VIEW_CLEARED)
    {
        n = wifi_put(n, "<p class=m>\xe6\xb8\x85\xe5\x8d\x95\xe5\xb7\xb2\xe6\xb8\x85\xe7\xa9\xba</p>"
                        "<div class=t><span>\xe5\x90\x88\xe8\xae\xa1</span><b>0.00\xe5\x85\x83</b></div>");
    }
    else if (snap.view == TFT_VIEW_RECEIPT)
    {
        n = wifi_put(n, "<p class=n>\xe6\xb8\x85\xe5\x8d\x95</p><div class=t><span>\xe5\x90\x88\xe8\xae\xa1</span><b>");
        wifi_fmt(num, snap.receipt_total, 2U);
        n = wifi_put(n, num);
        n = wifi_put(n, "\xe5\x85\x83</b></div>");
    }
    else if ((snap.view == TFT_VIEW_RESULT) && (snap.valid != 0U))
    {
        n = wifi_put(n, "<p class=n>");
        n = wifi_name(n, snap.product);
        n = wifi_put(n, "</p><p class=u>");
        wifi_fmt(num, snap.price_per_kg, 1U);
        n = wifi_put(n, num);
        n = wifi_put(n, "\xe5\x85\x83/kg</p>");
        n = wifi_weight_card(n, snap.weight_g);
        n = wifi_price_card(n, snap.price, (uint8_t)(strcmp(snap.product, "banana") == 0));
        n = wifi_nut(n, &snap);
    }
    else
    {
        n = wifi_put(n, "<p class=n>READY</p>");
        n = wifi_weight_card(n, Scale_GetWeightG());
    }
    wifi_ship(n, 2U);
}

static void wifi_begin_send(const char *body)
{
    const char *list;
    const char *list_end;
    const char *hash;
    const char *cursor;
    uint16_t    n = 0U;
    uint8_t     rows = 0U;

    if (body == NULL)
    {
        body = "";
    }
    hash = strchr(body, '#');
    list = body;
    list_end = (hash != NULL) ? hash : (body + strlen(body));
    n = wifi_page_open();
    n = wifi_put(n, "<ul>");

    cursor = list;
    while (cursor < list_end)
    {
        const char *stop = cursor;

        while ((stop < list_end) && (*stop != ';'))
        {
            stop++;
        }
        if (stop > cursor)
        {
            n = wifi_row(n, cursor, stop);
            rows++;
        }
        cursor = (stop < list_end) ? (stop + 1) : stop;
    }
    if (rows == 0U)
    {
        n = wifi_put(n, "<p class=c>");
        if ((list_end > list) && (strchr(list, '|') == NULL))
        {
            n = wifi_span(n, list, list_end);
        }
        else if (s_kind == 1U)
        {
            n = wifi_put(n, "\xe6\xb8\x85\xe5\x8d\x95\xe6\x98\xaf\xe7\xa9\xba\xe7\x9a\x84");
        }
        else
        {
            n = wifi_put(n, "\xe8\xbf\x98\xe6\xb2\xa1\xe6\x9c\x89\xe7\xa7\xb0\xe9\x87\x8d\xe8\xae\xb0\xe5\xbd\x95");
        }
        n = wifi_put(n, "</p>");
    }
    n = wifi_put(n, "</ul>");
    if (hash != NULL)
    {
        n = wifi_put(n, "<div class=t><span>");
        n = wifi_put(n, "\xe5\x90\x88\xe8\xae\xa1");
        n = wifi_put(n, "</span><b>");
        n = wifi_put(n, hash + 1);
        n = wifi_put(n, "\xe5\x85\x83</b></div>");
    }
    wifi_ship(n, s_kind);
}

static void wifi_maybe_reset(void)
{
    if (s_reset_arm != 0U)
    {
        HAL_Delay(400U);
        NVIC_SystemReset();
    }
}

static void wifi_page_done(void)
{
    s_paint_ready = 1U;
}

uint8_t Wifi_Busy(void)
{
    return (s_paint != 0U) ? 1U : 0U;
}

void Wifi_CancelPaint(void)
{
    s_paint = 0U;
}

static void wifi_deferred(void)
{
    uint8_t paint;

    if ((s_paint_ready == 0U) || (s_phase != WIFI_PHASE_RUN))
    {
        return;
    }
    s_paint_ready = 0U;
    if (s_sync_receipt != 0U)
    {
        s_sync_receipt = 0U;
        Proto_SendCommand("receipt");
    }
    paint = s_paint;
    s_paint = 0U;
    if (paint == 3U)
    {
        TFT_ShowWeight(0.0f);
    }
    else if (paint == 4U)
    {
        TFT_ShowSaved();
    }
    else if (paint == 5U)
    {
        TFT_ShowCleared();
    }
}

static void wifi_run_kind(uint8_t kind)
{
    if (kind == 3U)
    {
        if (Proto_PressTare() != 0U)
        {
            s_notice = 1U;
            s_paint = 3U;
        }
        wifi_begin_screen();
        return;
    }
    if (kind == 4U)
    {
        Proto_PressSave();
        s_paint = 4U;
        wifi_begin_screen();
        return;
    }
    if (kind == 5U)
    {
        Proto_PressClear();
        s_paint = 5U;
        wifi_begin_screen();
        return;
    }
    if (kind == 6U)
    {
        Proto_PressReset();
        s_notice = 4U;
        s_reset_arm = 1U;
        wifi_begin_screen();
        return;
    }
    if (kind >= 2U)
    {
        wifi_begin_screen();
        return;
    }
    if (kind == 1U)
    {
        wifi_ask("receipt");
        if (s_pending != 0U)
        {
            s_sync_receipt = 1U;
        }
        return;
    }
    wifi_ask("records");
}

static void wifi_ask(const char *query)
{
    char line[64];

    if (s_pending != 0U || s_phase != WIFI_PHASE_RUN)
    {
        return;
    }
    sprintf(line, "{\"v\":1,\"type\":\"query\",\"query\":\"%s\"}", query);
    Proto_SendLine(line);
    s_pending    = 1U;
    s_pending_at = HAL_GetTick();
}

static void wifi_queue_close(uint8_t id)
{
    if ((s_udp != 0U) && (id == 4U))
    {
        return;
    }
    if (id < 5U)
    {
        s_drop |= (uint8_t)(1U << id);
    }
}

static void wifi_tcp_byte(uint8_t byte)
{
    uint8_t id = s_seen;

    if ((s_raw_bad != 0U) || (id >= 4U))
    {
        return;
    }
    if (byte == (uint8_t)'\r')
    {
        return;
    }
    if (byte != (uint8_t)'\n')
    {
        if ((s_get_len + 1U) < sizeof(s_get))
        {
            s_get[s_get_len] = (char)byte;
            s_get_len++;
        }
        if (s_get_len == 4U)
        {
            if (memcmp(s_get, "GET ", 4) != 0)
            {
                s_raw_bad = 1U;
                s_get_on  = 0U;
                s_get_len = 0U;
                wifi_queue_close(id);
            }
            else
            {
                s_http = (uint8_t)(s_http | (uint8_t)(1U << id));
            }
        }
        return;
    }
    s_get[s_get_len] = '\0';
    if ((s_get_len >= 4U) && (memcmp(s_get, "GET ", 4) == 0))
    {
        s_seen    = id;
        s_get_on  = 0U;
        s_raw_bad = 1U;
        wifi_on_esp_line(s_get);
        s_get_len = 0U;
        return;
    }
    s_raw_bad = 1U;
    s_get_on  = 0U;
    s_get_len = 0U;
    wifi_queue_close(id);
}

static void wifi_tcp_end(void)
{
    uint8_t id = s_seen;

    if ((s_raw_bad != 0U) || (id >= 4U))
    {
        s_raw_bad = 0U;
        return;
    }
    if ((s_get_len > 0U) && (s_get_len < 4U) && (memcmp("GET ", s_get, s_get_len) == 0))
    {
        s_get_on = 1U;
        s_get_id = id;
        return;
    }
    if ((s_get_len >= 4U) && (memcmp(s_get, "GET ", 4) == 0))
    {
        s_get_on = 1U;
        s_get_id = id;
        return;
    }
    if (s_get_len > 0U)
    {
        s_get_len = 0U;
        s_get_on  = 0U;
        wifi_queue_close(id);
    }
    s_raw_bad = 0U;
}

static uint8_t wifi_reply_done(const char *line)
{
    if ((line[0] == 'O') && (line[1] == 'K') && (line[2] == '\0'))
    {
        return 1U;
    }
    if (strncmp(line, "ERROR", 5) == 0)
    {
        return 1U;
    }
    if (strstr(line, "FAIL") != NULL)
    {
        return 1U;
    }
    return 0U;
}

static void wifi_close_one(void)
{
    char    cmd[20];
    uint8_t id;

    /* 上一条 AT 还没回答时不能再发，否则模块会把连接表堵死。 */
    if ((s_phase != WIFI_PHASE_RUN) || (s_at_wait != 0U) || (s_pending != 0U) || (s_drop == 0U))
    {
        return;
    }
    for (id = 0U; id < 5U; id++)
    {
        if ((s_udp != 0U) && (id == 4U))
        {
            s_drop &= (uint8_t)~(1U << id);
            continue;
        }
        if ((s_drop & (uint8_t)(1U << id)) == 0U)
        {
            continue;
        }
        if ((s_hold != 0U) && (id == s_link))
        {
            continue;
        }
        if ((s_next_ok != 0U) && (id == s_next_id))
        {
            continue;
        }
        s_drop &= (uint8_t)~(1U << id);
        sprintf(cmd, "AT+CIPCLOSE=%u", (unsigned)id);
        wifi_send(cmd);
        s_at_wait = 1U;
        s_at_due  = HAL_GetTick() + 800U;
        return;
    }
}

static void wifi_take_page(uint8_t id, uint8_t kind)
{
    if (((s_hold != 0U) && (id == s_link)) || ((s_next_ok != 0U) && (id == s_next_id)))
    {
        return;
    }
    if ((s_hold != 0U) || (s_pending != 0U) || (s_phase != WIFI_PHASE_RUN) || (s_at_wait != 0U))
    {
        if ((s_next_ok != 0U) && (s_next_id != id))
        {
            wifi_queue_close(s_next_id);
        }
        s_next_ok   = 1U;
        s_next_id   = id;
        s_next_kind = kind;
        s_drop &= (uint8_t)~(1U << id);
        return;
    }
    s_link = id;
    s_kind = kind;
    s_hold = 1U;
    s_drop &= (uint8_t)~(1U << id);
    wifi_note("get");
    wifi_run_kind(kind);
}

static uint8_t wifi_take_probe(uint8_t id, const char *body)
{
    uint8_t kind = 0U;

    if ((strstr(body, "generate_204") != NULL) || (strstr(body, "generate204") != NULL) ||
        (strstr(body, "gen_204") != NULL))
    {
        kind = 1U;
    }
    else if ((strstr(body, "hotspot-detect") != NULL) || (strstr(body, "canonical.html") != NULL))
    {
        kind = 2U;
    }
    else if (strstr(body, "connecttest.txt") != NULL)
    {
        kind = 3U;
    }
    else if (strstr(body, "ncsi.txt") != NULL)
    {
        kind = 4U;
    }
    else if (strstr(body, "success.txt") != NULL)
    {
        kind = 5U;
    }
    else
    {
        return 0U;
    }
    if ((s_probe_on != 0U) && (s_probe_id != id))
    {
        wifi_queue_close(s_probe_id);
    }
    s_probe_on   = 1U;
    s_probe_id   = id;
    s_probe_kind = kind;
    s_drop &= (uint8_t)~(1U << id);
    return 1U;
}

static void wifi_on_esp_line(char *line)
{
    char   *mark = strstr(line, "+IPD,");
    char   *body = line;
    uint8_t id = s_seen;
    uint8_t kind = 0U;

    /* 模块经常先单独来一行 +IPD，GET 在下一行。没有完整请求时不要关连接。 */
    if (mark != NULL)
    {
        mark += 5;
        if ((*mark >= '0') && (*mark <= '4'))
        {
            id = (uint8_t)(*mark - '0');
            s_seen = id;
        }
        body = strchr(mark, ':');
        if (body != NULL)
        {
            body++;
        }
        else
        {
            body = line;
        }
    }
    if ((strstr(body, "GET /") == NULL) || (strstr(body, "HTTP/") == NULL))
    {
        /* 只有 +IPD 头、还没看到正文时不能关。手机把任意域名指到本机后，
         * 加密连接没有 GET，不关就会占满 4 条网页连接。 */
        if ((mark == NULL) || (body == line) || (id >= 4U))
        {
            return;
        }
        if (((s_hold != 0U) && (id == s_link)) ||
            ((s_next_ok != 0U) && (id == s_next_id)) ||
            ((s_http & (uint8_t)(1U << id)) != 0U))
        {
            return;
        }
        if (body[0] != '\0')
        {
            wifi_queue_close(id);
        }
        return;
    }
    if (id < 4U)
    {
        s_http |= (uint8_t)(1U << id);
    }
    if (wifi_take_probe(id, body) != 0U)
    {
        return;
    }
    if (strstr(body, "GET /do/reset") != NULL)
    {
        kind = 6U;
    }
    else if (strstr(body, "GET /do/tare") != NULL)
    {
        kind = 3U;
    }
    else if (strstr(body, "GET /do/save") != NULL)
    {
        kind = 4U;
    }
    else if (strstr(body, "GET /do/clear") != NULL)
    {
        kind = 5U;
    }
    else if (strstr(body, "GET /receipt") != NULL)
    {
        kind = 1U;
    }
    else if (strstr(body, "GET /records") != NULL)
    {
        kind = 0U;
    }
    else if ((strstr(body, "GET / HTTP") != NULL) || (strstr(body, "GET /?") != NULL))
    {
        kind = 2U;
    }
    else
    {
        if (!((s_hold != 0U) && (id == s_link)))
        {
            wifi_queue_close(id);
        }
        return;
    }
    wifi_take_page(id, kind);
}

static void wifi_service_side(void)
{
    const char *body;

    if ((s_phase != WIFI_PHASE_RUN) || (s_at_wait != 0U) || (s_hold != 0U) || (s_pending != 0U))
    {
        return;
    }
    if (s_probe_on != 0U)
    {
        if (s_probe_kind == 1U)
        {
            body = "HTTP/1.1 204 No Content\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
        }
        else if (s_probe_kind == 3U)
        {
            body = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nMicrosoft Connect Test";
        }
        else if (s_probe_kind == 4U)
        {
            body = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nMicrosoft NCSI";
        }
        else if (s_probe_kind == 5U)
        {
            body = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nsuccess\n";
        }
        else
        {
            body = "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n<html><body>Success</body></html>";
        }
        s_link     = s_probe_id;
        s_keep     = 0U;
        s_probe_on = 0U;
        s_hold     = 1U;
        wifi_note("probe");
        wifi_begin_bytes((const uint8_t *)body, (uint16_t)strlen(body));
    }
}

static void wifi_on_sock_line(const char *line)
{
    if ((line[0] >= '0') && (line[0] <= '4') && (strstr(line, ",CLOSED") != NULL))
    {
        uint8_t id = (uint8_t)(line[0] - '0');

        if (!((s_udp != 0U) && (id == 4U)))
        {
            s_drop &= (uint8_t)~(1U << id);
            s_http &= (uint8_t)~(1U << id);
            if ((s_get_on != 0U) && (s_get_id == id))
            {
                s_get_on  = 0U;
                s_get_len = 0U;
            }
            wifi_note("closed");
        }
    }
    else if (strstr(line, ",CONNECT") != NULL)
    {
        wifi_note("connect");
    }
}

static uint8_t wifi_take(uint8_t *out)
{
    if (s_tail == s_head)
    {
        return 0U;
    }
    *out   = s_ring[s_tail];
    s_tail = (uint16_t)((s_tail + 1U) % WIFI_RING);
    return 1U;
}

static void wifi_revive(void)
{
    s_phase    = WIFI_PHASE_AT;
    s_hold     = 0U;
    s_at_wait  = 0U;
    s_pending  = 0U;
    s_drop     = 0U;
    s_next_ok  = 0U;
    s_probe_on = 0U;
    s_raw_left = 0U;
    s_keep     = 0U;
    wifi_open(115200U);
    if (s_phase != WIFI_PHASE_DEAD)
    {
        wifi_next_setup();
    }
}

static void wifi_push_line(void)
{
    s_line[s_line_len] = '\0';
    if ((s_line_len > 0U) && (strstr(s_line, "ready") != NULL))
    {
        /* The module rebooted at 115200. Start the access point again. */
        wifi_revive();
        s_line_len = 0U;
        return;
    }
    if (s_line_len > 0U)
    {
        if (s_phase < WIFI_PHASE_RUN)
        {
            wifi_note(s_line);
            if ((s_phase == WIFI_PHASE_UDP) && (strstr(s_line, "ALREADY") != NULL))
            {
                s_udp = 1U;
            }
            if (wifi_setup_accepted(s_line) != 0U)
            {
                if ((s_phase == WIFI_PHASE_UDP) && (strstr(s_line, "OK") != NULL))
                {
                    s_udp = 1U;
                }
                s_phase++;
                if (s_phase < WIFI_PHASE_RUN)
                {
                    wifi_next_setup();
                }
                else
                {
                    wifi_enter_run();
                }
            }
            else if ((s_phase == WIFI_PHASE_UDP) &&
                     ((strncmp(s_line, "ERROR", 5) == 0) || (strstr(s_line, "FAIL") != NULL)))
            {
                if ((s_udp != 0U) || (s_udp_try >= 2U))
                {
                    s_phase++;
                    wifi_next_setup();
                }
                else
                {
                    s_udp_try++;
                    wifi_next_setup();
                }
            }
        }
        else if (s_phase == WIFI_PHASE_RUN)
        {
            wifi_on_sock_line(s_line);
            /* 0,CLOSED is not the end of CIPCLOSE. Wait for a real OK or ERROR. */
            if ((s_at_wait != 0U) && (wifi_reply_done(s_line) != 0U))
            {
                s_at_wait = 0U;
            }
            wifi_on_esp_line(s_line);
        }
        else if (s_phase == WIFI_PHASE_SEND)
        {
            wifi_on_sock_line(s_line);
            if (strstr(s_line, "SEND OK") != NULL)
            {
                s_hold = 0U;
                if (s_keep == 0U)
                {
                    wifi_queue_close(s_link);
                }
                s_keep  = 0U;
                s_phase = WIFI_PHASE_RUN;
                wifi_page_done();
                wifi_maybe_reset();
            }
            else if ((strstr(s_line, "ERROR") != NULL) || (strstr(s_line, "FAIL") != NULL))
            {
                s_hold = 0U;
                if (s_keep == 0U)
                {
                    wifi_queue_close(s_link);
                }
                s_keep  = 0U;
                s_phase = WIFI_PHASE_RUN;
                wifi_page_done();
                wifi_maybe_reset();
            }
            else
            {
                wifi_on_esp_line(s_line);
            }
        }
    }
    s_line_len = 0U;
}

void Wifi_Init(void)
{
    s_head      = 0U;
    s_tail      = 0U;
    s_line_len  = 0U;
    s_phase     = 0U;
    s_link      = 0U;
    s_seen      = 0U;
    s_kind      = 0U;
    s_pending   = 0U;
    s_drop      = 0U;
    s_hold      = 0U;
    s_at_wait   = 0U;
    s_prompted  = 0U;
    s_next_ok   = 0U;
    s_next_id   = 0U;
    s_next_kind = 0U;
    s_udp       = 0U;
    s_udp_try   = 0U;
    s_keep      = 0U;
    s_probe_on  = 0U;
    s_raw_left  = 0U;
    s_raw_tcp   = 0U;
    s_raw_bad   = 0U;
    s_get_len   = 0U;
    s_get_on    = 0U;
    s_get_id    = 0U;
    s_notice       = 0U;
    s_reset_arm    = 0U;
    s_paint        = 0U;
    s_paint_ready  = 0U;
    s_sync_receipt = 0U;
    s_http         = 0U;
    wifi_open(115200U);
    if (s_phase != WIFI_PHASE_DEAD)
    {
        wifi_next_setup();
    }
}

void Wifi_Poll(void)
{
    uint8_t byte;

    if (s_phase == WIFI_PHASE_DEAD)
    {
        return;
    }
    if ((s_pending != 0U) && (s_at_wait == 0U) && (s_phase == WIFI_PHASE_RUN) &&
        ((HAL_GetTick() - s_pending_at) > 2000U))
    {
        wifi_begin_send("\xe7\x94\xb5\xe8\x84\x91\xe8\xbf\x98\xe6\xb2\xa1\xe6\x9c\x89\xe5\x9b\x9e\xe7\xad\x94\xef\xbc\x8c\xe8\xaf\xb7\xe5\x86\x8d\xe5\x88\xb7\xe6\x96\xb0\xe4\xb8\x80\xe6\xac\xa1\xe3\x80\x82");
    }

    while (wifi_take(&byte) != 0U)
    {
        if (s_raw_left > 0U)
        {
            if (s_raw_tcp != 0U)
            {
                wifi_tcp_byte(byte);
            }
            s_raw_left--;
            if ((s_raw_left == 0U) && (s_raw_tcp != 0U))
            {
                wifi_tcp_end();
            }
            continue;
        }
        if ((s_phase == WIFI_PHASE_SEND) && (s_prompted == 0U) && (s_line_len == 0U) && (byte == (uint8_t)'>'))
        {
            s_prompted = 1U;
            HAL_UART_Transmit(&huart4, (uint8_t *)s_page, s_page_len, 800U);
            s_line_len = 0U;
            continue;
        }
        if (byte == (uint8_t)'\n')
        {
            wifi_push_line();
        }
        else if (byte != (uint8_t)'\r')
        {
            if (s_line_len + 1U < WIFI_LINE)
            {
                s_line[s_line_len] = (char)byte;
                s_line_len++;
            }
            else
            {
                if ((s_line_len > 5U) && (s_line[0] == '+') &&
                    (s_line[5] >= '0') && (s_line[5] <= '3'))
                {
                    wifi_queue_close((uint8_t)(s_line[5] - '0'));
                }
                s_line_len = 0U;
            }
        }
        if ((s_line_len > 0U) && (wifi_dns_header() != 0U))
        {
            /* DNS payload is binary. Do not parse it as AT text. */
        }
    }

    if ((s_phase < WIFI_PHASE_RUN) && ((int32_t)(HAL_GetTick() - s_deadline) >= 0))
    {
        if (s_phase == WIFI_PHASE_AT)
        {
            /* ESP-01 on this board is 115200. A late "ready" used to fall
             * through to 9600 and then stay silent. */
            wifi_open(115200U);
            if (s_phase != WIFI_PHASE_DEAD)
            {
                wifi_next_setup();
            }
        }
        else
        {
            s_phase++;
            if (s_phase < WIFI_PHASE_RUN)
            {
                wifi_next_setup();
            }
            else
            {
                wifi_enter_run();
            }
        }
    }
    else if ((s_phase == WIFI_PHASE_SEND) && ((int32_t)(HAL_GetTick() - s_deadline) >= 0))
    {
        s_hold  = 0U;
        s_keep  = 0U;
        if ((s_udp == 0U) || (s_link != 4U))
        {
            wifi_queue_close(s_link);
        }
        s_phase = WIFI_PHASE_RUN;
        wifi_page_done();
        wifi_maybe_reset();
    }
    if ((s_at_wait != 0U) && ((int32_t)(HAL_GetTick() - s_at_due) >= 0))
    {
        s_at_wait = 0U;
    }
    /* 先关掉这一条网页连接，再画屏幕。浏览器要等连接关闭才算页面完成。 */
    wifi_close_one();
    wifi_deferred();
    if ((s_phase == WIFI_PHASE_RUN) && (s_pending == 0U) && (s_hold == 0U) &&
        (s_at_wait == 0U) && (s_next_ok != 0U) && (s_probe_on == 0U))
    {
        uint8_t id = s_next_id;
        uint8_t kind = s_next_kind;

        s_next_ok = 0U;
        s_link    = id;
        s_kind    = kind;
        s_hold    = 1U;
        s_drop &= (uint8_t)~(1U << id);
        wifi_note("get");
        wifi_run_kind(kind);
    }
    wifi_service_side();
}

void Wifi_OnPcLine(const char *line)
{
    const char *text;
    static char body[480];
    uint16_t    i;

    if ((s_pending == 0U) || (s_phase != WIFI_PHASE_RUN) || (s_at_wait != 0U))
    {
        return;
    }
    text = strstr(line, "\"text\":\"");
    if (text == NULL)
    {
        return;
    }
    text += 8;
    i = 0U;
    while ((text[i] != '\0') && (text[i] != '"') && ((i + 1U) < sizeof(body)))
    {
        body[i] = text[i];
        i++;
    }
    body[i] = '\0';
    wifi_begin_send(body);
}

void Wifi_Uart4Isr(void)
{
    uint32_t sr = huart4.Instance->SR;

    if ((sr & USART_SR_RXNE) != 0U)
    {
        uint8_t  byte = (uint8_t)(huart4.Instance->DR & 0xFFU);
        uint16_t next = (uint16_t)((s_head + 1U) % WIFI_RING);

        if (next != s_tail)
        {
            s_ring[s_head] = byte;
            s_head         = next;
        }
    }
    else if ((sr & (USART_SR_ORE | USART_SR_FE | USART_SR_NE | USART_SR_PE)) != 0U)
    {
        (void)huart4.Instance->DR;
    }
}

#else

uint8_t Wifi_Busy(void)
{
    return 0U;
}

void Wifi_CancelPaint(void)
{
}

void Wifi_Init(void)
{
}

void Wifi_Poll(void)
{
}

void Wifi_OnPcLine(const char *line)
{
    (void)line;
}

void Wifi_Uart4Isr(void)
{
}

#endif
