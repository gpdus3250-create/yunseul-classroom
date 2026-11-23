// Frozen voice 38.0 sound assets: F2/M2 must not change during any future update.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.join(__dirname,'..','dictation');
const base=path.join(root,'voice');
const bytes=fs.readFileSync(path.join(root,'voice-lock-38.json'));
function sha(b){return crypto.createHash('sha1').update(Buffer.from('blob '+b.length+'\0')).update(b).digest('hex')}
if(sha(bytes)!=='1a77a6309b53bebc7f2758ccec32e84c30130d17')throw Error('The 38.0 voice lock is modified.');
const data=JSON.parse(bytes.toString('utf8')).voices;
if(Object.keys(data).sort().join(',')!=='F2,M2')throw Error('F2/M2 original voice identities missing.');
let count=0;
for(const v of ['F2','M2']){
const dir=path.join(base,v), expected=data[v];
const names=fs.readdirSync(dir).filter(x=>x.endsWith('.mp3')).sort();
if(names.length!==172||names.join('|')!==Object.keys(expected).sort().join('|'))throw Error(v+' voice files missing/added');
for(const name of names){
 const b=fs.readFileSync(path.join(dir,name));
 if(b.length!==expected[name].size||sha(b)!==expected[name].git_blob_sha)throw Error(v+'/'+name+' modified (must preserve original)');
 count++;
}
}
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
if(!html.includes('<option value="F2">')||!html.includes('<option value="M2">'))throw Error('38.0 voices must remain selectable');
console.log('Verified '+count+' unchanged 38.0 F2/M2 clips; original voices protected.');
