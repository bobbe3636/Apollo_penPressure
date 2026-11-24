// Test stub: just what virtual_tablet.{h,cpp} use from Apollo's platform header
#pragma once
#include <cstdint>
#include <string>

#include "src/config.h"
#include "src/logging.h"

// moonlight-common-c Limelight.h values
#define LI_TOUCH_EVENT_HOVER 0x00
#define LI_TOUCH_EVENT_DOWN 0x01
#define LI_TOUCH_EVENT_UP 0x02
#define LI_TOUCH_EVENT_MOVE 0x03
#define LI_TOUCH_EVENT_CANCEL 0x04
#define LI_TOUCH_EVENT_BUTTON_ONLY 0x05
#define LI_TOUCH_EVENT_HOVER_LEAVE 0x06
#define LI_TOUCH_EVENT_CANCEL_ALL 0x07
#define LI_TOOL_TYPE_UNKNOWN 0x00
#define LI_TOOL_TYPE_PEN 0x01
#define LI_TOOL_TYPE_ERASER 0x02
#define LI_PEN_BUTTON_PRIMARY 0x01
#define LI_PEN_BUTTON_SECONDARY 0x02
#define LI_PEN_BUTTON_TERTIARY 0x04
#define LI_TILT_UNKNOWN 0xFF
#define LI_ROT_UNKNOWN 0xFFFF

namespace platf {
  struct pen_input_t {
    std::uint8_t eventType;
    std::uint8_t toolType;
    std::uint8_t penButtons;
    std::uint8_t tilt;
    std::uint16_t rotation;
    float x;
    float y;
    float pressureOrDistance;
    float contactAreaMajor;
    float contactAreaMinor;
  };
}  // namespace platf
