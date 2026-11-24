/**
 * @file src/cursor_share.h
 * @brief The host's pointer for clients that draw it themselves.
 *
 * Windows desktop duplication reports the pointer's shape and whether it is shown; the control
 * stream sends both to the clients that asked for them (the client then shows it as its own
 * pointer, with no network delay), and the capture leaves the pointer out of the picture while
 * such a client is connected.
 */
#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>

namespace cursor_share {
  /// The pointer's pixel format (the DXGI_OUTDUPL_POINTER_SHAPE_TYPE values).
  enum class kind_e : std::uint8_t {
    monochrome = 1,  ///< 1 bit per pixel: the AND mask's rows, then the XOR mask's rows
    color = 2,  ///< 32-bit BGRA with alpha
    masked_color = 4,  ///< 32-bit BGRA; alpha 0xFF: the color is XORed with the screen, 0: it replaces it
  };

  struct shape_t {
    std::uint32_t serial;  ///< new for each different shape
    kind_e kind;
    std::uint16_t width;
    std::uint16_t height;  ///< the pointer's rows (a monochrome shape's data has twice as many)
    std::uint16_t pitch;  ///< bytes per row of data
    std::int16_t hot_x;
    std::int16_t hot_y;
    std::vector<std::uint8_t> data;
  };

  struct state_t {
    bool here;  ///< shown on this screen
    bool shown;  ///< shown on the desktop (false: an app hid it; true and not here: on another screen)
    std::int32_t x;  ///< the pointer image's top left on this screen
    std::int32_t y;
  };

  /**
   * @brief A new pointer shape from the capture (the same shape again changes nothing).
   * @param height The pointer's rows (half the monochrome data's rows).
   */
  void set_shape(kind_e kind, int width, int height, int pitch, int hot_x, int hot_y, const std::uint8_t *data, std::size_t size);

  /// Where the pointer is and whether it is shown, from the capture.
  void set_state(bool here, bool shown, int x, int y);

  /// Changes whenever the shape or the visibility changes (not for movement alone).
  std::uint64_t generation();

  /**
   * @brief The current pointer.
   * @return false while no capture has reported one (a capture method without pointer data).
   */
  bool get(std::uint64_t &generation, std::shared_ptr<const shape_t> &shape, state_t &state);

  /// A connected client draws the pointer itself (counted; the capture leaves it out meanwhile).
  void add_client();
  void remove_client();
  bool client_draws();
}  // namespace cursor_share
