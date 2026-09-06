(() => {
  const image = document.querySelector('#camera');
  const canvas = document.querySelector('#overlay');
  const ctx = canvas.getContext('2d');
  const add = document.querySelector('#add');
  const status = document.querySelector('#status');
  let start = null, box = null, dragging = false;

  function refresh() { image.src = `/frame.jpg?t=${Date.now()}`; }
  image.onload = () => { canvas.width=image.clientWidth; canvas.height=image.clientHeight; if (!dragging) status.textContent='Обведите объект мышью'; setTimeout(refresh, 120); };
  image.onerror = () => setTimeout(refresh, 700);
  window.addEventListener('resize', () => { canvas.width=image.clientWidth; canvas.height=image.clientHeight; box=null; add.disabled=true; });
  function point(event) { const r=canvas.getBoundingClientRect(); return {x:event.clientX-r.left,y:event.clientY-r.top}; }
  function draw() { ctx.clearRect(0,0,canvas.width,canvas.height); if(box){ctx.strokeStyle='#22c55e';ctx.lineWidth=3;ctx.fillStyle='#22c55e22';ctx.fillRect(box.x,box.y,box.w,box.h);ctx.strokeRect(box.x,box.y,box.w,box.h);} }
  canvas.addEventListener('pointerdown', e => { start=point(e); dragging=true; box=null; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', e => { if(!dragging)return; const p=point(e);box={x:Math.min(start.x,p.x),y:Math.min(start.y,p.y),w:Math.abs(p.x-start.x),h:Math.abs(p.y-start.y)};draw(); });
  canvas.addEventListener('pointerup', () => { dragging=false;add.disabled=!box||box.w<8||box.h<8; });
  add.addEventListener('click', async () => {
    add.disabled=true; status.className=''; status.textContent='Добавление шаблона…';
    const payload={x0:box.x/canvas.width,y0:box.y/canvas.height,x1:(box.x+box.w)/canvas.width,y1:(box.y+box.h)/canvas.height,id:Number(document.querySelector('#object-id').value)};
    try { const response=await fetch('/selection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await response.json();if(!response.ok)throw new Error(result.error);status.textContent=`Объект ${result.id} добавлен`;box=null;draw(); }
    catch(error){status.className='error';status.textContent=error.message;add.disabled=false;}
  });
  refresh();
})();
