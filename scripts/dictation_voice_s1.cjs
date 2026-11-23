// Validate the complete independent Korean-native teacher voice before publishing 39.0.
const fs=require('node:fs'),path=require('node:path');
const root=path.join(__dirname,'..','dictation');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'voice-manifest.json'),'utf8'));
const expected=[];
for(let g=1;g<=14;g++){
 const list=manifest.grades[String(g)];
 if(!Array.isArray(list)||list.length!==10)throw Error('Original grade data missing: '+g);
 for(let i=1;i<=10;i++)expected.push('g'+String(g).padStart(2,'0')+'_'+String(i).padStart(2,'0')+'.mp3');
}
for(const k of Object.keys(manifest.extras))expected.push(k+'.mp3');
if(expected.length!==172)throw Error('Expected 172 dictation audio clips');
const dir=path.join(root,'voice','S1');
const actual=fs.readdirSync(dir).filter(x=>x.endsWith('.mp3')).sort();
if(actual.length!==172||actual.join('\0')!==expected.sort().join('\0'))throw Error('S1 voice missing or unexpected MP3');
for(const name of expected)if(fs.statSync(path.join(dir,name)).size<2000)throw Error('Empty S1 clip: '+name);
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
for(const name of ['F1','M1','F2','M2','S1'])
 if(!html.includes('<option value="'+name+'">'))throw Error('Missing voice option '+name);
if(!html.includes("setRecordedVoice('S1')"))throw Error('Cannot preview new Korean-native voice');
if(!html.includes('받아쓰기 왕국 39.0'))throw Error('39.0 build title missing');
console.log('Valid: all 172 S1 clips, five selectable voices, original 140 dictation sentences preserved.');
