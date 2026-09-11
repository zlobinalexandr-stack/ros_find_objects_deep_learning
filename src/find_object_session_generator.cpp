#include <find_object_2d/FindObject.h>

#include <opencv2/imgcodecs.hpp>
#include <QCoreApplication>
#include <QFileInfo>
#include <QString>

#include <cerrno>
#include <cstdlib>
#include <dirent.h>
#include <iostream>
#include <limits>
#include <map>
#include <string>

namespace
{
bool parseImageName(const std::string & name, int & id)
{
  const std::string suffix = ".image";
  if (name.size() <= suffix.size() ||
      name.compare(name.size() - suffix.size(), suffix.size(), suffix) != 0)
  {
    return false;
  }
  const std::string number = name.substr(0, name.size() - suffix.size());
  char * end = 0;
  errno = 0;
  const long value = std::strtol(number.c_str(), &end, 10);
  if (errno || !end || *end || value < 0 || value > std::numeric_limits<int>::max())
  {
    return false;
  }
  id = static_cast<int>(value);
  return true;
}
}

int main(int argc, char ** argv)
{
  QCoreApplication application(argc, argv);
  if (argc != 3)
  {
    std::cerr << "Usage: find_object_session_generator STORAGE_DIRECTORY SESSION_PATH\n";
    return 2;
  }

  const std::string directory = argv[1];
  DIR * handle = opendir(directory.c_str());
  if (!handle)
  {
    std::cerr << "Cannot open object storage " << directory << "\n";
    return 1;
  }
  std::map<int, std::string> images;
  for (dirent * entry = readdir(handle); entry; entry = readdir(handle))
  {
    int id = -1;
    if (parseImageName(entry->d_name, id))
    {
      images[id] = directory + "/" + entry->d_name;
    }
  }
  closedir(handle);

  find_object::FindObject detector;
  for (std::map<int, std::string>::const_iterator iter = images.begin();
       iter != images.end(); ++iter)
  {
    const cv::Mat image = cv::imread(iter->second, cv::IMREAD_COLOR);
    if (image.empty())
    {
      std::cerr << "Cannot decode object image " << iter->second << "\n";
      return 1;
    }
    detector.addObjectAndUpdate(
        image, iter->first, QString::fromStdString(iter->second));
  }
  detector.saveSession(QString::fromLocal8Bit(argv[2]));
  if (!QFileInfo(QString::fromLocal8Bit(argv[2])).isFile())
  {
    std::cerr << "find_object_2d did not create session " << argv[2] << "\n";
    return 1;
  }
  std::cout << "Saved " << images.size() << " object(s) to " << argv[2] << "\n";
  return 0;
}
