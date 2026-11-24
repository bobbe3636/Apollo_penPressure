// Test stub: the config values virtual_tablet.cpp reads
#pragma once
#include <string>

namespace config {
  struct input_t {
    int pen_virtual_tablet_port = 47001;
    std::string pen_virtual_tablet_model = "intuos";
  };

  inline input_t input;
}  // namespace config
