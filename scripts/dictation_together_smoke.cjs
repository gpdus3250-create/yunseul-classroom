const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const html=fs.readFileSync(path.join(__dirname,'../dictation/index.html'),'utf8');
const code=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)][0]?.[1];
assert(code,'Inline dictation script must exist');
const start=code.indexOf('let togetherState='),end=code.indexOf('function render(){',start);
assert(start>=0&&end>start,'Shared 3-choice mode block must exist');
const readCalls=[];
const app={innerHTML:''};
const ctx={
  view:'together',number:3,selected:new Set([1]),levels:{1:['꽃이 활짝 피었습니다.','하늘이 맑다.','무릎을 꿇다.']},
  COLORS:['#e993af','#e7be69','#8eaddf'],audioConfig:{mode:'recorded',recordedVoice:'MELO'},
  allQuestions:()=>[...ctx.selected].flatMap(g=>ctx.levels[g].map((text,index)=>({grade:g,index,text,id:g+':'+index}))),
  shuffle(xs){return xs.slice()},
  makeOptions(text){return [text+' (틀림 1)',text,text+' (틀림 2)']},
  esc:x=>x, grades:()=>'', chosenKoVoice:()=>null,
  readText:(s,o)=>readCalls.push([s,o]), stopVoice:()=>{}, voiceStatus:()=>{},
  alert:s=>{throw Error(s)}, clearTimeout:()=>{},
  setTimeout:()=>1, setView:()=>{},
  $:()=>app,
  document:{body:{classList:{remove:()=>{}}},querySelectorAll:()=>[]},
};
vm.createContext(ctx);
vm.runInContext(code.slice(start,end)+`
this.api={
 state:()=>togetherState,
 setCount:togetherSetCount,start:togetherStart,ready:togetherReady,
 answer:togetherAnswer,advance:togetherAdvance,lane:togetherRenderLane,
 hear:togetherHear,exit:togetherExit
};`,ctx);
ctx.api.setCount(3);
ctx.api.start();
assert.equal(ctx.api.state().stage,'ready');
ctx.api.ready(0);ctx.api.ready(1);
assert.equal(readCalls.length,0,'Audio must wait until all students are ready');
ctx.api.ready(2);
let st=ctx.api.state();
assert.equal(st.stage,'play');
assert.equal(readCalls.length,1,'Shared sentence must be read exactly once when ready');
assert.equal(readCalls[0][0],st.question.text);
assert.equal(st.choices.length,3);
assert.equal(new Set(st.choices).size,3);
const expectedOptionTexts=Array.from({length:3},(_,i)=>ctx.api.lane(i).match(/<button class="tg-option[^>]*>[\s\S]*?<\/button>/g).map(x=>x.replace(/togetherAnswer\(\d+,/g,'togetherAnswer(student,')));
assert.deepEqual(expectedOptionTexts[0],expectedOptionTexts[1],'Every student must have identical visible options');
assert.deepEqual(expectedOptionTexts[1],expectedOptionTexts[2],'Every student must have identical visible options');
ctx.api.answer(0,1);
assert.equal(st.stage,'play','First answer must not reveal correct option');
assert(!ctx.api.lane(1).includes('is-correct'),'No answer key revealed before everyone submits');
ctx.api.answer(1,0);
ctx.api.answer(2,2);
assert.equal(st.stage,'reveal');
assert.equal(st.scores.join(','),'1,0,0','Independent answer grading must use shared sentence');
ctx.api.advance();
st=ctx.api.state();
assert.equal(st.stage,'play');
assert.equal(readCalls.length,2,'Next shared round should read one new sentence');
assert.equal(readCalls[1][0],st.question.text);
assert.notEqual(readCalls[0][0],readCalls[1][0],'No duplicate sentence on consecutive rounds');
ctx.api.hear();
assert.equal(readCalls.length,3,'Replay is available to everyone at once');
assert.equal(readCalls[2][0],st.question.text);
console.log('Shared 3-choice regression passed: same question and options, one common audio, independent answers, delayed reveal.');
