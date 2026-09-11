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
ROS-топики, публикует реестр шаблонов и выдаёт результат в стандартный TF-топик
`/tf`.

| Направление | Назначение | Тип | Имя по умолчанию |
|---|---|---|---|
| вход | RGB-кадр (используются размеры) | `sensor_msgs/Image` | `/video/image_raw` |
| вход | карта глубины | `sensor_msgs/Image` | `/depthnet/depth` |
| вход | параметры камеры | `sensor_msgs/CameraInfo` | `/video/camera_info` |
| вход | двумерные обнаружения | `find_object_2d/ObjectsStamped` | `/objectsStamped` |
| вход | загрузка и сохранение эталона | `sensor_msgs/CompressedImage` | `/find_object_2d/add_object` |
| вход | удаление сохранённого эталона | `std_msgs/Int32` | `/find_object_3d_web/remove_object` |
| выход, latched | список сохранённых ID | `std_msgs/Int32MultiArray` | `/find_object_3d_web/objects` |
| выход | положение обнаруженного объекта | `tf2_msgs/TFMessage` | `/tf` |

Нода сохраняет каждый принятый эталон на диске и назначает ID для запросов с
пустым `header.frame_id` или значением `"0"`. Менеджер создаёт совместимый каталог изображений и
перезапускает детектор с поддерживаемым параметром `objects_path` после
добавления или удаления объекта. Все
имена входов можно переопределить аргументами launch-файла. `/tf` переназначать
обычно не требуется.

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

После `cv_bridge` каждое значение сначала умножается на `depth_scale`. Для `16UC1` в
миллиметрах задайте `depth_scale: 0.001`. Затем применяется метрическая
калибровка `z = z_raw * depth_calibration_scale + depth_calibration_offset`.
Допускаются только конечные скалиброванные значения в диапазоне `[min_depth, max_depth]`;
в окне вокруг центра объекта берётся медиана.

```bash
rostopic echo -n 1 /depthnet/depth/header
rostopic hz /depthnet/depth
```

#### Калибровка расстояния

`depth_scale` используйте только для перевода единиц (например, мм в м). Для калибровки
монокулярной DepthNet или систематической ошибки RGB-D используйте два новых
параметра:

1. Разместите объект по оптической оси камеры на двух точно измеренных расстояниях
   `D1` и `D2` (например, 1 и 3 м **от камеры**, а не от `base_link`).
2. Для каждой точки запишите несколько значений `position.z` из лога и возьмите их медианы
   `R1` и `R2`.
3. Вычислите `scale = (D2-D1)/(R2-R1)` и `offset = D1-scale*R1`.
4. Запишите их в YAML и перезапустите ноду:

   ```yaml
   depth_scale: 1.0
   depth_calibration_scale: 1.25
   depth_calibration_offset: -0.08
   ```

Если ошибка чисто масштабная (например, реальные 2.5 м вместо выдаваемых 2.0 м), можно
использовать `depth_calibration_scale: 1.25` и нулевое смещение. Если ошибка сильно
меняется с дистанцией, аффинная поправка недостаточна: нужна метрическая depth-модель или
аппаратная RGB-D/стереокамера.

Параметры можно передать без редактирования `default.yaml`. Например, если измеренное
расстояние 3.0 м, а нода выдаёт 0.5 м, одноточечная масштабная оценка равна
`3.0/0.5 = 6.0`:

```bash
roslaunch find_object_3d_web find_object_3d_web.launch \
  depth_calibration_scale:=6.0 depth_calibration_offset:=0.0
```

Это предварительная оценка по одной точке. После неё нужно проверить ещё хотя бы одну
дистанцию. Для точной оценки `scale` и `offset` используйте описанные выше две точки.

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
Поэтому пиксель и поза камеры задают только **луч** на объект. Метрические `x`, `y`
и `z` все зависят от глубины; по одному RGB-кадру нельзя получить точную позицию без
дополнительного ограничения (глубины, известной плоскости пола или известного размера объекта).

```bash
rostopic echo -n 1 /video/camera_info
```

#### TF оптического frame камеры

По REP-103 оси `camera_link` обычно направлены `x` вперёд, `y` влево, `z` вверх, а оси
`camera_link_optical` — `z` вперёд, `x` вправо, `y` вниз. Стандартное fixed-преобразование:

```xml
<joint name="camera_optical_joint" type="fixed">
  <parent link="camera_link"/>
  <child link="camera_link_optical"/>
  <origin xyz="0 0 0" rpy="${-pi/2} 0 ${-pi/2}"/>
</joint>
```

Знак последнего угла важен: `rpy="${-pi/2} 0 ${pi/2}"` направляет положительную ось `z`
оптического frame назад вдоль `-x` frame `camera_link`. Точка с положительной глубиной тогда попадает
за робота. Проверка после изменения URDF:

```bash
rosrun tf tf_echo camera_link camera_link_optical
rosrun tf tf_echo base_link object_1
```

Физический наклон `camera_link` должен быть вокруг оси `y` (pitch), а не вокруг `x` (roll).
При стандартных осях `camera_link` (`x` вперёд, `z` вверх) **наклон камеры вверх** на `0.17` рад
задаётся как `rpy="0 -0.17 0"`, а вниз — как `rpy="0 0.17 0"`. Знак нужно окончательно сверить
с видом осей в RViz: красная `x`-ось `camera_link` должна идти вверх по фактической оси камеры.

После исправления URDF не нужно откатывать разбор гомографии или метрическую калибровку:
это независимые этапы. URDF задаёт направление и позу камеры, гомография — пиксель объекта,
а depth-калировка — расстояние вдоль луча. Возвращать коэффициенты к `1.0` и `0.0` следует только
если повторные измерения показали, что depth-топик уже выдаёт метрическую глубину без систематической
ошибки.

### `/find_object_2d/add_object` — загрузка эталона

Тип: `sensor_msgs/CompressedImage`.

| Поле | Что передавать |
|---|---|
| `header.stamp` | время отправки; рекомендуется текущее ROS-время |
| `header.frame_id` | положительный десятичный ID, например строка `"7"`; пустая строка или `"0"` запрашивает автоматический ID |
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

В `Subscribers` должен присутствовать `find_object_3d_web`: он сохраняет шаблон,
запрашивает обновление каталога объектов и перезапуск детектора. Пустой `data` отмечается
предупреждением и не сохраняется. У `find_object_2d 0.7.0` нет subscriber для
динамической загрузки `CompressedImage`, поэтому пакет не пытается пересылать
шаблон в несуществующий вход.

Для каждого сохранённого ID нода запоминает запрос. Первое обнаружение того же ID в
`/objectsStamped` создаёт лог `Template processing confirmed by first detection`
— это сквозное подтверждение участия эталона в детекции. При пустом
`header.frame_id` или значении `"0"` назначается наименьший свободный положительный ID.
ID `0` служит маркером автоматического назначения в `find_object_2d`; нумерация начинается
с `1`. При первом запуске обновлённого пакета старый сохранённый ID `0`
автоматически переносится на ближайший свободный положительный ID. Подробный лог
входного сообщения включается командой:

```bash
rosconsole set /find_object_3d_web ros.find_object_3d_web debug
```

### Список и удаление сохранённых эталонов

Полный отсортированный список ID публикуется latched-сообщением, поэтому новый
подписчик сразу получает актуальное состояние:

```bash
rostopic echo -n 1 /find_object_3d_web/objects
```

Тип топика — `std_msgs/Int32MultiArray`, например `data: [1, 2, 7]`. Чтобы
удалить ID `7` с диска и из работающего `find_object_2d`, опубликуйте:

```bash
rostopic pub -1 /find_object_3d_web/remove_object std_msgs/Int32 "data: 7"
```

После добавления или удаления список публикуется заново, каталог изображений для
`find_object_2d` обновляется, а детектор автоматически перезапускается. По
умолчанию исходные файлы хранятся в `~/.ros/find_object_3d_web/objects`, а
экспортированные JPEG/PNG — в `~/.ros/find_object_3d_web/detector_objects`.
Пути изменяются параметрами `storage_directory` и `detector_objects_path`.
Удаление отсутствующего или неположительного ID отклоняется.

Во время перезапуска завершение прежнего процесса `find_object_2d` с кодом `0`
является штатной частью обновления. Менеджер ожидает окончания перезапуска и не
завершает свою ноду, пока новый процесс детектора запускается.

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
 h11, h21, h31,
 h12, h22, h32,
 h13, h23, h33]
```

где `id` — ID эталона, `width`/`height` — его исходные размеры в пикселях, а
`h11..h33` — записанная **по столбцам** матрица гомографии 3×3, переводящая координаты
эталона в RGB-кадр. Это порядок полей `find_object_2d`, а не привычная построчная запись.
Несколько обнаружений объединяются подряд, поэтому длина
`objects.data` должна быть кратна 12. Поле `objects.layout` нодой не используется.

Пример одного обнаружения ID 7 для эталона 20×10 с переносом на `(100, 50)`:

```yaml
header:
  stamp: {secs: 0, nsecs: 0}
  frame_id: "camera_rgb_optical_frame"
objects:
  layout: {dim: [], data_offset: 0}
  data: [7, 20, 10, 1, 0, 0, 0, 1, 0, 100, 50, 1]
```

Обычно этот топик публикует `find_object_2d`; вручную отправлять его следует
только при тестировании.

### Как читать диагностический лог `find_object_2d`

Строки вида

```text
No objects detected. (47 ms)
500 descriptors extracted from object -1 (in 46 ms)
```

не являются ошибкой. `object -1` — служебный ID текущего кадра сцены, а не ID
загруженного эталона и не «объект с отрицательным номером». В данном примере
детектор нашёл в очередном RGB-кадре 500 ключевых признаков и вычислил их
дескрипторы за 46 мс. `No objects detected` означает, что на обработанном кадре
эти признаки не дали достаточно надёжного соответствия ни с одним загруженным
эталоном; полный цикл занял 47 мс. Соседние строки могут относиться к разным
кадрам, поэтому порядок этих двух сообщений не противоречив.

Если сообщение повторяется постоянно, проверьте, что эталон действительно
загружен (его ID присутствует в `/find_object_3d_web/objects`), RGB-кадр приходит
в `/video/image_raw`, а объект достаточно крупный, резкий и похож на эталон по
ракурсу и освещению. Пока соответствие не найдено, пустой `/objectsStamped` и
отсутствие TF `object_<id>` являются ожидаемым результатом.

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

Нельзя рисовать маркер на 2D-карте, просто используя `translation.x` и `translation.y` из этого
сообщения. Эти поля заданы в `header.frame_id`, обычно в `camera_link_optical`, где `x` направлен
вправо, `y` вниз, а **расстояние вперёд хранится в `z`**. Например, для оптических координ
`[0.300, 0.542, 4.297]` ошибочная 2D-отрисовка `(x, y)` покажет маркер всего в
`sqrt(0.300^2+0.542^2) = 0.62` м от начала, хотя объект находится примерно в 4.3 м впереди.

Перед отрисовкой клиент должен запросить TF `map -> object_<id>` на метке времени обнаружения и
использовать `x`, `y` **уже этого преобразования**. Для ручной проверки, пока детектор видит объект:

```bash
rosrun tf tf_echo map object_1
```
Вывод этой команды содержит **абсолютные** координаты объекта в `map`, а не расстояние от робота.
Чтобы сравнить TF с 2D-картой, одновременно получите `map -> base_link` и вычислите:

```text
dx = object_map_x - robot_map_x
dy = object_map_y - robot_map_y
planar_distance = sqrt(dx*dx + dy*dy)
```

Для одного снимка TF удобнее использовать `tf_echo base_link object_1`: его `x/y` сразу показывают
продольное и боковое смещение относительно робота.

Координата `map_z` не используется 2D-картой, но служит важной проверкой. Большое отрицательное
значение для объекта над полом обычно означает, что в URDF неверны высота или pitch камеры, либо depth
завышен вдоль направленного вниз луча. Проверьте фактическую высоту оптического центра и знак
наклона по осям TF в RViz.

Если web-клиент использует `ROSLIB.TFClient`, ему нужно задать `fixedFrame: 'map'`, подписаться на
`object_1` и отрисовывать возвращённые TFClient `translation.x/y`, а не сырые координаты из `/tf`.

Посмотреть сырые TF-сообщения можно командой `rostopic echo /tf`, но удобнее
обращаться к конкретному frame через TF API:

Положение относительно `base_link` можно получить стандартным TF-запросом, если
frame камеры уже связан с деревом робота:

```bash
rosrun tf tf_echo base_link object_1
```

`object_<id>` публикуется в динамическом `/tf` только при обработке очередного обнаружения.
Это не static TF и не latched-топик: новый процесс `tf_echo` не получит сообщение, отправленное до его
запуска. Если детектор больше не видит объект, `tf_echo` выведет `source_frame does not exist`, даже если связь
`base_link -> camera_link -> camera_link_optical` исправна. Для диагностики запустите `tf_echo`, затем покажите объект
камере и убедитесь, что в это же время появляются логи `Object detected`:

```bash
rostopic hz /objectsStamped
rostopic echo /tf | rg -A 12 object_1
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
   rosrun tf tf_echo <camera_info_frame> object_1
   ```

Имена входных топиков узла локализации можно изменить аргументами:

```bash
roslaunch find_object_3d_web find_object_3d_web.launch \
  image_topic:=/video/image_raw depth_topic:=/depthnet/depth \
  camera_info_topic:=/video/camera_info objects_topic:=/objectsStamped \
  add_object_topic:=/find_object_2d/add_object \
  remove_object_topic:=/find_object_3d_web/remove_object \
  object_list_topic:=/find_object_3d_web/objects
```

Пути внутреннего хранилища и экспортируемого каталога можно изменить отдельно:

```bash
roslaunch find_object_3d_web find_object_3d_web.launch \
  storage_directory:=/data/find_objects \
  detector_objects_path:=/data/find_object_2d_images
```

При старте `find_object_2d_session_manager` сначала экспортирует все `<id>.image`
из хранилища в обычные JPEG/PNG и только затем запускает `/find_object_2d` с
`objects_path`. Это исключает гонку, при которой детектор стартует раньше
восстановления эталонов. Бинарный `session.bin` намеренно не генерируется: пакет
`ros-melodic-find-object-2d` устанавливает библиотеку без публичных C++-заголовков,
а `objects_path` является штатным интерфейсом установленной ноды.

По умолчанию `find_object_2d` запускается без графического интерфейса
(`detector_gui:=false`). Это позволяет запускать пакет на роботе или через SSH без
X-сервера. Для локальной настройки детектора с окном Qt включите интерфейс явно:

```bash
roslaunch find_object_3d_web find_object_3d_web.launch detector_gui:=true
```

Если при запуске видны сообщения `Could not connect to display` или
`Could not connect to any X display`, значит GUI был включён, но процесс не имеет
доступа к X-серверу. Отключите его через `detector_gui:=false` либо настройте
рабочий X11 forwarding. Падение `find_object_2d` в этом случае не связано с
RGB/depth-топиками; однако без детектора `/objectsStamped` больше не получает
новые обнаружения, даже если `find_object_3d_web` продолжает работать.

После обновления пакета пересоберите workspace и повторно загрузите окружение:

```bash
catkin_make --force-cmake && source devel/setup.bash
```

Если CMake после обновления сообщает, что цель `find_object_session_generator`
не существует, используется старый исходный файл или кэш предыдущей сборки. В
актуальном `CMakeLists.txt` её установка защищена условием `if(TARGET ...)`,
поэтому правило для отсутствующей цели не создаётся. Проверьте commit и очистите
кэш пакета:

```bash
git -C ~/myrobot/src/ros_find_objects_deep_learning rev-parse --short HEAD
nl -ba ~/myrobot/src/ros_find_objects_deep_learning/CMakeLists.txt | sed -n '15,32p'
rm -rf ~/myrobot/build/ros_find_objects_deep_learning
cd ~/myrobot
catkin_make --force-cmake
source devel/setup.bash
```

Строка `install(TARGETS find_object_session_generator ...)` должна находиться
между `if(TARGET find_object_session_generator)` и `endif()`. Если она выполняется
без этого условия, обновление исходников применено не полностью. Если ошибка
сохраняется с правильным файлом, удалите общие каталоги `build` и `devel`
workspace и выполните полную сборку заново; это также пересоздаст
верхнеуровневый кэш catkin.

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
