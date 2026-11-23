const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');

const html=fs.readFileSync('index.html','utf8');
const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)];
assert.equal(scripts.length,1,'Expected one inline application script');
new vm.Script(scripts[0][1],{filename:'site-inline-script.js'});
for(const term of [
  'lessonComprehensionPanel()',
  "case'lesson-launch'",
  "case'lesson-meaning-answer'",
  'lesson-recommendations.json'
]){
  assert.ok(html.includes(term),'Missing UI hook: '+term);
}
assert.ok(!html.includes('${lessonRecommendationsPanel(true)}'),'Unhelpful lesson panel must not render on homepage');
assert.ok(!html.includes('+lessonRecommendationsPanel(false)'),'Unhelpful lesson panel must not render on weekly page');
assert.ok(!html.includes('data-act="lesson-spark"'),'Idea picker button must stay removed');
assert.ok(html.includes('weeklyLoad().then(weeklyRefreshRemote);'),'PDF weekly notices must remain connected');
const data=JSON.parse(fs.readFileSync('weekly-data/lesson-recommendations.json','utf8'));
assert.equal(data.version,1);
assert.ok(data.weeks && typeof data.weeks==='object');
for(const [week,record] of Object.entries(data.weeks)){
  assert.match(week,/^\d{4}-\d\d-\d\d$/);
  for(const rec of record.recommendations||[]){
    assert.ok(rec.evidence.length,'Missing evidence for '+rec.id);
    assert.ok(Number.isInteger(rec.source_page),'Missing source page');
    for(const action of rec.actions){
      assert.ok(html.includes("'"+action.id+"'"),'Unknown action '+action.id);
    }
  }
}
const catalog=JSON.parse(fs.readFileSync('lesson-catalog.json','utf8'));
assert.equal(catalog.version,1);
assert.ok(catalog.activities.length>=10,'Integrated textbook ideas missing');
const textbookNames=new Set(catalog.activities.map(x=>x.book));
assert.ok(textbookNames.has('상상 1-2')&&textbookNames.has('이야기 1-2'),'Both integrated books required');
for(const item of catalog.activities){
  assert.ok(item.topic&&item.source_patterns.length>0,'Evidence rule missing: '+item.id);
  assert.ok(item.steps.length>=3&&item.materials.length>0&&item.sheet?.prompt,'Practical lesson details missing: '+item.id);
}
for(const name of ['lessonPrintSheet','lessonRecommendationsPanel',"case'lesson-filter'","case'lesson-print'"]){
  assert.ok(html.includes(name),'Integrated activity UI handler missing: '+name);
}
const current=data.weeks['2026-11-23'];
assert.ok(current&&current.status==='ok','Current weekly source not usable');
assert.ok(current.recommendations.some(x=>x.subject==='상상')&&current.recommendations.some(x=>x.subject==='이야기'),
  'Current weekly PDF must include both integrated textbook activity recommendations');
for(const item of current.recommendations.filter(x=>x.book)){
  assert.ok(item.evidence.length>0&&item.source_page===1,'Book suggestion lacks source evidence');
  assert.ok(item.sheet?.prompt&&item.steps?.length>0,'Book suggestion lacks ready-to-teach plans');
}


// The standalone playlab must work without a network, account or build framework.
const playHtml=fs.readFileSync('playlab.html','utf8');
const playScripts=[...playHtml.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)];
assert.equal(playScripts.length,1,'Playlab should have one inline game script');
new vm.Script(playScripts[0][1],{filename:'playlab-inline.js'});
const gameModes=['safety','builder','roulette','story','path','train'];
for(const mode of gameModes){
  assert.ok(playHtml.includes('data-mode="'+mode+'"'),'Missing game tab: '+mode);
  assert.ok(html.includes('playlab.html#'+mode),'Homepage game shortcut missing: '+mode);
}
assert.ok(html.includes('function lessonPlayMode'),'Weekly integrated cards must link to playable games');
assert.ok(!html.includes('🪄 수업 흐름과 교사용 팁 보기</summary>') || !html.includes('+guide+(sparkText?'),
  'Teacher plan text must not appear in recommendation cards');
// Run each game's initial render under a minimal browser-like environment.
const testStage={innerHTML:''};
const fakeTabs=gameModes.map(mode=>({dataset:{mode},classList:{toggle(){}}}));
const fakeLocation={hash:'#safety'};
const fakeDocument={
  getElementById(id){return id==='stage'?testStage:null;},
  querySelectorAll(query){return query==='.tab'?fakeTabs:[];},
  addEventListener(){},
};
const sandbox=vm.createContext({
  document:fakeDocument,window:{addEventListener(){}},location:fakeLocation,
  history:{replaceState(a,b,hash){fakeLocation.hash=hash;}},requestAnimationFrame(){},
  Math,Set,Array,console,devicePixelRatio:1
});
vm.runInContext(playScripts[0][1],sandbox,{timeout:3000});
for(const mode of gameModes){
  vm.runInContext('setMode("'+mode+'")',sandbox,{timeout:1000});
  assert.ok(testStage.innerHTML.length>250,'Game did not render: '+mode);
}
console.log('✓ Six immediate-play integrated games parse and render in minimal browser context');


// Automated tests for worksheet studio 2.0.
const appJs=scripts[0][1];
const worksheetStart=appJs.indexOf('function worksheetMathPairs(');
const worksheetEnd=appJs.indexOf('// 2. 읽기 왕국',worksheetStart);
assert.ok(worksheetStart>0&&worksheetEnd>worksheetStart,'Worksheet studio source missing');
const worksheetCode=appJs.slice(worksheetStart,worksheetEnd);
const wsObj={
 theme:'cute',kind:'math',n:11,difficulty:'normal',items:[],answers:false,
 mathRange:'20',operation:'mixed',carry:'any',wordRatio:0,
 purpose:'class',pageMode:'auto',previewPage:0,editIndex:null
};
wsObj.items=Array.from({length:11},(_,i)=>({text:(i+1)+' + 2 =',answer:String(i+3)}));
const fakeDb={settings:{grade:1,room:6,school:'우리 학교'}};
const htmlSafe=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const wsContext=vm.createContext({
 ui:{worksheet:wsObj},db:fakeDb,safe:htmlSafe,console,Math,Set,Array,
 rnd:(a,b)=>a+Math.floor(Math.random()*(b-a+1)),
 shuffle:a=>a.slice().reverse(),
 KOREAN_ITEMS:[['우리 집','우리집'],['맛있는 밥','맛있는밥']],
 WRITE_TOPICS:['나의 즐거운 하루','우리 반 친구'],
 toast:()=>{},render:()=>{},
 confirm:()=>true,requestAnimationFrame:()=>{},
 localStorage:{getItem(){return 'cute'},setItem(){}},
 heading:(a,b,c)=>'<h2>'+b+'</h2>',
 shell:(a,b)=>'<section><h3>'+a+'</h3>'+b+'</section>',
 blank:message=>message,
 hField:(label,body)=>'<label>'+label+body+'</label>',
 selectOptions:(items,chosen)=>items.map(([value,title])=>'<option '+(String(chosen)===String(value)?'selected':'')+'>'+title+'</option>').join(''),
 printHTML:(title,body)=>{wsContext.lastPrinted={title,body};return true}
});
vm.runInContext(worksheetCode,wsContext,{timeout:3000});
const cute=vm.runInContext('renderWorksheet()',wsContext,{timeout:1000});
assert.ok(cute.includes('ws-sheet ws-cute'),'Cute sheet preview missing');
assert.ok(cute.includes('ws-bunny'),'Cute bunny decoration missing');
assert.ok(cute.includes('data-id="cute"')&&cute.includes('data-id="simple"'),'Two theme choices missing');
assert.ok(cute.includes('worksheet-word-ratio'),'Word-problem ratio slider missing');
assert.ok(cute.includes('worksheet-range')&&cute.includes('worksheet-carry'),'Number range and regrouping controls missing');
assert.ok(cute.includes('worksheet-purpose')&&cute.includes('worksheet-page-mode'),'Page and use-case options missing');
assert.ok(cute.includes('data-act="worksheet-reroll"')&&cute.includes('data-act="worksheet-edit"'),'One-by-one editing missing');
wsObj.theme='simple';
const simple=vm.runInContext('renderWorksheet()',wsContext,{timeout:1000});
assert.ok(simple.includes('ws-sheet ws-simple'),'Simple sheet preview missing');
assert.ok(!simple.includes('<span class="ws-bunny">'),'Simple design should omit illustration');
vm.runInContext('printWorksheet()',wsContext,{timeout:1000});
assert.ok(wsContext.lastPrinted.body.includes('ws-sheet ws-simple'),'Printable simple design missing');
assert.equal((wsContext.lastPrinted.body.match(/ws-purpose-class ws-print"/g)||[]).length,2,
  'Auto mode must split 11 equations across two student pages');
assert.ok(wsContext.lastPrinted.body.includes('ws-answers'),'Printable answer key missing');
wsObj.theme='cute';wsObj.pageMode='one';wsObj.wordRatio=2;
wsObj.items=[
 {text:'16 + 4 =',answer:'20'},{text:'7 + 9 =',answer:'16'},
 {text:'18 - 6 =',answer:'12'},
 {text:'사과가 1개 있고, 3개를 더 받았어요. 모두 몇 개일까요?',answer:'4'},
 {text:'7 + 11 =',answer:'18'},{text:'18 - 5 =',answer:'13'},
 {text:'9 + 5 =',answer:'14'},
 {text:'사과가 12개 있고, 7개를 더 받았어요. 모두 몇 개일까요?',answer:'19'},
 {text:'11 + 3 =',answer:'14'},{text:'13 - 6 =',answer:'7'}
];
const modes=vm.runInContext('ui.worksheet.items.map(q=>worksheetQuestionMode(q,"math"))',wsContext,{timeout:1000});
assert.equal(modes.filter(x=>x==='word').length,2);
const mixedGroups=vm.runInContext('worksheetPaginate(ui.worksheet)',wsContext,{timeout:1000});
assert.equal(mixedGroups.length,1,'Ten mixed math problems should fit one sheet');
const mixed=vm.runInContext('renderWorksheet()',wsContext,{timeout:1000});
assert.ok(mixed.includes('ws-auto-mixed'),'Mixed 2-column/full-width layout missing');
assert.equal((mixed.match(/class="ws-q ws-q-word"/g)||[]).length,2);
assert.equal((mixed.match(/class="ws-q ws-q-equation"/g)||[]).length,8);
assert.ok(mixed.includes('ws-word-response'),'Word problems need both equation and answer fields');
vm.runInContext('printWorksheet()',wsContext,{timeout:1000});
assert.ok(wsContext.lastPrinted.body.includes('ws-q-word'),'Word problems should print full-width');
assert.ok(wsContext.lastPrinted.body.includes('grid-column:1/-1'),'Print stylesheet missing full-width rule');
const ratioOutput=vm.runInContext("makeQuestions('math',10,'normal',{mathRange:'20',operation:'mixed',carry:'none',wordRatio:3})",wsContext,{timeout:1000});
assert.equal(ratioOutput.length,10);
assert.equal(ratioOutput.filter(x=>x.mode==='word').length,3,'Exact word ratio was not respected');
for(const q of ratioOutput){
 assert.equal(Number(q.answer),q.meta.expected,'Generated answer must match arithmetic');
 assert.ok(q.meta.expected<=20,'Out-of-range result');
 assert.equal(q.meta.carry,undefined);
}
const allBefore=wsObj.items.map(x=>x.text);
vm.runInContext('worksheetRerollOne(2)',wsContext,{timeout:1000});
assert.equal(wsObj.items.length,10);
assert.equal(wsObj.items[0].text,allBefore[0]);
assert.equal(wsObj.items[1].text,allBefore[1]);
assert.equal(wsObj.items[3].text,allBefore[3]);
wsObj.items=[{text:'5 + 3 =',answer:'9'}];
const invalid=vm.runInContext('worksheetIssues(ui.worksheet)',wsContext,{timeout:1000});
assert.ok(invalid.some(x=>x.level==='error'&&x.message.includes('계산식')),'Wrong math answer must be detected');
wsObj.items=[{text:'나의 즐거운 하루',answer:'자유 응답'}];wsObj.kind='writing';
const writing=vm.runInContext('renderWorksheet()',wsContext,{timeout:1000});
assert.ok(writing.includes('ws-writing-lines'),'Writing paper lines absent');
vm.runInContext('printWorksheet()',wsContext,{timeout:1000});
assert.ok(!/class="ws-sheet ws-cute ws-kind-writing [^"]*ws-answers/.test(wsContext.lastPrinted.body),'Writing should not print an answer page');
wsObj.kind='pattern';wsObj.items=[{text:'규칙을 찾아 빈칸에 알맞은 수를 쓰세요.  1 → 3 → 5 → □ → 9',answer:'7'}];
assert.ok(vm.runInContext('renderWorksheet()',wsContext).includes('ws-pattern-wide'),'Patterns should use full-width rows');
for(const action of ["worksheet-reroll","worksheet-edit","worksheet-save-one","worksheet-remove","worksheet-add","worksheet-preview-page"]){
 assert.ok(html.includes("case'"+action+"'"),"Worksheet action not wired: "+action);
}
console.log('✓ Worksheet studio: themes, ratio, math validation, purpose, A4, per-question edits and print validated');

const publicSheets=[
  '1BS2-5MUB_RP-GV8TgYscY70aNrxyRyiAaDSMd0H1Gv8',
  '11veDOcjX0EB-M2qmv46SZ2x-Yle1MKx32H54ySWenlc',
  '1gERSanAtJyXjvVaClyKokEKHDFbYTISckBaO_iq6s8A',
  '1z1SIGY0po5oZNPqbqylxw_3QjB2jh8y4arhDR0MW6MI'
];
for(const id of publicSheets){
  assert.ok(html.includes(id),'Expected public shortcut missing: '+id);
}
const blocked=[
  '1m6bmPL1oXSJQG2EPk0X2rLs2bPAzdZnw6ThTCVARj2s',
  '1ENaxKLSD59mleEZoyQP7V-O6k0y0TymNlHvjL9nt-po'
];
for(const id of blocked){
  assert.ok(!html.includes(id),'Sensitive sheet ID remains in public HTML');
}
assert.ok(html.includes('personalShortcutsPanel()'),'Google Sheets shortcut panel missing');
assert.ok(html.includes('🔗 4개 바로가기'),'Public shortcut count incorrect');
console.log('✓ HTML JavaScript syntax valid');
console.log('✓ Weekly recommendations grounded in PDF evidence');
console.log('✓ Lesson action handlers present');
console.log('✓ Four public Google Sheets shortcuts; two sensitive sheet IDs absent');
console.log('✓ Bulky recommendation panel and idea picker hidden; weekly PDFs and playable tools remain');
