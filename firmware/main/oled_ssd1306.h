/**
 * @file oled_ssd1306.h
 * @brief Self-contained 128x64 SSD1306 I2C OLED task for the Seeed XIAO
 *        Expansion Board. Independent of the RM67162/LVGL display path.
 *
 * Reads vitals via edge_get_vitals() and renders text. Gracefully no-ops if
 * no panel ACKs at 0x3C, so it is safe to start unconditionally.
 */
#pragma once
#include "esp_err.h"

/** Start the OLED task. Returns ESP_OK whether or not a panel was found. */
esp_err_t oled_task_start(void);
