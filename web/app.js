(() => {
  const image = document.querySelector('#camera');
  const canvas = document.querySelector('#overlay');
  const ctx = canvas.getContext('2d');
  const add = document.querySelector('#add');
  const status = document.querySelector('#status');
  let start = null;
  let box = null;
  let dragging = false;
  let frameReceived = false;

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.className = isError ? 'error' : '';
  }

  function resizeOverlay() {
    canvas.width = image.clientWidth;
    canvas.height = image.clientHeight;
    box = null;
    add.disabled = true;
  }

  function rosbridgeUrl() {
    const configured = new URLSearchParams(window.location.search).get('rosbridge');
    if (configured) return configured;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.hostname}:9090`;
  }

  if (typeof ROSLIB === 'undefined') {
    setStatus('Не удалось загрузить roslibjs', true);
    return;
  }

  const ros = new ROSLIB.Ros({url: rosbridgeUrl()});
  const cameraTopic = new ROSLIB.Topic({
    ros,
    name: '/video/image_compressed/compressed',
    messageType: 'sensor_msgs/CompressedImage',
    queue_size: 1,
    throttle_rate: 100
  });

  ros.on('connection', () => setStatus('ROS подключён. Ожидание изображения…'));
  ros.on('error', () => setStatus('Ошибка подключения к rosbridge', true));
  ros.on('close', () => {
    frameReceived = false;
    add.disabled = true;
    setStatus('Соединение с rosbridge закрыто', true);
  });

  cameraTopic.subscribe(message => {
    if (typeof message.data !== 'string') {
      setStatus('Неверный формат sensor_msgs/CompressedImage', true);
      return;
    }
    const format = (message.format || '').toLowerCase();
    const mime = format.includes('png') ? 'image/png' : 'image/jpeg';
    image.src = `data:${mime};base64,${message.data}`;
  });

  image.onload = () => {
    if (!frameReceived || canvas.width !== image.clientWidth || canvas.height !== image.clientHeight) {
      resizeOverlay();
    }
    frameReceived = true;
    if (!dragging && !box) setStatus('Обведите объект мышью');
  };
  image.onerror = () => setStatus('Не удалось декодировать изображение камеры', true);
  window.addEventListener('resize', resizeOverlay);

  function point(event) {
    const bounds = canvas.getBoundingClientRect();
    return {x: event.clientX - bounds.left, y: event.clientY - bounds.top};
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!box) return;
    ctx.strokeStyle = '#22c55e';
    ctx.lineWidth = 3;
    ctx.fillStyle = '#22c55e22';
    ctx.fillRect(box.x, box.y, box.w, box.h);
    ctx.strokeRect(box.x, box.y, box.w, box.h);
  }

  canvas.addEventListener('pointerdown', event => {
    if (!frameReceived) return;
    start = point(event);
    dragging = true;
    box = null;
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointermove', event => {
    if (!dragging) return;
    const current = point(event);
    box = {
      x: Math.min(start.x, current.x),
      y: Math.min(start.y, current.y),
      w: Math.abs(current.x - start.x),
      h: Math.abs(current.y - start.y)
    };
    draw();
  });
  canvas.addEventListener('pointerup', () => {
    dragging = false;
    add.disabled = !box || box.w < 8 || box.h < 8;
  });

  add.addEventListener('click', async () => {
    add.disabled = true;
    setStatus('Добавление шаблона…');
    const payload = {
      x0: box.x / canvas.width,
      y0: box.y / canvas.height,
      x1: (box.x + box.w) / canvas.width,
      y1: (box.y + box.h) / canvas.height,
      id: Number(document.querySelector('#object-id').value)
    };
    try {
      const response = await fetch('/selection', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error);
      setStatus(`Объект ${result.id} добавлен`);
      box = null;
      draw();
    } catch (error) {
      setStatus(error.message, true);
      add.disabled = false;
    }
  });
})();
