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
test('Maker encyclopedia has connected, usable learning topics and quizzes',()=>{
  const articles=JSON.parse(fs.readFileSync(path.join(source,'maker-data.json'),'utf8'));
  const ids=new Set(articles.map(a=>a.id));
  assert.equal(ids.size,articles.length,'Topic IDs must be unique');
  for(const id of ['3d-printing','arduino','raspberry-pi','pico','esp32','circuits','sensors','motors','networks'])assert.ok(ids.has(id),id);
  for(const article of articles){
    assert.ok(article.simple.length>40,article.id+' needs an introduction');
    assert.ok(article.more.length>=2,article.id+' needs deeper reading');
    assert.ok(article.mission.length>30,article.id+' needs an activity');
    assert.ok(article.quiz.answer>=0&&article.quiz.answer<article.quiz.options.length,article.id+' quiz answer');
    for(const id of article.related){assert.ok(ids.has(id),article.id+' has broken related topic '+id);assert.notEqual(id,article.id);}
    for(const reference of article.sources)assert.equal(new URL(reference.url).protocol,'https:');
  }
});
test('Maker reader requires only local scripts, styles, and content',()=>{
  const html=fs.readFileSync(path.join(source,'makers.html'),'utf8');
  for(const match of html.matchAll(/(?:src|href)="([^"]+)"/g)){
    assert.ok(!/^(https?:)?\/\//.test(match[1]),'External runtime asset: '+match[1]);
    if(!match[1].startsWith('/'))assert.ok(fs.existsSync(path.join(source,match[1])),match[1]);
  }
  const script=fs.readFileSync(path.join(source,'makers.js'),'utf8');
  assert.match(script,/fetch\('maker-data.json'\)/);
  assert.doesNotMatch(script,/innerHTML|eval\(/,'Render encyclopedia text as text, not executable HTML');
});
