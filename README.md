# find_object_3d_web

Пакет ROS Melodic добавляет к [`find_object_2d`](https://wiki.ros.org/find_object_2d) простой web-интерфейс выбора шаблона и вычисляет положение найденного объекта по карте глубины. Браузер отправляет выделенный фрагмент как `sensor_msgs/Image` в `/find_object_2d/object`. Для каждого результата `ObjectsStamped` центр шаблона проецируется гомографией в изображение, глубина берётся как медиана небольшого окна, а координаты вычисляются по матрице `K` из `CameraInfo`.

## Результат

Узел публикует динамические TF:

```text
<frame_id сообщения /video/camera_info> -> object_<id>
```

Положение относительно `base_link` можно получить стандартным TF-запросом, если frame камеры уже связан с деревом робота:

```bash
rosrun tf tf_echo base_link object_1
```

Ориентация TF единичная: из одной глубины определяется положение, но не ориентация объекта.

## Установка (Melodic / Ubuntu 18.04)

```bash
sudo apt install ros-melodic-find-object-2d ros-melodic-cv-bridge python-opencv python-numpy
cd ~/catkin_ws/src
git clone <URL-этого-репозитория> find_object_3d_web
cd ..
catkin_make
source devel/setup.bash
```

## Запуск

1. Запустите камеру и `ros_deep_learning` DepthNet.
2. Запустите `find_object_2d` на **том же RGB-изображении**, которое передано этому пакету. Например:

   ```bash
   rosrun find_object_2d find_object_2d image:=/video/image_raw
   ```

3. Запустите узел:

   ```bash
   roslaunch find_object_3d_web find_object_3d_web.launch
   ```

4. Откройте `http://<IP-робота>:8080`, обведите объект и нажмите «Добавить объект».
5. Проверьте результат:

   ```bash
   rosrun tf tf_echo <camera_info_frame> object_0
   rostopic echo /objectsStamped
   ```

Заданные в launch-файле значения по умолчанию соответствуют указанным топикам:

| Назначение | Топик |
|---|---|
| RGB | `/video/image_raw` |
| глубина | `/depthnet/depth` |
| калибровка | `/video/camera_info` |
| детекции | `/objectsStamped` |
| новый шаблон | `/find_object_2d/object` |

Имена можно изменить аргументами:

```bash
roslaunch find_object_3d_web find_object_3d_web.launch \
  image_topic:=/video/image_raw depth_topic:=/depthnet/depth \
  camera_info_topic:=/video/camera_info objects_topic:=/objectsStamped \
  object_topic:=/find_object_2d/object port:=8080
```

Для совместимости с пакетами ROS Melodic шаблон передаётся через image-топик,
а не через отсутствующий в этих сборках Python-модуль `find_object_2d.srv`.

## Важные условия

- `/depthnet/depth` должен быть `sensor_msgs/Image`; поддерживаются обычные `32FC1` и `16UC1` данные через `cv_bridge`. Для миллиметров установите `depth_scale: 0.001` в `config/default.yaml`.
- RGB и depth должны смотреть в одном направлении и быть геометрически совмещены. Узел масштабирует пиксельные координаты при разном разрешении, но это **не заменяет регистрацию** камер.
- Матрица `K` в `/video/camera_info` должна соответствовать RGB-изображению. При использовании intrinsics depth-камеры сначала зарегистрируйте depth к RGB либо публикуйте подходящий `CameraInfo`.
- Монокулярная DepthNet может выдавать относительную, а не метрическую глубину. В таком случае откалибруйте `depth_scale`; TF будет метрическим только при метрических входных значениях.
- Для защиты от несинхронных кадров параметр `max_depth_age` ограничивает допустимую разницу временных меток. Убедитесь, что все узлы используют одинаковое время (и `/use_sim_time`, если применимо).
- Web-сервер не выполняет аутентификацию. Не публикуйте порт `8080` в недоверенную сеть.

## Параметры

Основные параметры находятся в [`config/default.yaml`](config/default.yaml): масштаб и диапазон глубины, радиус медианного окна, максимальная разница времени и префикс TF. Узел намеренно не использует `/depthnet/colormap`: цветовая карта предназначена для визуализации, а координаты вычисляются из числового `/depthnet/depth`.
