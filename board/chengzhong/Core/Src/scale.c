/**
  ******************************************************************************
  * @file    scale.c
  * @brief   称重的核心：把 HX711 的原始读数换成克，判断八个状态，处理去皮。
  *
  *          几个和文档对齐的要点：
  *           - 上电不做自动去皮，零点只来自标定常数。
  *           - 每来一个新样本才发一条 weight，没新样本不补发。
  *           - 状态变了才发 status，状态没变不重复发。
  *           - 拿走东西时先发一次 WEIGHT_REMOVED，下一状态才是 ZERO。
  *           - 只有 空秤/在变/已稳/刚拿走 这四种情况允许去皮。
  ******************************************************************************
  */

#include "scale.h"
#include "config.h"
#include "hx711.h"
#include "protocol.h"
#include "voice.h"

#define SCALE_HIST_LEN          24U     /* 稳定判断最多回看这么多个样本 */
#define SCALE_EMA_ALPHA         0.4f    /* 滤波强度，越大越跟手、越小越平滑 */
#define SCALE_WINDOW_MIN_COUNT  4U      /* 稳定判断至少要看这么多个样本 */

static ScaleState_t s_state            = SCALE_BOOT;

/* 去皮偏移：相对标定零点 CALIB_ZERO_RAW 的差值。上电为 0（文档要求）。 */
static int32_t      s_tare_raw         = 0;
static float        s_counts_per_g     = 1.0f;

static float        s_ema              = 0.0f;   /* 滤波后的净重 */
static uint8_t      s_ema_ready        = 0U;

static float        s_hist[SCALE_HIST_LEN];
static uint32_t     s_hist_tick[SCALE_HIST_LEN];
static uint8_t      s_hist_idx         = 0U;
static uint8_t      s_hist_cnt         = 0U;

static uint32_t     s_last_sample_tick = 0U;
static uint8_t      s_pending_removed  = 0U;    /* 上面有东西，等着报一次"拿走" */
static uint8_t      s_hold_zero        = 0U;    /* 去皮后先待在 ZERO，别马上跳 WEIGHT_CHANGED */

static float        s_weight_g         = 0.0f;
static float        s_tare_g           = 0.0f;
static uint8_t      s_stable           = 0U;

#if (VOICE_ANNOUNCE_WEIGHT == 1)
static uint8_t      s_weight_announced   = 0U;
static float        s_weight_announced_g = 0.0f;
#endif

static void    scale_set_state(ScaleState_t st);
static void    scale_reset_filter(void);
static void    scale_push_history(float g);
static uint8_t scale_window_stable(void);

/**
  * @brief  状态名转成文档里规定的字符串
  */
const char *Scale_StateName(ScaleState_t st)
{
    switch (st)
    {
        case SCALE_BOOT:           return "BOOT";
        case SCALE_READY:          return "READY";
        case SCALE_ZERO:           return "ZERO";
        case SCALE_WEIGHT_CHANGED: return "WEIGHT_CHANGED";
        case SCALE_WEIGHT_STABLE:  return "WEIGHT_STABLE";
        case SCALE_WEIGHT_REMOVED: return "WEIGHT_REMOVED";
        case SCALE_OVERLOAD:       return "OVERLOAD";
        case SCALE_ERROR:          return "ERROR";
        default:                   return "ERROR";
    }
}

/**
  * @brief  状态变了才发 status，没变就不发
  */
static void scale_set_state(ScaleState_t st)
{
    if (st == s_state)
    {
        return;
    }

    s_state = st;
    Proto_SendStatus(Scale_StateName(s_state));
}

void Scale_SendCurrentStatus(void)
{
    Proto_SendStatus(Scale_StateName(s_state));
}

/**
  * @brief  清空滤波和稳定判断用的历史数据
  */
static void scale_reset_filter(void)
{
    uint8_t i;

    for (i = 0U; i < SCALE_HIST_LEN; i++)
    {
        s_hist[i]      = 0.0f;
        s_hist_tick[i] = 0U;
    }

    s_hist_idx        = 0U;
    s_hist_cnt        = 0U;
    s_ema             = 0.0f;
    s_ema_ready       = 0U;
    s_stable          = 0U;
    s_pending_removed = 0U;
}

static void scale_push_history(float g)
{
    s_hist[s_hist_idx]      = g;
    s_hist_tick[s_hist_idx] = HAL_GetTick();

    s_hist_idx = (uint8_t)((s_hist_idx + 1U) % SCALE_HIST_LEN);
    if (s_hist_cnt < SCALE_HIST_LEN)
    {
        s_hist_cnt++;
    }
}

/**
  * @brief  最近 STABLE_TIME_MS 毫秒内，重量波动是否不超过 STABLE_TOLERANCE_G
  * @retval 1 = 稳住了
  */
static uint8_t scale_window_stable(void)
{
    uint32_t now = HAL_GetTick();
    float    mn  = 0.0f;
    float    mx  = 0.0f;
    uint8_t  n   = 0U;
    uint8_t  i;

    for (i = 0U; i < s_hist_cnt; i++)
    {
        if ((now - s_hist_tick[i]) <= STABLE_TIME_MS)
        {
            if (n == 0U)
            {
                mn = s_hist[i];
                mx = s_hist[i];
            }
            else
            {
                if (s_hist[i] < mn) { mn = s_hist[i]; }
                if (s_hist[i] > mx) { mx = s_hist[i]; }
            }
            n++;
        }
    }

    if ((n >= SCALE_WINDOW_MIN_COUNT) && ((mx - mn) <= STABLE_TOLERANCE_G))
    {
        return 1U;
    }
    return 0U;
}

/**
  * @brief  上电初始化。注意：这里不做自动去皮。
  */
void Scale_Init(void)
{
    HX711_Init();

    s_counts_per_g = (CALIB_COUNTS_PER_G > 0.0f) ? CALIB_COUNTS_PER_G : 1.0f;
    s_tare_raw     = 0;                 /* 偏移先给 0，符合文档要求 */
    s_weight_g     = 0.0f;
    s_tare_g       = 0.0f;

    scale_reset_filter();
    s_hold_zero = 0U;

    s_last_sample_tick = HAL_GetTick();

    s_state = SCALE_READY;
    Proto_SendStatus(Scale_StateName(s_state));
}

/**
  * @brief  主循环里反复调用。有新的样本才会做事。
  */
void Scale_Loop(void)
{
    int32_t raw   = 0;
    float   grams;
    float   abs_w;
    uint8_t empty;
    uint8_t overload;
#if (VOICE_ANNOUNCE_WEIGHT == 1)
    ScaleState_t prev_state;
#endif

    /* 没有新样本：只检查是不是已经太久没数据了 */
    if (HX711_IsReady() == 0U)
    {
        if ((HAL_GetTick() - s_last_sample_tick) >= HX711_TIMEOUT_MS)
        {
            if (s_state != SCALE_ERROR)
            {
                /* 刚进故障：先报状态，再补一条 weight 行告诉电脑"这条不能计价"。
                 * 故障期间平时不发 weight（没有新样本就不发），
                 * 所以只有这一条，不会刷屏。 */
                scale_set_state(SCALE_ERROR);
                Proto_SendWeight(s_weight_g, 0U, s_tare_g, "error");
            }
        }
        return;
    }

    if (HX711_ReadRaw(&raw) != 0)
    {
        if (s_state != SCALE_ERROR)
        {
            scale_set_state(SCALE_ERROR);
            Proto_SendWeight(s_weight_g, 0U, s_tare_g, "error");
        }
        return;
    }

    s_last_sample_tick = HAL_GetTick();

    /* 原始值 -> 克。零点 = 标定零点 + 去皮偏移 */
    grams   = ((float)(raw - (CALIB_ZERO_RAW + s_tare_raw))) / s_counts_per_g;
    s_tare_g = ((float)s_tare_raw) / s_counts_per_g;

    /* 轻度滤波，读数才不至于抖得到处跳 */
    if (s_ema_ready == 0U)
    {
        s_ema       = grams;
        s_ema_ready = 1U;
    }
    else
    {
        s_ema += SCALE_EMA_ALPHA * (grams - s_ema);
    }
    s_weight_g = s_ema;

    scale_push_history(s_ema);
    s_stable = scale_window_stable();

#if (DEBUG_PRINT_RAW == 1)
    Proto_SendRawDebug(raw, s_ema);
#endif

    /* ---------------- 八个状态的判断 ---------------- */
    abs_w    = (s_ema < 0.0f) ? -s_ema : s_ema;
    empty    = (abs_w <= ZERO_THRESHOLD_G) ? 1U : 0U;
    overload = (abs_w >= (SCALE_FULL_SCALE_G * SCALE_OVERLOAD_RATIO)) ? 1U : 0U;

#if (VOICE_ANNOUNCE_WEIGHT == 1)
    prev_state = s_state;
#endif

    if (overload != 0U)
    {
        scale_set_state(SCALE_OVERLOAD);
    }
    else if (empty != 0U)
    {
        if (s_hold_zero != 0U)
        {
            /* 刚做完去皮：按文档直接留在 ZERO，
             * 等读数重新稳住再把"保持"解除，免得中间冒一次多余的 WEIGHT_CHANGED。 */
            if (s_stable != 0U)
            {
                s_hold_zero = 0U;
            }
            scale_set_state(SCALE_ZERO);
        }
        else if (s_pending_removed != 0U)
        {
            /* 东西刚被拿走：只报一次 WEIGHT_REMOVED。
             * 文档要求"下一状态就是 ZERO"，所以这里把"保持 ZERO"打开，
             * 免得读数还在晃的时候插一次多余的 WEIGHT_CHANGED 进去。 */
            s_pending_removed = 0U;
            s_hold_zero       = 1U;
            scale_set_state(SCALE_WEIGHT_REMOVED);
        }
        else
        {
            /* 空秤继续放着就留在 ZERO，不反复说拿走了 */
            scale_set_state((s_stable != 0U) ? SCALE_ZERO : SCALE_WEIGHT_CHANGED);
        }
    }
    else
    {
        /* 有东西放上来，去皮后的"保持 ZERO"立刻解除 */
        s_hold_zero       = 0U;
        s_pending_removed = 1U;
        scale_set_state((s_stable != 0U) ? SCALE_WEIGHT_STABLE : SCALE_WEIGHT_CHANGED);
    }

#if (VOICE_ANNOUNCE_WEIGHT == 1)
    /* 刚稳住：念一遍重量。同一个重量反复抖动，不重复念。 */
    if ((s_state == SCALE_ZERO) || (s_state == SCALE_WEIGHT_REMOVED))
    {
        s_weight_announced = 0U;
    }
    else if ((s_state == SCALE_WEIGHT_STABLE) && (prev_state != SCALE_WEIGHT_STABLE))
    {
        float diff = s_ema - s_weight_announced_g;

        if ((s_weight_announced == 0U) || (diff > 2.0f) || (diff < -2.0f))
        {
            Voice_SayWeight(s_ema);
            s_weight_announced   = 1U;
            s_weight_announced_g = s_ema;
        }
    }
#endif

    /* ---------------- 每来一个新样本发一条 weight ---------------- */
    {
        uint8_t     line_stable;
        const char *line_status;

#if (WEIGHT_STABLE_FLAG_ONLY_WHEN_LOADED == 1)
        line_stable = (s_state == SCALE_WEIGHT_STABLE) ? 1U : 0U;
#else
        /* 软件同学的要求：进入 WEIGHT_STABLE 和 ZERO 之后 stable 就是 true。
         * ZERO 本来就是"空秤且稳住了"的意思，这两个状态下直接给 true。 */
        line_stable = ((s_state == SCALE_ZERO) || (s_state == SCALE_WEIGHT_STABLE))
                      ? 1U : s_stable;
#endif

        /* weight 行自己的 status：正常 ok、过载 overload、故障 error */
        if (s_state == SCALE_OVERLOAD)
        {
            line_status = "overload";
        }
        else if (s_state == SCALE_ERROR)
        {
            line_status = "error";
        }
        else
        {
            line_status = "ok";
        }

        Proto_SendWeight(s_ema, line_stable, s_tare_g, line_status);
    }
}

/**
  * @brief  去皮。
  *         只有 空秤 / 在变 / 已稳 / 刚拿走 这四种情况才做，
  *         上电、过载、故障时一律返回失败，而且零点保持不动。
  *         做法：连续取 TARE_SAMPLE_COUNT 个新样本求平均，当成新的零点。
  * @retval 1 = 成功，0 = 失败
  */
uint8_t Scale_Tare(void)
{
    int32_t  sum   = 0;
    int32_t  raw   = 0;
    uint8_t  n     = 0U;
    uint32_t start;

    if ((s_state != SCALE_READY)          &&
        (s_state != SCALE_ZERO)           &&
        (s_state != SCALE_WEIGHT_CHANGED) &&
        (s_state != SCALE_WEIGHT_STABLE)  &&
        (s_state != SCALE_WEIGHT_REMOVED))
    {
        return 0U;      /* BOOT/过载/故障：失败，零点不动 */
    }

    start = HAL_GetTick();
    while (n < (uint8_t)TARE_SAMPLE_COUNT)
    {
        if ((HAL_GetTick() - start) >= TARE_TIMEOUT_MS)
        {
            break;      /* 3 秒还凑不满 10 个样本，认输 */
        }

        if (HX711_IsReady() != 0U)
        {
            if (HX711_ReadRaw(&raw) != 0)
            {
                break;
            }
            sum += raw;
            n++;
            s_last_sample_tick = HAL_GetTick();
        }
    }

    if (n < (uint8_t)TARE_SAMPLE_COUNT)
    {
        return 0U;      /* 取不到足够样本：失败，零点不动 */
    }

    /* 新的零点 = 这次的平均值；相对标定零点记为皮重 */
    s_tare_raw = (int32_t)(sum / (int32_t)TARE_SAMPLE_COUNT) - CALIB_ZERO_RAW;
    s_tare_g   = ((float)s_tare_raw) / s_counts_per_g;

    scale_reset_filter();
    s_weight_g = 0.0f;
    s_state    = SCALE_ZERO;    /* 去皮完就进 ZERO，状态由上层在 ack 之后报出去 */
    s_hold_zero = 1U;           /* 先保持在 ZERO，直到读数重新稳住 */

    return 1U;
}

ScaleState_t Scale_GetState(void)   { return s_state;    }
float        Scale_GetWeightG(void) { return s_weight_g; }
float        Scale_GetTareG(void)   { return s_tare_g;   }
uint8_t      Scale_IsStable(void)   { return s_stable;   }
