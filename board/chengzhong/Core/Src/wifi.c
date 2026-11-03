/**
  ******************************************************************************
  * @file    wifi.c
  * @brief   ESP-01 走 USART3，PD8 发送、PD9 接收。手机连热点 SmartScale 后打开
  *          http://192.168.4.1/records 或 /receipt 。
  *          模块答 AT，真正的记录在电脑上。
  ******************************************************************************
  */

#include "wifi.h"
#include "config.h"
#include "protocol.h"
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
#define WIFI_DNS           320U

static UART_HandleTypeDef huart4;
static volatile uint8_t  s_ring[WIFI_RING];
static volatile uint16_t s_head;
static volatile uint16_t s_tail;

static char     s_line[WIFI_LINE];
static uint16_t s_line_len;
static char     s_page[WIFI_PAGE];
static uint16_t s_page_len;
static uint8_t  s_phase;
static uint8_t  s_baud_alt;
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
static uint8_t  s_dns_ready;
static uint16_t s_dns_len;
static uint16_t s_dns_port;
static uint16_t s_raw_left;
static uint16_t s_raw_len;
static char     s_dns_ip[16];
static uint8_t  s_raw[WIFI_DNS];
static uint8_t  s_dns[WIFI_DNS];

static void wifi_send(const char *text);
static void wifi_arm(uint32_t wait_ms);
static void wifi_next_setup(void);
static void wifi_on_esp_line(char *line);
static void wifi_ask(const char *query);
static void wifi_begin_send(const char *body);
static void wifi_begin_bytes(const uint8_t *data, uint16_t len);
static void wifi_service_side(void);
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
        if (s_udp_try == 0U)
        {
            wifi_send("AT+CIPSTART=4,\"UDP\",\"255.255.255.255\",53,53,2");
        }
        else if (s_udp_try == 1U)
        {
            wifi_send("AT+CIPSTART=4,\"UDP\",\"192.168.4.255\",53,53,2");
        }
        else
        {
            wifi_send("AT+CIPSTART=4,\"UDP\",\"192.168.4.2\",53,53,2");
        }
    }
    else if (s_phase == WIFI_PHASE_SERVER)
    {
        wifi_send("AT+CIPSERVER=1,80");
    }
    else if (s_phase == WIFI_PHASE_STO)
    {
        wifi_send("AT+CIPSTO=0");
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
    char cmd[72];

    if ((len == 0U) || (len >= WIFI_PAGE))
    {
        return;
    }
    if (data != (const uint8_t *)s_page)
    {
        memcpy(s_page, data, len);
    }
    s_page_len = len;
    if ((s_keep != 0U) && (s_dns_ip[0] != '\0'))
    {
        sprintf(cmd, "AT+CIPSEND=%u,%u,\"%s\",%u",
                (unsigned)s_link, (unsigned)len, s_dns_ip, (unsigned)s_dns_port);
    }
    else
    {
        sprintf(cmd, "AT+CIPSEND=%u,%u", (unsigned)s_link, (unsigned)len);
    }
    wifi_send(cmd);
    wifi_arm(3000U);
    s_prompted = 0U;
    s_pending  = 0U;
    s_phase    = WIFI_PHASE_SEND;
}

static uint16_t wifi_dns_name_end(const uint8_t *q, uint16_t qlen, uint16_t i)
{
    uint16_t guard = 0U;

    while ((i < qlen) && (guard < 40U))
    {
        uint8_t lab = q[i];

        guard++;
        if (lab == 0U)
        {
            return (uint16_t)(i + 1U);
        }
        if ((lab & 0xC0U) == 0xC0U)
        {
            return (uint16_t)(i + 2U);
        }
        if ((uint16_t)(i + 1U + lab) > qlen)
        {
            return 0U;
        }
        i = (uint16_t)(i + 1U + lab);
    }
    return 0U;
}

static uint16_t wifi_dns_reply(const uint8_t *q, uint16_t qlen, uint8_t *out)
{
    uint16_t name_end;
    uint16_t qend;
    uint16_t qtype;
    uint16_t n;
    uint8_t  an;
    static const uint8_t ans[16] = {
        0xC0U, 0x0CU, 0x00U, 0x01U, 0x00U, 0x01U, 0x00U, 0x00U,
        0x00U, 0x3CU, 0x00U, 0x04U, 192U, 168U, 4U, 1U
    };

    if (qlen < 12U)
    {
        return 0U;
    }
    name_end = wifi_dns_name_end(q, qlen, 12U);
    if ((name_end == 0U) || ((uint16_t)(name_end + 4U) > qlen))
    {
        return 0U;
    }
    qend  = (uint16_t)(name_end + 4U);
    qtype = (uint16_t)(((uint16_t)q[name_end] << 8) | q[name_end + 1U]);
    an    = (qtype == 1U) ? 1U : 0U;
    if ((uint16_t)(qend + ((an != 0U) ? 16U : 0U)) > WIFI_DNS)
    {
        return 0U;
    }
    memcpy(out, q, qend);
    out[2]  = 0x81U;
    out[3]  = 0x80U;
    out[6]  = 0U;
    out[7]  = an;
    out[8]  = 0U;
    out[9]  = 0U;
    out[10] = 0U;
    out[11] = 0U;
    n = qend;
    if (an != 0U)
    {
        memcpy(out + n, ans, 16U);
        n = (uint16_t)(n + 16U);
    }
    return n;
}

static void wifi_dns_store(void)
{
    uint16_t n = wifi_dns_reply(s_raw, s_raw_len, s_dns);

    s_raw_len = 0U;
    if (n == 0U)
    {
        return;
    }
    s_dns_len   = n;
    s_dns_ready = 1U;
    wifi_note("dnsq");
}

static uint8_t wifi_dns_header(void)
{
    char    *p;
    char    *comma;
    unsigned len = 0U;
    unsigned port = 0U;
    uint16_t i;
    uint16_t ncopy;

    if ((s_udp == 0U) || (s_line_len < 7U) || (memcmp(s_line, "+IPD,4,", 7) != 0))
    {
        return 0U;
    }
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
    s_dns_ip[0] = '\0';
    s_dns_port  = 0U;
    if (*p == ',')
    {
        p++;
        comma = strchr(p, ',');
        if (comma != NULL)
        {
            ncopy = (uint16_t)(comma - p);
            if (ncopy >= sizeof(s_dns_ip))
            {
                ncopy = (uint16_t)(sizeof(s_dns_ip) - 1U);
            }
            memcpy(s_dns_ip, p, ncopy);
            s_dns_ip[ncopy] = '\0';
            p = comma + 1;
            while ((*p >= '0') && (*p <= '9'))
            {
                port = (port * 10U) + (unsigned)(*p - '0');
                p++;
            }
            s_dns_port = (uint16_t)port;
        }
    }
    s_line_len = 0U;
    if ((len == 0U) || (len > 1024U))
    {
        s_raw_left = 0U;
        return 1U;
    }
    s_raw_left = (uint16_t)len;
    s_raw_len  = 0U;
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
        n = wifi_put(n, "<p class=empty>");
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

    n = wifi_put(n,
                 "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n"
                 "<!DOCTYPE html><html><head><meta charset=utf-8>"
                 "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
                 "<title>");
    n = wifi_put(n, "\xe6\x99\xba\xe8\x83\xbd\xe7\x94\xb5\xe5\xad\x90\xe7\xa7\xa4");
    n = wifi_put(n,
                 "</title><style>"
                 "body{margin:0;background:#f3efe6;color:#1c1915;font-family:sans-serif;font-size:17px}"
                 "a{color:#1e3d34;text-decoration:none}"
                 "header{padding:24px 18px 16px;background:#1e3d34;color:#f7f3ea}"
                 ".mark{margin:0;font-size:12px;letter-spacing:.16em;opacity:.7}"
                 "h1{margin:4px 0 0;font-size:28px}"
                 "nav{display:flex;gap:8px;margin-top:16px}"
                 "nav a{flex:1;text-align:center;background:#f3efe6;border-radius:999px;padding:12px 0;font-size:16px}"
                 "nav a.on{background:#e4c27a;font-weight:700}"
                 "main{padding:16px 16px 36px}"
                 "ul{list-style:none;margin:0;padding:0}"
                 "li{background:#fff;border-radius:16px;padding:16px;margin:0 0 12px;display:flex;gap:8px}"
                 "b{flex:1;font-size:20px}"
                 "span{color:#6f675e;font-size:15px}"
                 "em{font-style:normal;font-size:20px;font-weight:700}"
                 ".empty{background:#fff;border-radius:16px;padding:28px 16px;color:#6f675e;font-size:18px}"
                 ".total{margin-top:4px;background:#1e3d34;color:#f7f3ea;border-radius:16px;padding:16px;display:flex}"
                 ".total b{flex:none;margin-left:auto;font-size:28px;color:#f7f3ea}"
                 "a.go{display:block;margin-top:18px;text-align:center;font-size:16px}"
                 "</style></head><body><header><p class=mark>SMART SCALE</p><h1>");
    n = wifi_put(n, "\xe6\x99\xba\xe8\x83\xbd\xe7\x94\xb5\xe5\xad\x90\xe7\xa7\xa4");
    n = wifi_put(n, "</h1><nav><a href=/records");
    if (s_kind == 0U)
    {
        n = wifi_put(n, " class=on");
    }
    n = wifi_put(n, ">");
    n = wifi_put(n, "\xe7\xa7\xb0\xe9\x87\x8d\xe8\xae\xb0\xe5\xbd\x95");
    n = wifi_put(n, "</a><a href=/receipt");
    if (s_kind == 1U)
    {
        n = wifi_put(n, " class=on");
    }
    n = wifi_put(n, ">");
    n = wifi_put(n, "\xe8\xb4\xad\xe7\x89\xa9\xe6\xb8\x85\xe5\x8d\x95");
    n = wifi_put(n, "</a></nav></header><main><ul>");

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
        n = wifi_put(n, "<p class=empty>");
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
        n = wifi_put(n, "<div class=total><span>");
        n = wifi_put(n, "\xe5\x90\x88\xe8\xae\xa1");
        n = wifi_put(n, "</span><b>");
        n = wifi_put(n, hash + 1);
        n = wifi_put(n, "\xe5\x85\x83</b></div>");
    }
    n = wifi_put(n, "<a class=go href=>");
    n = wifi_put(n, "\xe5\x88\xb7\xe6\x96\xb0\xe8\xbf\x99\xe4\xb8\x80\xe9\xa1\xb5");
    n = wifi_put(n, "</a></main></body></html>");
    if ((n + 1U) >= WIFI_PAGE)
    {
        return;
    }
    s_page[n] = '\0';
    s_page_len = n;
    s_keep     = 0U;
    wifi_begin_bytes((const uint8_t *)s_page, n);
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
    if (kind != 0U)
    {
        wifi_ask("receipt");
    }
    else
    {
        wifi_ask("records");
    }
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
        return;
    }
    if (wifi_take_probe(id, body) != 0U)
    {
        return;
    }
    if (strstr(body, "GET /receipt") != NULL)
    {
        kind = 1U;
    }
    else if ((strstr(body, "GET /records") == NULL) &&
             (strstr(body, "GET / HTTP") == NULL) &&
             (strstr(body, "GET /?") == NULL))
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
        return;
    }
    if (s_dns_ready != 0U)
    {
        s_link      = 4U;
        s_keep      = 1U;
        s_dns_ready = 0U;
        wifi_note("dns");
        wifi_begin_bytes(s_dns, s_dns_len);
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

static void wifi_push_line(void)
{
    s_line[s_line_len] = '\0';
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
            }
            else if ((strstr(s_line, "ERROR") != NULL) || (strstr(s_line, "FAIL") != NULL))
            {
                s_hold = 0U;
                if ((s_keep != 0U) && (s_dns_ip[0] != '\0'))
                {
                    /* Extended UDP CIPSEND was rejected. Retry toward the last peer. */
                    s_dns_ip[0] = '\0';
                    s_dns_ready = 1U;
                }
                else if (s_keep == 0U)
                {
                    wifi_queue_close(s_link);
                }
                s_keep  = 0U;
                s_phase = WIFI_PHASE_RUN;
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
    s_baud_alt  = 0U;
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
    s_dns_ready = 0U;
    s_raw_left  = 0U;
    s_dns_ip[0] = '\0';
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
            if (s_raw_len + 1U < WIFI_DNS)
            {
                s_raw[s_raw_len] = byte;
                s_raw_len++;
            }
            s_raw_left--;
            if (s_raw_left == 0U)
            {
                wifi_dns_store();
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
        if ((s_phase == WIFI_PHASE_AT) && (s_baud_alt == 0U))
        {
            s_baud_alt = 1U;
            wifi_open(9600U);
            if (s_phase != WIFI_PHASE_DEAD)
            {
                wifi_next_setup();
            }
        }
        else if (s_phase == WIFI_PHASE_AT)
        {
            wifi_note("silent");
            s_phase = WIFI_PHASE_DEAD;
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
    }
    if ((s_at_wait != 0U) && ((int32_t)(HAL_GetTick() - s_at_due) >= 0))
    {
        s_at_wait = 0U;
    }
    /* Close the finished link and wait for OK before starting another page. */
    wifi_close_one();
    wifi_service_side();
    if ((s_phase == WIFI_PHASE_RUN) && (s_pending == 0U) && (s_hold == 0U) &&
        (s_at_wait == 0U) && (s_next_ok != 0U) && (s_probe_on == 0U) && (s_dns_ready == 0U))
    {
        uint8_t id = s_next_id;
        uint8_t kind = s_next_kind;

        s_next_ok = 0U;
        s_link    = id;
        s_kind    = kind;
        s_hold    = 1U;
        s_drop &= (uint8_t)~(1U << id);
        wifi_note("get");
        if (kind != 0U)
        {
            wifi_ask("receipt");
        }
        else
        {
            wifi_ask("records");
        }
    }
}

void Wifi_OnPcLine(const char *line)
{
    const char *text;
    char        body[480];
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
