/**
 * @file src/cursor_share.cpp
 * @brief The host's pointer for clients that draw it themselves.
 */
#include "cursor_share.h"

#include <algorithm>
#include <atomic>
#include <mutex>

namespace cursor_share {
  namespace {
    // Pointers larger than this are not shared (Windows draws them at most 256 pixels wide)
    constexpr int MAX_SIZE = 512;

    std::mutex mutex;
    std::shared_ptr<const shape_t> current_shape;
    state_t current_state {};
    bool published = false;
    std::uint32_t next_serial = 1;
    std::atomic<std::uint64_t> current_generation {0};
    std::atomic<int> clients {0};
  }  // namespace

  void set_shape(kind_e kind, int width, int height, int pitch, int hot_x, int hot_y, const std::uint8_t *data, std::size_t size) {
    if (kind != kind_e::monochrome && kind != kind_e::color && kind != kind_e::masked_color) {
      return;
    }
    if (width <= 0 || height <= 0 || width > MAX_SIZE || height > MAX_SIZE || pitch <= 0 || pitch > 4 * MAX_SIZE) {
      return;
    }
    std::size_t rows = kind == kind_e::monochrome ? 2 * (std::size_t) height : (std::size_t) height;
    std::size_t needed = rows * (std::size_t) pitch;
    std::size_t row_bytes = kind == kind_e::monochrome ? ((std::size_t) width + 7) / 8 : 4 * (std::size_t) width;
    if (data == nullptr || size < needed || (std::size_t) pitch < row_bytes) {
      return;
    }

    std::lock_guard lg {mutex};
    if (current_shape && current_shape->kind == kind && current_shape->width == width && current_shape->height == height &&
        current_shape->pitch == pitch && current_shape->hot_x == hot_x && current_shape->hot_y == hot_y &&
        std::equal(data, data + needed, current_shape->data.begin(), current_shape->data.end())) {
      return;
    }

    auto shape = std::make_shared<shape_t>();
    shape->serial = next_serial++;
    shape->kind = kind;
    shape->width = (std::uint16_t) width;
    shape->height = (std::uint16_t) height;
    shape->pitch = (std::uint16_t) pitch;
    shape->hot_x = (std::int16_t) std::clamp(hot_x, 0, width - 1);
    shape->hot_y = (std::int16_t) std::clamp(hot_y, 0, height - 1);
    shape->data.assign(data, data + needed);

    current_shape = std::move(shape);
    published = true;
    current_generation++;
  }

  void set_state(bool here, bool shown, int x, int y) {
    std::lock_guard lg {mutex};
    shown = shown || here;
    bool changed = !published || current_state.here != here || current_state.shown != shown;
    current_state = {here, shown, x, y};
    published = true;
    if (changed) {
      current_generation++;
    }
  }

  std::uint64_t generation() {
    return current_generation.load(std::memory_order_acquire);
  }

  bool get(std::uint64_t &generation, std::shared_ptr<const shape_t> &shape, state_t &state) {
    std::lock_guard lg {mutex};
    if (!published) {
      return false;
    }
    generation = current_generation.load(std::memory_order_acquire);
    shape = current_shape;
    state = current_state;
    return true;
  }

  void add_client() {
    clients++;
  }

  void remove_client() {
    if (clients.fetch_sub(1) <= 0) {
      clients++;  // never below zero
    }
  }

  bool client_draws() {
    return clients.load(std::memory_order_relaxed) > 0;
  }
}  // namespace cursor_share
