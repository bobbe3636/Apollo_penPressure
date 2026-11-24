// Test harness around Apollo's real virtual_tablet.cpp (stubbed config/logging headers).
//   test_vt reports             -> hex of the Intuos reports for fixed pen states
//   test_vt serve <model> <s>   -> serve the tablet on 127.0.0.1:47100 (pen events on udp 47001) for s seconds
// Nothing is plugged into Windows (the tablet stays unplugged unless a stream asks for it).
//
// Build (MSYS2/WinLibs g++; -static: another libstdc++ on PATH breaks it), from this folder:
//   g++ -std=gnu++23 -O1 -Wall -Wextra -static -I stub -I ../../src/platform/windows test_vt.cpp -o test_vt.exe -lws2_32
// Run (the GitHub build does the same):
//   start test_vt.exe serve intuos 45 & python vt_client.py intuos   (USB/IP, the Wacom handshake, pen reports)
#include "virtual_tablet.cpp"

#include <cstdio>

using namespace platf::virtual_tablet;

static void hex(const char *label, int i, const std::vector<uint8_t> &v) {
  std::printf("%s %d ", label, i);
  for (auto b : v) {
    std::printf("%02x", b);
  }
  std::printf("\n");
}

int main(int argc, char **argv) {
  std::string mode = argc > 1 ? argv[1] : "reports";
  if (mode == "reports") {
    struct S {
      bool in_range, tip;
      uint8_t tool, buttons;
      float x, y, pressure, distance;
      int tx, ty;
    };

    const S states[] = {
      {true, false, LI_TOOL_TYPE_PEN, 0, 0.5f, 0.5f, 0.0f, 0.3f, 0, 0},
      {true, true, LI_TOOL_TYPE_PEN, LI_PEN_BUTTON_PRIMARY, 0.25f, 0.75f, 0.6f, 0.0f, -40, 0},
      {true, true, LI_TOOL_TYPE_ERASER, 0, 0.1f, 0.9f, 0.5f, 0.0f, 10, -20},
      {false, false, LI_TOOL_TYPE_ERASER, 0, 0.1f, 0.9f, 0.0f, 1.0f, 0, 0},
      {true, false, LI_TOOL_TYPE_PEN, LI_PEN_BUTTON_SECONDARY | LI_PEN_BUTTON_TERTIARY, 1.0f, 0.0f, 0.0f, 0.8f, 95, -95},
      {true, true, LI_TOOL_TYPE_PEN, 0, 0.0f, 1.0f, 1.0f, 0.0f, -90, 90},
    };
    int i = 0;
    for (const auto &s : states) {
      pen_state_t p;
      p.in_range = s.in_range;
      p.tip = s.tip;
      p.tool = s.tool;
      p.buttons = s.buttons;
      p.x = s.x;
      p.y = s.y;
      p.pressure = s.pressure;
      p.distance = s.distance;
      p.tilt_x = s.tx;
      p.tilt_y = s.ty;
      hex("r30", i, p.report30(0x1234, 0x5678));
      hex("r06ipm", i, p.report06_ipm(0x1234, 0x5678));
      i++;
    }
    return 0;
  }

  if (mode == "serve") {
    config::input.pen_virtual_tablet_model = argc > 2 ? argv[2] : "intuos";
    int seconds = argc > 3 ? std::atoi(argv[3]) : 60;
    // The token pen events over UDP must carry (vt_client.py sends the same)
    SetEnvironmentVariableA("APOLLO_PEN_TOKEN", "00112233445566778899aabbccddeeff");
    start();
    std::this_thread::sleep_for(std::chrono::seconds(seconds));
    stop();
    return 0;
  }
  return 2;
}
