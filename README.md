# find_object_3d_web

ROS Melodic-пакет вычисляет трёхмерное положение результатов
[`find_object_2d`](https://wiki.ros.org/find_object_2d) по карте глубины. Взаимодействие
с системой выполняется только через ROS-топики: эталоны объектов передаются в
`/find_object_2d/add_object`, а список обнаружений приходит из `/objectsStamped`.
HTTP-сервер, web-интерфейс и rosbridge пакет не запускает.

Для каждого результата `ObjectsStamped` центр шаблона проецируется гомографией в
RGB-изображение, глубина берётся как медиана небольшого окна, а координаты
вычисляются по матрице `K` из `CameraInfo`.

## Интерфейс ROS-ноды

`find_object_3d_web` не имеет HTTP-интерфейса, сервисов и actions. Он принимает
пять ROS-топиков и публикует результат в стандартный TF-топик `/tf`.

| Направление | Назначение | Тип | Имя по умолчанию |
|---|---|---|---|
| вход | RGB-кадр (используются размеры) | `sensor_msgs/Image` | `/video/image_raw` |
| вход | карта глубины | `sensor_msgs/Image` | `/depthnet/depth` |
| вход | параметры камеры | `sensor_msgs/CameraInfo` | `/video/camera_info` |
| вход | двумерные обнаружения | `find_object_2d/ObjectsStamped` | `/objectsStamped` |
| вход, мониторинг | загрузка эталона | `sensor_msgs/CompressedImage` | `/find_object_2d/add_object` |
| выход | положение обнаруженного объекта | `tf2_msgs/TFMessage` | `/tf` |

Топик `/find_object_2d/add_object` принадлежит `find_object_2d`: данная нода
подписана на него параллельно только для логирования и не пересылает сообщение.
Все имена входов можно переопределить аргументами launch-файла. `/tf`
переназначать обычно не требуется.

### Общие команды для просмотра

```bash
# Тип сообщения, список publishers/subscribers и число подключений
rostopic type /objectsStamped
rostopic info /objectsStamped

# Полное описание полей сообщения
rosmsg show find_object_2d/ObjectsStamped
rosmsg show sensor_msgs/Image

# Текущие сообщения и частота их поступления
rostopic echo /objectsStamped
rostopic hz /objectsStamped
```

Пустой вывод `rostopic echo /objectsStamped` означает, что сейчас нет
распознанного объекта. Это не перечень загруженных эталонов и не подтверждение
их регистрации.

### `/video/image_raw` — RGB-изображение

Тип: `sensor_msgs/Image`.

| Поле | Ожидаемое содержимое |
|---|---|
| `header.stamp` | время получения кадра; этой нодой напрямую не используется |
| `header.frame_id` | оптическая система координат RGB-камеры |
| `height`, `width` | размеры RGB-кадра; именно эти поля использует нода |
| `encoding` | обычно `bgr8` или `rgb8` |
| `is_bigendian`, `step`, `data` | стандартное представление строк и пикселей ROS Image |

Пиксели RGB этой нодой не декодируются: размеры нужны, чтобы пересчитать
координаты обнаружения, если разрешение depth отличается. Сам `find_object_2d`
должен получать тот же RGB-поток.

```bash
rostopic info /video/image_raw
rostopic echo -n 1 /video/image_raw/header
```

### `/depthnet/depth` — карта глубины

Тип: `sensor_msgs/Image`. `height` и `width` задают размер карты, а `data`
содержит по одному значению глубины на пиксель.

| Поле | Ожидаемое содержимое |
|---|---|
| `header.stamp` | время depth-кадра; сравнивается с временем `/objectsStamped` |
| `header.frame_id` | оптический frame depth-камеры; используется как резервный TF parent |
| `encoding` | `32FC1` (обычно метры) либо `16UC1` (часто миллиметры) |
| `height`, `width`, `step`, `data` | стандартная матрица `sensor_msgs/Image` |

После `cv_bridge` каждое значение умножается на `depth_scale`. Для `16UC1` в
миллиметрах задайте `depth_scale: 0.001`. Допускаются только конечные значения в
диапазоне `[min_depth, max_depth]`; в окне вокруг центра объекта берётся медиана.

```bash
rostopic echo -n 1 /depthnet/depth/header
rostopic hz /depthnet/depth
```

### `/video/camera_info` — калибровка камеры

Тип: `sensor_msgs/CameraInfo`.

| Поле | Использование |
|---|---|
| `header.frame_id` | основной parent frame публикуемого TF |
| `width`, `height` | должны соответствовать RGB-камере |
| `K[0]`, `K[4]` | фокусные расстояния `fx`, `fy` |
| `K[2]`, `K[5]` | координаты главной точки `cx`, `cy` |
| `D`, `R`, `P`, `distortion_model` | этой нодой не используются; входные пиксели считаются rectified |

Преобразование пикселя `(u, v)` с глубиной `z` выполняется как
`x=(u-cx)*z/fx`, `y=(v-cy)*z/fy`. Нулевые или нечисловые `fx`/`fy` считаются
ошибкой.

```bash
rostopic echo -n 1 /video/camera_info
```

### `/find_object_2d/add_object` — загрузка эталона

Тип: `sensor_msgs/CompressedImage`.

| Поле | Что передавать |
|---|---|
| `header.stamp` | время отправки; рекомендуется текущее ROS-время |
| `header.frame_id` | десятичный ID, например строка `"7"`; пустая строка запрашивает автоматический ID |
| `format` | строка `"jpeg"` (или формат, поддерживаемый `find_object_2d`) |
| `data` | байты целого сжатого изображения, а не base64 и не путь к файлу |

Пример публикации JPEG из Python:

```python
#!/usr/bin/env python
import rospy
from sensor_msgs.msg import CompressedImage

rospy.init_node('add_find_object_template')
publisher = rospy.Publisher(
    '/find_object_2d/add_object', CompressedImage, queue_size=1)
rospy.sleep(0.5)  # дать subscribers время подключиться

message = CompressedImage()
message.header.stamp = rospy.Time.now()
message.header.frame_id = '7'  # явный ID упрощает диагностику
message.format = 'jpeg'
with open('/path/to/template.jpg', 'rb') as image_file:
    message.data = image_file.read()
publisher.publish(message)
rospy.sleep(1.0)
```

До публикации проверьте подключения:

```bash
rostopic info /find_object_2d/add_object
```

В `Subscribers` должны присутствовать и `find_object_2d`, и
`find_object_3d_web`. Лог `Object template upload observed` подтверждает только
доставку диагностическому узлу: протокол этого топика не содержит ответа от
`find_object_2d`. Пустой `data` отмечается предупреждением.

Для явного ID нода запоминает запрос. Первое обнаружение того же ID в
`/objectsStamped` создаёт лог `Template processing confirmed by first detection`
— это сквозное подтверждение участия эталона в детекции. Автоматический ID
сопоставить с запросом невозможно. Подробный лог входного сообщения включается
командой:

```bash
rosconsole set /find_object_3d_web ros.find_object_3d_web debug
```

### `/objectsStamped` — двумерные обнаружения

Тип `find_object_2d/ObjectsStamped` имеет следующую логическую структуру:

```text
std_msgs/Header header
std_msgs/Float32MultiArray objects
```

`header.stamp` — время RGB-кадра, на котором выполнена детекция;
`header.frame_id` — frame исходного изображения. Нода сравнивает
`header.stamp` с меткой depth-кадра и отклоняет результат, если разница больше
`max_depth_age`.

`objects.data` — плоский массив. Каждое обнаружение занимает ровно 12 чисел:

```text
[id, width, height,
 h11, h12, h13,
 h21, h22, h23,
 h31, h32, h33]
```

где `id` — ID эталона, `width`/`height` — его исходные размеры в пикселях, а
`h11..h33` — построчно записанная матрица гомографии 3×3, переводящая координаты
эталона в RGB-кадр. Несколько обнаружений объединяются подряд, поэтому длина
`objects.data` должна быть кратна 12. Поле `objects.layout` нодой не используется.

Пример одного обнаружения ID 7 для эталона 20×10 с переносом на `(100, 50)`:

```yaml
header:
  stamp: {secs: 0, nsecs: 0}
  frame_id: "camera_rgb_optical_frame"
objects:
  layout: {dim: [], data_offset: 0}
  data: [7, 20, 10, 1, 0, 100, 0, 1, 50, 0, 0, 1]
```

Обычно этот топик публикует `find_object_2d`; вручную отправлять его следует
только при тестировании.

## Результат

### `/tf` — трёхмерное положение

Для каждого корректного обнаружения узел через `tf2_ros` публикует динамический
`geometry_msgs/TransformStamped` внутри стандартного сообщения
`tf2_msgs/TFMessage`:

```text
<frame_id сообщения /video/camera_info> -> object_<id>
```

| Поле transform | Значение |
|---|---|
| `header.stamp` | метка depth-кадра либо текущее время, если метка отсутствует |
| `header.frame_id` | `CameraInfo.header.frame_id`, иначе `depth.header.frame_id` |
| `child_frame_id` | `object_frame_prefix` + ID, по умолчанию `object_7` |
| `transform.translation.{x,y,z}` | положение в системе камеры; единицы совпадают с масштабированной depth-картой |
| `transform.rotation.{x,y,z,w}` | `(0, 0, 0, 1)`, то есть единичный quaternion |

Посмотреть сырые TF-сообщения можно командой `rostopic echo /tf`, но удобнее
обращаться к конкретному frame через TF API:

Положение относительно `base_link` можно получить стандартным TF-запросом, если
frame камеры уже связан с деревом робота:

```bash
rosrun tf tf_echo base_link object_1
```

Ориентация TF единичная: из одной глубины определяется положение, но не
ориентация объекта. Если ID присутствует в `/objectsStamped`, но TF не появился,
смотрите WARN-логи ноды: наиболее частые причины — отсутствие RGB/depth/
`CameraInfo`, устаревшая depth-метка или невалидная глубина около центра объекта.

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
2. Запустите launch-файл. Он запустит `find_object_2d` на **том же
   RGB-изображении**, которое передано узлу локализации, а затем запустит
   `find_object_3d_web`:

   ```bash
   roslaunch find_object_3d_web find_object_3d_web.launch
   ```

3. Передайте JPEG-эталон сообщением `sensor_msgs/CompressedImage` в
   `/find_object_2d/add_object` из собственного ROS-узла и читайте результаты из
   `/objectsStamped`.

4. Проверьте трёхмерный результат:

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
