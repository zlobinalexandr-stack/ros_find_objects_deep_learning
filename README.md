# find_object_3d_web

ROS Melodic-пакет вычисляет трёхмерное положение результатов
[`find_object_2d`](https://wiki.ros.org/find_object_2d) по карте глубины. Взаимодействие
с системой выполняется только через ROS-топики: эталоны объектов передаются в
`/find_object_2d/add_object`, а список обнаружений приходит из `/objectsStamped`.
HTTP-сервер, web-интерфейс и rosbridge пакет не запускает.

Для каждого результата `ObjectsStamped` центр шаблона проецируется гомографией в
RGB-изображение, глубина берётся как медиана небольшого окна, а координаты
вычисляются по матрице `K` из `CameraInfo`.

## Топики

Узел подписывается на:

| Назначение | Тип | Топик по умолчанию |
|---|---|---|
| RGB (для размеров кадра) | `sensor_msgs/Image` | `/video/image_raw` |
| глубина | `sensor_msgs/Image` | `/depthnet/depth` |
| калибровка | `sensor_msgs/CameraInfo` | `/video/camera_info` |
| список детекций | `find_object_2d/ObjectsStamped` | `/objectsStamped` |
| запросы добавления объектов (только логирование) | `sensor_msgs/CompressedImage` | `/find_object_2d/add_object` |

Эталон объекта следует публиковать непосредственно для `find_object_2d`:

| Назначение | Тип | Топик |
|---|---|---|
| новый эталон | `sensor_msgs/CompressedImage` | `/find_object_2d/add_object` |

JPEG-изображение эталона передаётся в поле `data`. Чтобы запросить конкретный ID,
укажите его десятичной строкой в `header.frame_id`; пустой `frame_id` позволяет
`find_object_2d` выбрать следующий ID. Данный пакет не дублирует и не проксирует
этот топик. Узел подписывается на него только для диагностики: при каждом запросе
в INFO-лог выводятся запрошенный ID (или `<automatic>`), формат и размер
изображения, а также имя публикующего узла. Этот лог подтверждает доставку
сообщения диагностическому узлу, но сам по себе **не подтверждает**, что
`find_object_2d` успешно создал эталон: протокол топика не предусматривает ответа.

Если в `header.frame_id` указан десятичный ID, узел запоминает запрос. Первое
обнаружение того же ID в `/objectsStamped` создаёт отдельный INFO-лог
`Template processing confirmed by first detection`. Он является сквозным
подтверждением того, что эталон участвует в детекции. При автоматическом ID
сопоставить запрос и обнаружение невозможно, поэтому для отладки рекомендуется
всегда задавать ID явно. До первого обнаружения `/objectsStamped` может оставаться
пустым: этот топик содержит результаты детекции, а не список загруженных эталонов.

Проверить, что непосредственно `find_object_2d` подключён к топику загрузки,
можно командой:

```bash
rostopic info /find_object_2d/add_object
```

В разделе `Subscribers` должен присутствовать узел `find_object_2d`. Полные поля
заголовка доступны при включённом уровне DEBUG, например:

```bash
rosconsole set /find_object_3d_web ros.find_object_3d_web debug
```

Пустое изображение дополнительно отмечается предупреждением.

Список обнаруженных объектов доступен только как ROS-сообщение:

```bash
rostopic echo /objectsStamped
```

## Результат

Для каждого корректного обнаружения узел публикует динамический TF:

```text
<frame_id сообщения /video/camera_info> -> object_<id>
```

Положение относительно `base_link` можно получить стандартным TF-запросом, если
frame камеры уже связан с деревом робота:

```bash
rosrun tf tf_echo base_link object_1
```

Ориентация TF единичная: из одной глубины определяется положение, но не
ориентация объекта.

## Установка (Melodic / Ubuntu 18.04)

```bash
sudo apt install ros-melodic-find-object-2d ros-melodic-cv-bridge python-numpy
cd ~/catkin_ws/src
git clone <URL-этого-репозитория> find_object_3d_web
cd ..
catkin_make
source devel/setup.bash
```

## Запуск

1. Запустите камеру и `ros_deep_learning` DepthNet.
2. Запустите `find_object_2d` на **том же RGB-изображении**, которое передано
   этому пакету:

   ```bash
   rosrun find_object_2d find_object_2d image:=/video/image_raw
   ```

3. Запустите узел локализации:

   ```bash
   roslaunch find_object_3d_web find_object_3d_web.launch
   ```

4. Передайте JPEG-эталон сообщением `sensor_msgs/CompressedImage` в
   `/find_object_2d/add_object` из собственного ROS-узла и читайте результаты из
   `/objectsStamped`.

5. Проверьте трёхмерный результат:

   ```bash
   rostopic echo /objectsStamped
   rosrun tf tf_echo <camera_info_frame> object_0
   ```

Имена входных топиков узла локализации можно изменить аргументами:

```bash
roslaunch find_object_3d_web find_object_3d_web.launch \
  image_topic:=/video/image_raw depth_topic:=/depthnet/depth \
  camera_info_topic:=/video/camera_info objects_topic:=/objectsStamped \
  add_object_topic:=/find_object_2d/add_object
```

После обновления пакета пересоберите workspace и повторно загрузите окружение:

```bash
catkin_make && source devel/setup.bash
```

## Важные условия

- `/depthnet/depth` должен быть `sensor_msgs/Image`; поддерживаются обычные
  `32FC1` и `16UC1` данные через `cv_bridge`. Для миллиметров установите
  `depth_scale: 0.001` в `config/default.yaml`.
- RGB и depth должны смотреть в одном направлении и быть геометрически
  совмещены. Узел масштабирует пиксельные координаты при разном разрешении, но
  это **не заменяет регистрацию** камер.
- Матрица `K` в `/video/camera_info` должна соответствовать RGB-изображению. При
  использовании intrinsics depth-камеры сначала зарегистрируйте depth к RGB либо
  публикуйте подходящий `CameraInfo`.
- Монокулярная DepthNet может выдавать относительную, а не метрическую глубину. В
  таком случае откалибруйте `depth_scale`; TF будет метрическим только при
  метрических входных значениях.
- Параметр `max_depth_age` ограничивает допустимую разницу временных меток.
  Убедитесь, что все узлы используют одинаковое время (и `/use_sim_time`, если
  применимо).

## Параметры

Основные параметры находятся в [`config/default.yaml`](config/default.yaml):
масштаб и диапазон глубины, радиус медианного окна, максимальная разница времени
и префикс TF. Узел намеренно не использует `/depthnet/colormap`: цветовая карта
предназначена для визуализации, а координаты вычисляются из числового
`/depthnet/depth`.
