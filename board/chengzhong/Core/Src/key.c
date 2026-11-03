/**
  ******************************************************************************
  * @file    key.c
  * @brief   去皮按键：引脚初始化、消抖、按下沿检测。
  ******************************************************************************
  */

#include "key.h"
#include "config.h"

typedef struct
{
    uint8_t  raw_prev;
    uint8_t  stable;
    uint32_t change_tick;
    uint32_t last_event_tick;
} KeyState_t;

static KeyState_t s_tare_key;
static KeyState_t s_save_key;
static KeyState_t s_receipt_key;
static KeyState_t s_clear_key;

/**
  * @brief  按端口自动打开对应的 GPIO 时钟
  */
static void key_enable_port_clock(GPIO_TypeDef *port)
{
    if (port == GPIOA)      { __HAL_RCC_GPIOA_CLK_ENABLE(); }
    else if (port == GPIOB) { __HAL_RCC_GPIOB_CLK_ENABLE(); }
    else if (port == GPIOC) { __HAL_RCC_GPIOC_CLK_ENABLE(); }
    else if (port == GPIOD) { __HAL_RCC_GPIOD_CLK_ENABLE(); }
    else if (port == GPIOE) { __HAL_RCC_GPIOE_CLK_ENABLE(); }
    else                    { /* 其它端口不用管 */ }
}

/**
  * @brief  读一次电平，换算成"1 = 按下"
  */
static uint8_t key_read_active_low(GPIO_TypeDef *port, uint16_t pin)
{
    GPIO_PinState st = HAL_GPIO_ReadPin(port, pin);
    return (st == GPIO_PIN_RESET) ? 1U : 0U;
}

static void key_init_pin(GPIO_TypeDef *port, uint16_t pin, KeyState_t *state)
{
    GPIO_InitTypeDef gpio = {0};

    key_enable_port_clock(port);
    gpio.Pin = pin;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(port, &gpio);

    state->raw_prev = key_read_active_low(port, pin);
    state->stable = state->raw_prev;
    state->change_tick = HAL_GetTick();
    state->last_event_tick = HAL_GetTick() - ACTION_KEY_LOCKOUT_MS;
}

static uint8_t key_pressed(GPIO_TypeDef *port, uint16_t pin, KeyState_t *state,
                           uint32_t debounce_ms)
{
    uint8_t raw = key_read_active_low(port, pin);
    uint8_t ret = 0U;

    if (raw != state->raw_prev)
    {
        state->raw_prev = raw;
        state->change_tick = HAL_GetTick();
    }
    else if ((raw != state->stable) &&
             ((HAL_GetTick() - state->change_tick) >= debounce_ms))
    {
        state->stable = raw;
        if ((raw != 0U) &&
            ((HAL_GetTick() - state->last_event_tick) >= ACTION_KEY_LOCKOUT_MS))
        {
            state->last_event_tick = HAL_GetTick();
            ret = 1U;
        }
    }

    return ret;
}

/**
  * @brief  初始化按键引脚
  */
void Key_Init(void)
{
    key_init_pin(TARE_KEY_PORT, TARE_KEY_PIN, &s_tare_key);
    key_init_pin(SAVE_KEY_PORT, SAVE_KEY_PIN, &s_save_key);
    key_init_pin(RECEIPT_KEY_PORT, RECEIPT_KEY_PIN, &s_receipt_key);
    key_init_pin(CLEAR_KEY_PORT, CLEAR_KEY_PIN, &s_clear_key);
}

/**
  * @brief  消抖 + 按下沿检测。
  *         电平必须连续保持 TARE_KEY_DEBOUNCE_MS 毫秒才算有效变化，
  *         并且只在"松开 -> 按下"那一次返回 1。
  */
uint8_t Key_TarePressed(void)
{
    return key_pressed(TARE_KEY_PORT, TARE_KEY_PIN, &s_tare_key,
                       TARE_KEY_DEBOUNCE_MS);
}

uint8_t Key_SavePressed(void)
{
    return key_pressed(SAVE_KEY_PORT, SAVE_KEY_PIN, &s_save_key,
                       ACTION_KEY_DEBOUNCE_MS);
}

uint8_t Key_ReceiptPressed(void)
{
    return key_pressed(RECEIPT_KEY_PORT, RECEIPT_KEY_PIN, &s_receipt_key,
                       ACTION_KEY_DEBOUNCE_MS);
}

uint8_t Key_ClearPressed(void)
{
    return key_pressed(CLEAR_KEY_PORT, CLEAR_KEY_PIN, &s_clear_key,
                       ACTION_KEY_DEBOUNCE_MS);
}
