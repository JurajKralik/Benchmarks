cmake_minimum_required(VERSION 3.16)
project(bench_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Release flags (CMake will add -O3 for Release on most toolchains)
add_executable(bench_cpp src/main.cpp)

# Helpful warnings
target_compile_options(bench_cpp PRIVATE -Wall -Wextra -Wpedantic)
