/**
  ******************************************************************************
  * @file    stm32f1xx_it.c
  * @brief   中断服务函数。这里只干两件事：给 HAL 计时、把串口收到的东西交给 HAL。
  ******************************************************************************
  */

#include "main.h"
#include "stm32f1xx_it.h"
#include "protocol.h"
#include "wifi.h"

extern UART_HandleTypeDef huart1;

/*============================================================================*/
/*                    Cortex-M3 处理器异常处理                                 */
/*============================================================================*/

void NMI_Handler(void)
{
    while (1)
    {
    }
}

void HardFault_Handler(void)
{
    while (1)
    {
    }
}

void MemManage_Handler(void)
{
    while (1)
    {
    }
}

void BusFault_Handler(void)
{
    while (1)
    {
    }
}

void UsageFault_Handler(void)
{
    while (1)
    {
    }
}

void SVC_Handler(void)
{
}

void DebugMon_Handler(void)
{
}

void PendSV_Handler(void)
{
}

/**
  * @brief  系统滴答：HAL_GetTick() 的毫秒计时全靠它
  */
void SysTick_Handler(void)
{
    HAL_IncTick();
}

/**
  * @brief  串口 1 中断：直接交给协议层处理（不再走 HAL 的 UART 状态机）
  */
void USART1_IRQHandler(void)
{
    Proto_Usart1Isr();
}

void USART3_IRQHandler(void)
{
    Wifi_Uart4Isr();
}
