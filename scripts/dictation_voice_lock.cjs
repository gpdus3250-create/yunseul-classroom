// Protect the two original Dictation Kingdom 37.0 AI voices from accidental changes.
// Both original sounds must remain byte-for-byte identical in all future releases.
// Future voices MUST be added under NEW folders and with NEW selectable options.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.join(__dirname, '..', 'dictation');
const lockPath = path.join(root, 'voice-lock.json');
const audio = path.join(root, 'voice');
const lockedManifestGitBlobSha = 'cf00ab23252757dd8816d872002c6d9fdea258be';
function gitBlobSha(bytes) {
  return crypto.createHash('sha1')
    .update(Buffer.from('blob ' + bytes.length + '\0'))
    .update(bytes)
    .digest('hex');
}
const lockBytes = fs.readFileSync(lockPath);
if (gitBlobSha(lockBytes) !== lockedManifestGitBlobSha) {
  throw Error('The original voice lock manifest has changed. Restore the frozen 37.0 voice manifest.');
}
const lock = JSON.parse(lockBytes.toString('utf8'));
if (Object.keys(lock.voices).sort().join(',') !== 'F1,M1') {
  throw Error('The original F1/M1 voice identities must be preserved.');
}
let verified = 0;
for (const voice of ['F1', 'M1']) {
  const expected = lock.voices[voice];
  const folder = path.join(audio, voice);
  const actualNames = fs.readdirSync(folder).filter(x => x.endsWith('.mp3')).sort();
  const expectedNames = Object.keys(expected).sort();
  if (actualNames.length !== 172 || actualNames.join('\0') !== expectedNames.join('\0')) {
    throw Error('Voice ' + voice + ': original set of 172 audio files was changed.');
  }
  for (const name of expectedNames) {
    const bytes = fs.readFileSync(path.join(folder, name));
    if (bytes.length !== expected[name].size || gitBlobSha(bytes) !== expected[name].git_blob_sha) {
      throw Error('Voice ' + voice + ': original audio must never be altered: ' + name);
    }
    verified++;
  }
}
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
for (const voice of ['F1', 'M1']) {
  if (!html.includes('<option value="' + voice + '">')) {
    throw Error('The original voice ' + voice + ' was removed from voice selection.');
  }
}
if (!html.includes("audioConfig.recordedVoice") || !html.includes("voice/'+audioConfig.recordedVoice+'/")) {
  throw Error('Audio playback no longer references the preserved original voice folders.');
}
console.log('Verified ' + verified + ' frozen AI MP3 files (F1/M1); names, bytes and selectable options unchanged.');
