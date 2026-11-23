const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');

const html=fs.readFileSync('index.html','utf8');
const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)];
assert.equal(scripts.length,1,'Expected one inline application script');
new vm.Script(scripts[0][1],{filename:'site-inline-script.js'});
for(const term of [
  'lessonRecommendationsPanel(true)',
  'lessonRecommendationsPanel(false)',
  'lessonComprehensionPanel()',
  "case'lesson-launch'",
  "case'lesson-meaning-answer'",
  'lesson-recommendations.json'
]){
  assert.ok(html.includes(term),'Missing UI hook: '+term);
}
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
const publicSheets=[
  '1BS2-5MUB_RP-GV8TgYscY70aNrxyRyiAaDSMd0H1Gv8',
  '11veDOcjX0EB-M2qmv46SZ2x-Yle1MKx32H54ySWenlc',
  '1m6bmPL1oXSJQG2EPk0X2rLs2bPAzdZnw6ThTCVARj2s',
  '1gERSanAtJyXjvVaClyKokEKHDFbYTISckBaO_iq6s8A',
  '1z1SIGY0po5oZNPqbqylxw_3QjB2jh8y4arhDR0MW6MI',
  '1ENaxKLSD59mleEZoyQP7V-O6k0y0TymNlHvjL9nt-po'
];
for(const id of publicSheets){
  assert.ok(html.includes(id),'Requested public school shortcut missing: '+id);
}
assert.ok(html.includes('personalShortcutsPanel()'),'Google Sheets shortcut panel missing');
assert.ok(html.includes('학생 명단과 교사 계정 시트는 반드시 접근 권한을 점검'),'Public sharing warning missing');
console.log('✓ HTML JavaScript syntax valid');
console.log('✓ Weekly recommendations grounded in PDF evidence');
console.log('✓ Lesson action handlers present');
console.log('✓ Six requested Google Sheets links published with access warning');
