// Test stub: BOOST_LOG(level) << ... prints one line to stderr
#pragma once
#include <iostream>
#include <string_view>

struct test_log_line {
  ~test_log_line() {
    std::cerr << std::endl;
  }

  template<class T>
  test_log_line &operator<<(const T &t) {
    std::cerr << t;
    return *this;
  }
};

#define BOOST_LOG(level) test_log_line()
