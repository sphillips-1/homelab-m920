'use strict';
const paper=document.querySelector('#paper'),pen=paper.getContext('2d');let drawing=false;
function clear(){pen.fillStyle='white';pen.fillRect(0,0,paper.width,paper.height);}clear();
function point(e){const r=paper.getBoundingClientRect();return[(e.clientX-r.left)*paper.width/r.width,(e.clientY-r.top)*paper.height/r.height];}
paper.onpointerdown=e=>{drawing=true;paper.setPointerCapture(e.pointerId);pen.beginPath();pen.moveTo(...point(e));};paper.onpointermove=e=>{if(!drawing)return;pen.strokeStyle=document.querySelector('#color').value;pen.lineWidth=Number(document.querySelector('#size').value);pen.lineCap='round';pen.lineJoin='round';pen.lineTo(...point(e));pen.stroke();};paper.onpointerup=paper.onpointercancel=()=>drawing=false;
document.querySelector('#clear').onclick=()=>{if(confirm('Start a new picture? Save this one first if you want to keep it.'))clear();};document.querySelector('#save').onclick=()=>{const a=document.createElement('a');a.download='my-masterpiece.png';a.href=paper.toDataURL();a.click();};
