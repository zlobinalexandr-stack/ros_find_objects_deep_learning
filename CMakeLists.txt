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

catkin_python_setup()

catkin_package(CATKIN_DEPENDS cv_bridge find_object_2d geometry_msgs rospy sensor_msgs std_msgs tf2_ros)

catkin_install_python(PROGRAMS scripts/find_object_3d_web_node
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})

install(DIRECTORY launch config web
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})

if(CATKIN_ENABLE_TESTING)
  catkin_add_nosetests(test)
endif()
