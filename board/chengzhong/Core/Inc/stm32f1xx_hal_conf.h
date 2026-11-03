/**
  ******************************************************************************
  * @file    stm32f1xx_hal_conf.h
  * @brief   HAL 配置。这里决定哪些 HAL 模块参与编译。
  *          本工程只用到这些：RCC / GPIO / DMA / UART / PWR / FLASH / EXTI / TIM / CORTEX。
  *          以后要用 SPI、I2C、ADC，就把对应的模块打开，并把源文件加进 Keil 工程。
  ******************************************************************************
  */

#ifndef __STM32F1xx_HAL_CONF_H
#define __STM32F1xx_HAL_CONF_H

#ifdef __cplusplus
extern "C" {
#endif

/* ########################## Module Selection ############################## */

#define HAL_MODULE_ENABLED
#define HAL_CORTEX_MODULE_ENABLED
#define HAL_DMA_MODULE_ENABLED
#define HAL_EXTI_MODULE_ENABLED
#define HAL_FLASH_MODULE_ENABLED
#define HAL_GPIO_MODULE_ENABLED
#define HAL_PWR_MODULE_ENABLED
#define HAL_RCC_MODULE_ENABLED
#define HAL_SPI_MODULE_ENABLED
/* TIM 没有被秤用到。这台 Keil 只能链接 32KB，不编译定时器驱动。 */
/* #define HAL_TIM_MODULE_ENABLED */
#define HAL_UART_MODULE_ENABLED

/* ########################## Oscillator Values ############################# */

#if !defined  (HSE_VALUE)
#define HSE_VALUE               8000000U   /* 外部晶振频率，8MHz */
#endif

#if !defined  (HSE_STARTUP_TIMEOUT)
#define HSE_STARTUP_TIMEOUT     100U
#endif

#if !defined  (HSI_VALUE)
#define HSI_VALUE               8000000U   /* 内部 RC 振荡器频率 */
#endif

#if !defined  (LSI_VALUE)
#define LSI_VALUE               40000U
#endif

#if !defined  (LSE_VALUE)
#define LSE_VALUE               32768U
#endif

#if !defined  (LSE_STARTUP_TIMEOUT)
#define LSE_STARTUP_TIMEOUT     5000U
#endif

/* ########################### System Configuration ######################### */

#define  VDD_VALUE                    3300U
#define  TICK_INT_PRIORITY            0x0FU
#define  USE_RTOS                     0U
#define  PREFETCH_ENABLE              1U
#define  USE_HAL_UART_REGISTER_CALLBACKS    0U
#define  USE_HAL_TIM_REGISTER_CALLBACKS     0U

/* ########################## Assert Selection ############################## */

/* #define USE_FULL_ASSERT    1U */

/* Includes ------------------------------------------------------------------*/

#ifdef HAL_RCC_MODULE_ENABLED
#include "stm32f1xx_hal_rcc.h"
#endif

#ifdef HAL_GPIO_MODULE_ENABLED
#include "stm32f1xx_hal_gpio.h"
#endif

#ifdef HAL_EXTI_MODULE_ENABLED
#include "stm32f1xx_hal_exti.h"
#endif

#ifdef HAL_DMA_MODULE_ENABLED
#include "stm32f1xx_hal_dma.h"
#endif

#ifdef HAL_CORTEX_MODULE_ENABLED
#include "stm32f1xx_hal_cortex.h"
#endif

#ifdef HAL_FLASH_MODULE_ENABLED
#include "stm32f1xx_hal_flash.h"
#endif

#ifdef HAL_PWR_MODULE_ENABLED
#include "stm32f1xx_hal_pwr.h"
#endif

#ifdef HAL_TIM_MODULE_ENABLED
#include "stm32f1xx_hal_tim.h"
#endif

#ifdef HAL_UART_MODULE_ENABLED
#include "stm32f1xx_hal_uart.h"
#endif

#ifdef HAL_SPI_MODULE_ENABLED
#include "stm32f1xx_hal_spi.h"
#endif

/* Exported macro ------------------------------------------------------------*/

#ifdef  USE_FULL_ASSERT
#define assert_param(expr) ((expr) ? (void)0U : assert_failed((uint8_t *)__FILE__, __LINE__))
void assert_failed(uint8_t *file, uint32_t line);
#else
#define assert_param(expr) ((void)0U)
#endif

#ifdef __cplusplus
}
#endif

#endif /* __STM32F1xx_HAL_CONF_H */
