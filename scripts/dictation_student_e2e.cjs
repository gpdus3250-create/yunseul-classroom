/* Real-browser student playthrough for the deployed single-file classroom app.
 * Tests a Chromium viewport comparable to the actual 4-team smartboard.
 * Clicks the rendered student controls, never forces game answers directly.
 */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

const SITE = process.env.DICTATION_E2E_URL || 'http://127.0.0.1:8765/';
const pause = ms => new Promise(r => setTimeout(r, ms));
const log = (...msg) => console.log('[학생 플레이]', ...msg);
const NAMES = ['테스트가람','테스트나래','테스트다온','테스트라온','테스트마루','테스트바다','테스트솔','테스트하늘'];
let browser;

async function visibleAndClickable(locator, label) {
  await locator.waitFor({state:'visible',timeout:12000});
  const result = await locator.evaluate(element => {
    const rect=element.getBoundingClientRect();
    const style=getComputedStyle(element);
    const top=document.elementFromPoint(Math.min(innerWidth-1,Math.max(0,rect.x+rect.width/2)),Math.min(innerHeight-1,Math.max(0,rect.y+rect.height/2)));
    return {
      text:element.textContent.trim().slice(0,40),
      width:rect.width,height:rect.height,top:rect.top,bottom:rect.bottom,
      styleDisplay:style.display,styleVisibility:style.visibility,opacity:Number(style.opacity),
      hit:top===element||element.contains(top),overlap:top?.className || top?.tagName,
      inViewport:rect.bottom>0 && rect.top<innerHeight && rect.left<innerWidth && rect.right>0
    };
  });
  assert(result.width>10&&result.height>10, label+' zero-size: '+JSON.stringify(result));
  assert(result.opacity>.45&&result.styleVisibility!=='hidden',label+' invisible '+JSON.stringify(result));
  assert(result.inViewport, label+' outside browser viewport '+JSON.stringify(result));
  assert(result.hit, label+' overlapped or clipped '+JSON.stringify(result));
  return result;
}

async function setup(page, kind, questionsPerChild=1, people=8) {
  await page.goto(SITE,{waitUntil:'domcontentloaded',timeout:40000});
  await page.locator('.tab[data-v="multi"]').click();
  await page.locator('.grade').first().click();
  const count=await page.evaluate(()=>classNames().length);
  if(count===0){
    await page.locator('#adQuickNameInput').fill(NAMES.slice(0,people).join('\n'));
    await page.locator('.ad-quick-submit').click();
  }
  await page.locator('.ad-modecard').filter({hasText:kind==='build'?'글자 블록 공방':kind==='repair'?'낱말 수리소':'받아쓰기 보스전'}).click();
  await page.locator('.ad-count-custom select').selectOption(String(questionsPerChild));
  await page.locator('.ad-launch').click();
  assert.equal(await page.locator('.ad-lane').count(),4,'4 students must have game lanes');
}

async function performCorrectTurn(page, index, shouldBeCorrect=true) {
  const lane=page.locator('#adlane-'+index);
  await lane.waitFor({state:'visible'});
  const item=await page.evaluate(i=>{
    const t=adventure.lanes[i].task;
    return {type:t.type,index:t.index,good:t.good,options:t.options,tiles:t.tiles,target:t.target,wordIndex:t.wordIndex};
  },index);
  const name=(await lane.locator('.ad-current-name').innerText()).trim();
  if(item.type==='repair'){
    await visibleAndClickable(lane.locator('.ad-word').nth(item.index),name+' repair-word');
    await lane.locator('.ad-word').nth(item.index).click();
    let position=item.options.findIndex(x=>shouldBeCorrect?x===item.good:x!==item.good);
    assert(position>=0, 'repair choices must include expected answer');
    await visibleAndClickable(lane.locator('.ad-replace').nth(position),name+' repair-replacement');
    await lane.locator('.ad-replace').nth(position).click();
  }else{
    assert.equal(item.type,'build');
    const available=item.tiles.map((x,j)=>({j,val:x.val}));
    const chosen=[];
    for(const c of [...item.target]){
      let matching=available.find(x=>x.val===c&&!chosen.includes(x.j));
      assert(matching, 'missing expected tile '+c+' in '+name+' tiles');
      chosen.push(matching.j);
    }
    if(!shouldBeCorrect){
      const other=available.find(x=>!chosen.includes(x.j));
      if(other)chosen[0]=other.j;
    }
    const undoOnce=shouldBeCorrect&&index===0;
    if(undoOnce){
      await visibleAndClickable(lane.locator('.ad-tile').nth(chosen[0]),name+' tile before undo');
      await lane.locator('.ad-tile').nth(chosen[0]).click();
      await visibleAndClickable(lane.locator('.ad-undo'),name+' undo');
      await lane.locator('.ad-undo').click();
      assert.equal((await lane.locator('.ad-build-line').innerText()).replace(/\s/g,'').replace(/＿/g,''),'','undo must remove letter');
    }
    for(let k=0;k<chosen.length;k++){
      await visibleAndClickable(lane.locator('.ad-tile').nth(chosen[k]),name+' tile '+k);
      await lane.locator('.ad-tile').nth(chosen[k]).click();
      const text=await lane.locator('.ad-build-line').innerText();
      assert(text.trim(),name+' selected letters must become visible');
    }
    const confirm=lane.locator('.ad-send');
    assert(!(await confirm.isDisabled()),name+' completed word should be submit-able');
    await visibleAndClickable(confirm,name+' submit');
    await confirm.click();
  }
  const done=await page.evaluate(i=>adventure.lanes[i].done,index);
  assert(done,name+' answer not recorded');
  return name;
}

async function play4Teams(browser,kind,questionsPerChild){
  const page=await browser.newPage({viewport:{width:1800,height:850},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror', e=>errors.push(e.message));
  try {
    log('시작',kind,questionsPerChild+'문제/학생');
    await setup(page,kind,questionsPerChild);
    const visited=new Set();
    let rounds=0, sawWrong=false, sawWait=false, bossCleared=false;
    while(rounds<25){
      const stage=await page.evaluate(()=>phase);
      if(stage==='done')break;
      if(stage==='ready'){
        const active=await page.evaluate(()=>adventure.lanes.map((p,i)=>p.turnName===null?-1:i).filter(i=>i>=0));
        assert(active.length>0,'no student active in ready state');
        for(const i of active){
          const name=await page.locator('#adlane-'+i+' .ad-current-name').innerText();
          visited.add(name.trim());
          const button=page.locator('#adlane-'+i+' .ad-ready');
          await visibleAndClickable(button,name+' ready');
          await button.click();
        }
        await page.waitForFunction(()=>phase==='play',{timeout:20000});
        assert.equal(await page.locator('.ad-lane').count(),4);
      }
      await page.waitForFunction(()=>phase==='play',{timeout:5000});
      const active=await page.evaluate(()=>adventure.lanes.map((p,i)=>p.turnName===null?-1:i).filter(i=>i>=0));
      for(let k=0;k<active.length;k++){
        const i=active[k];
        const shouldBeCorrect=!(rounds===0&&k===0);
        await performCorrectTurn(page,i,shouldBeCorrect);
        if(!shouldBeCorrect)sawWrong=true;
        if(k===0 && active.length>1){
          assert.equal(await page.evaluate(()=>phase),'play','answers revealed before all teams submitted');
          assert(await page.locator('#adlane-'+i+' .ad-submitted-card').isVisible(),'submitted student must have a visible waiting card');
          sawWait=true;
        }
      }
      await page.waitForFunction(()=>phase==='reveal',{timeout:4000});
      assert(await page.locator('#adlane-'+active[0]+' .ad-reveal-result').isVisible(),'reveal result missing');
      const wrong=await page.locator('.ad-reveal-result.bad').count();
      if(rounds===0)assert(wrong>=1,'wrong response was not marked');
      await page.waitForFunction(()=>phase==='ready'||phase==='play'||phase==='boss-clear'||phase==='done',{timeout:16000});
      const next=await page.evaluate(()=>phase);
      if(next==='boss-clear'){
        bossCleared=true;
        assert(await page.locator('.boss-cleared-next').isVisible(),'boss defeat should show continue');
        await visibleAndClickable(page.locator('.boss-cleared-next'),'boss next');
        await page.locator('.boss-cleared-next').click();
      }
      rounds++;
      log(kind,'라운드',rounds,'단계',await page.evaluate(()=>phase));
    }
    assert.equal(await page.evaluate(()=>phase),'done',kind+' did not finish: '+rounds);
    assert(visited.size===8,kind+' expected all eight players to participate, got '+visited.size);
    assert(sawWrong&&sawWait,'must test wrong answer and waiting');
    if(kind==='boss')assert(bossCleared,'boss victory modal was never exercised');
    assert.equal(errors.length,0,'browser JS exceptions: '+errors.join('; '));
    log('합격',kind,rounds+'라운드',visited.size+'명 참여');
    return {kind,rounds,participants:visited.size,bossCleared};
  }catch(e){
    const path='/tmp/'+kind+'-failure.png';
    try{await page.screenshot({path,fullPage:true,timeout:9000})}catch(_){}
    log('실패',kind,e.stack||e.message,'screenshot',path,'pageerrors',errors);
    throw e;
  }finally{await page.close()}
}
async function sharedChoice(browser){
  const page=await browser.newPage({viewport:{width:1800,height:850}});
  try{
    await page.goto(SITE);
    await page.locator('.tab[data-v="board"]').click();
    await page.locator('.board-choice-secondary').click();
    await page.locator('.grade').first().click();
    await page.locator('button').filter({hasText:'3문제'}).last().click();
    await page.locator('button').filter({hasText:'3지선다 테스트 시작'}).last().click();
    for(let i=0;i<4;i++)await page.locator('.tg-lane').nth(i).locator('.tg-ready-btn').click();
    assert.equal(await page.locator('.tg-option').count(),12,'4 students each need three answers');
    const shared=await page.evaluate(()=>({q:togetherState.question.text,choices:togetherState.choices}));
    for(let i=0;i<4;i++){
      const buttons=await page.locator('.tg-lane').nth(i).locator('.tg-option').allTextContents();
      assert.deepEqual(buttons.map(t=>t.replace(/^\s*\d+/,'').trim()),shared.choices);
      await visibleAndClickable(page.locator('.tg-lane').nth(i).locator('.tg-option').nth(0),'3choice student '+i);
      await page.locator('.tg-lane').nth(i).locator('.tg-option').nth(0).click();
      if(i===0)assert.equal(await page.evaluate(()=>togetherState.stage),'play');
    }
    assert.equal(await page.evaluate(()=>togetherState.stage),'reveal','should reveal after all answer');
    log('합격: 3지선다 동일문장/동일보기에 따른 독립 선택');
  }finally{await page.close()}
}
async function auditAllGradeSentences(browser) {
 const page=await browser.newPage();
 try {
  await page.goto(SITE);
  const report=await page.evaluate(()=>{
   const cases=[],errors=[];
   for(let grade=1;grade<=14;grade++)for(let index=0;index<10;index++){
     const text=levels[grade][index],q={grade,index,text,id:grade+':'+index};
     try{
       const opt=makeOptions(text);
       if(opt.length!==3||new Set(opt).size!==3||opt.filter(x=>x===text).length!==1)
         throw Error('3지선다 오답 생성 비정상');
       const repair=adRepairTask(q);
       if(repair.options.length!==3||new Set(repair.options).size!==3||repair.options.filter(x=>x===repair.good).length!==1)
         throw Error('낱말 수리소 보기 생성 비정상');
       const build=adBuildTask(q);
       const counts=new Map();
       for(const tile of build.tiles)counts.set(tile.val,(counts.get(tile.val)||0)+1);
       for(const ch of build.target){
         if(!(counts.get(ch)>0))throw Error('정답 글자 '+ch+' 누락');
         counts.set(ch,counts.get(ch)-1);
       }
       if(build.tiles.length!==[...build.target].length+2)
         throw Error('글자 블록 개수 이상');
       cases.push(q.id);
     }catch(e){errors.push({grade,index,text,error:e.message})}
   }
   return {checked:cases.length+errors.length,passed:cases.length,errors};
  });
  log('140문장 출제 전수 검사',JSON.stringify(report));
  assert.equal(report.checked,140,'question bank size mismatch');
  assert.deepEqual(report.errors,[],'Question generation failure(s)');
  return report;
 }finally{await page.close()}
}
async function auditTwoToSixTeamLayouts(browser) {
 const layouts=[];
 for(const count of [2,3,5,6]){
  const page=await browser.newPage({viewport:{width:1800,height:850}});
  try{
   await page.goto(SITE);
   await page.locator('.tab[data-v="multi"]').click();
   await page.locator('.grade').first().click();
   await page.locator('#adQuickNameInput').fill(NAMES.join('\\n'));
   await page.locator('.ad-quick-submit').click();
   await page.locator('.ad-team-actions button').filter({hasText:count+'팀'}).click();
   await page.locator('.ad-launch').click();
   const lanes=page.locator('.ad-lane');
   assert.equal(await lanes.count(),count,'Incorrect lane count at '+count+' teams');
   for(let i=0;i<count;i++){
     await visibleAndClickable(page.locator('#adlane-'+i+' .ad-ready'),count+' teams ready '+i);
   }
   layouts.push(count);
   log('합격',count+'팀', '전원 준비완료 버튼 실제 화면 표시 확인');
  }finally{await page.close()}
 }
 return layouts;
}
(async()=>{
 browser=await chromium.launch({headless:true,channel:'chrome',args:['--no-sandbox']});
 const results=[];
 try{
   results.push(await play4Teams(browser,'build',1));
   results.push(await play4Teams(browser,'repair',1));
   results.push(await play4Teams(browser,'boss',2));
   await sharedChoice(browser);
   await auditAllGradeSentences(browser);
   await auditTwoToSixTeamLayouts(browser);
   log('전 과정 통과',JSON.stringify(results));
 }finally{await browser.close()}
})().catch(e=>{console.error('[학생 플레이 테스트 실패]',e.stack||e.message);process.exitCode=1});
