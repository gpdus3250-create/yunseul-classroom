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


// Verify both printable worksheet designs with a functional HTML preview and print smoke test.
const appJs=scripts[0][1];
const worksheetStart=appJs.indexOf('const WORKSHEET_PRINT_CSS=');
const worksheetEnd=appJs.indexOf('// 2. 읽기 왕국',worksheetStart);
assert.ok(worksheetStart>0&&worksheetEnd>worksheetStart,'Worksheet theme implementation missing');
const worksheetCode=appJs.slice(worksheetStart,worksheetEnd);
const dummyItems=Array.from({length:11},(_,i)=>({text:(i+1)+' + 2 =',answer:String(i+3)}));
const wsObj={theme:'cute',kind:'math',n:11,difficulty:'normal',items:dummyItems,answers:false};
const fakeDb={settings:{grade:1,room:6,school:'우리 학교'}};
const htmlSafe=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const wsContext=vm.createContext({
 ui:{worksheet:wsObj},db:fakeDb,safe:htmlSafe,console,
 localStorage:{getItem(){return 'cute'},setItem(){}},
 heading:(a,b,c)=>'<h2>'+b+'</h2>',
 shell:(a,b)=>'<section><h3>'+a+'</h3>'+b+'</section>',
 blank:message=>message,
 hField:(label,body)=>'<label>'+label+body+'</label>',
 selectOptions:(items,chosen)=>items.map(([value,title])=>'<option '+(chosen===value?'selected':'')+'>'+title+'</option>').join(''),
 printHTML:(title,body)=>{wsContext.lastPrinted={title,body};return true}
});
vm.runInContext(worksheetCode,wsContext,{timeout:3000});
const cuteHtml=vm.runInContext('renderWorksheet()',wsContext,{timeout:1000});
assert.ok(cuteHtml.includes('ws-cute'),'Cute worksheet preview not rendered');
assert.ok(cuteHtml.includes('ws-bunny'),'Cute illustration missing');
assert.ok(cuteHtml.includes('data-id="cute"')&&cuteHtml.includes('data-id="simple"'),'Theme picker missing');
assert.equal(wsObj.items.length,11);
wsObj.theme='simple';
const simpleHtml=vm.runInContext('renderWorksheet()',wsContext,{timeout:1000});
assert.ok(simpleHtml.includes('ws-simple'),'Simple worksheet preview not rendered');
assert.ok(!simpleHtml.includes('<span class="ws-bunny">'),'Simple design should not print cute illustration');
assert.equal(wsObj.items.length,11,'Switching theme changed worksheet questions');
vm.runInContext('printWorksheet()',wsContext,{timeout:1000});
assert.ok(wsContext.lastPrinted.body.includes('ws-simple'),'Print did not preserve selected design');
assert.ok(wsContext.lastPrinted.body.includes('.ws-sheet.ws-cute'),'Print CSS for both themes missing');
assert.equal((wsContext.lastPrinted.body.match(/ws-print/g)||[]).length>0,true);
assert.equal((wsContext.lastPrinted.body.match(/class="ws-sheet ws-simple ws-kind-math ws-print"/g)||[]).length,2,
  'Eleven math questions should print on two A4 question pages');
assert.ok(wsContext.lastPrinted.body.includes('ws-answers'),'Printable answer key missing');
wsObj.theme='cute';
vm.runInContext('printWorksheet()',wsContext,{timeout:1000});
assert.ok(wsContext.lastPrinted.body.includes('ws-cute'),'Cute design does not print');
wsObj.kind='writing';
wsObj.items=[{text:'나의 즐거운 하루',answer:'자유 응답'}];
const writingPreview=vm.runInContext('renderWorksheet()',wsContext,{timeout:1000});
assert.ok(writingPreview.includes('ws-writing-lines'),'Writing guide lines missing');
vm.runInContext('printWorksheet()',wsContext,{timeout:1000});
assert.ok(!wsContext.lastPrinted.body.includes('class="ws-sheet ws-cute ws-kind-writing ws-answers'),'Writing worksheets should not print an unhelpful answer key');
console.log('✓ Cute/simple worksheet styles preview correctly, preserve questions and print A4 pages');

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
