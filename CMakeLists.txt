cmake_minimum_required(VERSION 3.0.2)
project(find_object_3d_web)

find_package(catkin REQUIRED COMPONENTS
  cv_bridge
  find_object_2d
  geometry_msgs
  rospy
  sensor_msgs
  std_msgs
  tf2_ros
)
find_package(OpenCV REQUIRED)
find_package(Qt5 REQUIRED COMPONENTS Core)

# The Melodic binary package installs this upstream header under
# include/find_object, while some source builds export it directly.  Locate the
# header instead of assuming that the ROS package name is also its include
# namespace.
find_path(FIND_OBJECT_INCLUDE_DIR FindObject.h
  HINTS ${find_object_2d_INCLUDE_DIRS} ${catkin_INCLUDE_DIRS}
  PATH_SUFFIXES find_object find_object_2d)
if(NOT FIND_OBJECT_INCLUDE_DIR)
  message(FATAL_ERROR "FindObject.h was not found; install the find_object_2d development headers")
endif()

catkin_python_setup()

catkin_package(CATKIN_DEPENDS cv_bridge find_object_2d geometry_msgs rospy sensor_msgs std_msgs tf2_ros)

include_directories(${catkin_INCLUDE_DIRS} ${OpenCV_INCLUDE_DIRS} ${FIND_OBJECT_INCLUDE_DIR})

add_executable(find_object_session_generator src/find_object_session_generator.cpp)
target_link_libraries(find_object_session_generator
  ${catkin_LIBRARIES} ${OpenCV_LIBRARIES} Qt5::Core)

catkin_install_python(PROGRAMS scripts/find_object_3d_web_node scripts/find_object_2d_session_manager
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})

install(TARGETS find_object_session_generator
  RUNTIME DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})

install(DIRECTORY launch config
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})

if(CATKIN_ENABLE_TESTING)
  catkin_add_nosetests(test)
endif()
