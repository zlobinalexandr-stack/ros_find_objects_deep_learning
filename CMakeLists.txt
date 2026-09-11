cmake_minimum_required(VERSION 3.0.2)
project(find_object_3d_web)

find_package(catkin REQUIRED COMPONENTS
  cv_bridge
  find_object_2d
  geometry_msgs
  rospy
  sensor_msgs
  std_msgs
  tf2_geometry_msgs
  tf2_ros
)
catkin_python_setup()

catkin_package(CATKIN_DEPENDS cv_bridge find_object_2d geometry_msgs rospy sensor_msgs std_msgs tf2_geometry_msgs tf2_ros)

catkin_install_python(PROGRAMS scripts/find_object_3d_web_node scripts/find_object_2d_session_manager
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})

# Compatibility with workspaces that still carry the optional native generator
# from an earlier revision.  Never register an install rule for a missing CMake
# target: the current objects_path implementation does not build this target.
if(TARGET find_object_session_generator)
  install(TARGETS find_object_session_generator
    RUNTIME DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})
endif()

install(DIRECTORY launch config
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})

if(CATKIN_ENABLE_TESTING)
  catkin_add_nosetests(test)
endif()
