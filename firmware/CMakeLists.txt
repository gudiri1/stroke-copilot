cmake_minimum_required(VERSION 3.13)

# Needs PICO_SDK_PATH in the environment, or pico_sdk_import.cmake beside this file.
include(pico_sdk_import.cmake)

project(stroke_copilot_driver C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()

add_executable(driver main.c)
pico_generate_pio_header(driver ${CMAKE_CURRENT_LIST_DIR}/step.pio)
target_link_libraries(driver pico_stdlib hardware_pio)

pico_enable_stdio_usb(driver 1)
pico_enable_stdio_uart(driver 0)
pico_add_extra_outputs(driver)
