const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=path.join(__dirname,'../services/kids/web');
function gameContext(game){
  const nodes={};
  const pen=new Proxy({}, {get:()=>()=>{},set:()=>true});
  const sandbox={URLSearchParams,location:{search:'?game='+game},requestAnimationFrame:()=>{},
    addEventListener:()=>{},document:{querySelector:selector=>nodes[selector]??=(selector==='#board'?{getContext:()=>pen,focus:()=>{}}:{})}};
  vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(source,'games.js'),'utf8'),sandbox);
  return sandbox;
}
test('Snake wraps around the garden instead of losing at the wall',()=>{
  const s=gameContext('snake');
  assert.equal(vm.runInContext('reset(); body=[{x:29,y:10},{x:28,y:10}]; apple={x:5,y:5}; step(); body[0].x',s),0);
});
test('Snake stops on self collision and can restart',()=>{
  const s=gameContext('snake');
  assert.equal(vm.runInContext('reset(); body=[{x:8,y:10},{x:9,y:10},{x:9,y:11},{x:8,y:11}]; step(); active',s),false);
  assert.equal(vm.runInContext('reset(); active && !paused',s),true);
});
test('Breakout offers another launch after a missed ball',()=>{
  const s=gameContext('breakout');
  assert.equal(vm.runInContext('reset(); launched=true; ball.y=500; step(); active && !launched',s),true);
});
test('Drawing exports a named PNG using the canvas data',()=>{
  let saved;
  const pen={fillRect:()=>{}};
  const nodes={'#paper':{width:1000,height:600,getContext:()=>pen,toDataURL:()=> 'data:image/png;base64,test'},'#clear':{},'#save':{}};
  const s={document:{querySelector:x=>nodes[x],createElement:()=>{const a={click:()=>{saved=a;}};return a;}}};
  vm.createContext(s);vm.runInContext(fs.readFileSync(path.join(source,'draw.js'),'utf8'),s);
  nodes['#save'].onclick();
  assert.equal(saved.download,'my-masterpiece.png');assert.equal(saved.href,'data:image/png;base64,test');
});
