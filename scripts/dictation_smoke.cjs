const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const file = path.join(__dirname, '..', 'dictation', 'index.html');
const html = fs.readFileSync(file, 'utf8');
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
if (scripts.length !== 1) throw Error('Expected one inline application script');
new vm.Script(scripts[0][1], { filename: 'dictation/index.html:inline.js' });
if (!html.includes('받아쓰기 왕국') || !html.includes('recordedMode') ||
    !html.includes('function playRecorded') || !html.includes('function examSpeech')) {
  throw Error('Core dictation or AI voice controls missing');
}
const sentenceArray = html.match(/const ORIGINAL=(\{[^\n]+\}), CURATED=/);
if (!sentenceArray) throw Error('Original grade table missing');
const grades = JSON.parse(sentenceArray[1]);
if (Object.keys(grades).length !== 14 || Object.values(grades).some(x => x.length !== 10)) {
  throw Error('Expected exactly 140 dictation sentences');
}
console.log('Dictation Kingdom verified: JavaScript parses, 140 original sentences retained, AI voice controls present.');
