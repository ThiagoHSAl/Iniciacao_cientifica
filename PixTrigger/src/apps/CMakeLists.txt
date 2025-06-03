cmake_minimum_required(VERSION 3.10)
project(pixtrigger CXX)

# Specify C++17 standard for MAVSDK compatibility
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Include directories for your project's headers
# Assuming 'src/include' contains common headers like capture.h, geotag.h etc.
include_directories(src/include)
include_directories(src) # If your .h files are directly in src

# Add your source files to the executable
# Assuming capture.cpp, geotag.cpp, usb.cpp, path.cpp are in 'src/'
add_executable(pixtrigger
    main.cpp
    src/capture.cpp
    src/geotag.cpp
    src/usb.cpp
    src/path.cpp
)

# --- Find and link external libraries ---

# Find MAVSDK
# This will try to find MAVSDKConfig.cmake or mavsdk-config.cmake
find_package(MAVSDK REQUIRED)
if (MAVSDK_FOUND)
    message(STATUS "MAVSDK found. Version: ${MAVSDK_VERSION_STR}")
    # Link to the main MAVSDK library. This typically pulls in all necessary plugins.
    target_link_libraries(pixtrigger MAVSDK::mavsdk)
else()
    message(FATAL_ERROR "MAVSDK not found. Please ensure it's installed and in CMake's search path.")
endif()

# Find libgphoto2
# This automatically handles include paths and link libraries.
find_package(GPHOTO2 REQUIRED)
if (GPHOTO2_FOUND)
    message(STATUS "GPHOTO2 found. Version: ${GPHOTO2_VERSION_STR}")
    # Link to the gphoto2 and gphoto2_port libraries
    target_link_libraries(pixtrigger GPHOTO2::gphoto2 GPHOTO2::gphoto2_port)
else()
    message(FATAL_ERROR "GPHOTO2 not found. Please ensure libgphoto2-dev is installed.")
endif()

# --- OPTIONAL: WiringPi (Only if you still need it) ---
# It's recommended to remove wiringPi from your C++ code and CMake if not used.
# If you still need it, this is a safer way to link:
# find_library(WIRINGPI_LIBRARY wiringPi)
# if(WIRINGPI_LIBRARY)
#     message(STATUS "wiringPi library found.")
#     target_link_libraries(pixtrigger ${WIRINGPI_LIBRARY})
# else()
#     message(WARNING "wiringPi library not found. If your code depends on it, compilation might fail.")
# endif()