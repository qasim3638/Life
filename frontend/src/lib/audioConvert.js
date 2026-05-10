/**
 * Decode any audio Blob (AAC, WebM, MP4, etc.) and re-encode to WAV.
 * Used to normalize Capacitor Voice Recorder output (Android AAC) for
 * OpenAI Whisper, which doesn't accept raw AAC.
 *
 * Browser-only — uses Web Audio API + AudioContext.decodeAudioData.
 */

function writeString(view, offset, str) {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
}

function floatTo16BitPCM(view, offset, input) {
  for (let i = 0; i < input.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
}

function audioBufferToWavBlob(buffer) {
  const numChannels = 1; // force mono — smaller + Whisper is fine
  const sampleRate = buffer.sampleRate;
  // Downmix to mono
  let mono;
  if (buffer.numberOfChannels === 1) {
    mono = buffer.getChannelData(0);
  } else {
    const ch0 = buffer.getChannelData(0);
    const ch1 = buffer.getChannelData(1);
    mono = new Float32Array(ch0.length);
    for (let i = 0; i < ch0.length; i++) mono[i] = (ch0[i] + ch1[i]) / 2;
  }

  const dataLen = mono.length * 2; // 16-bit
  const bufferLen = 44 + dataLen;
  const arrBuf = new ArrayBuffer(bufferLen);
  const view = new DataView(arrBuf);

  // RIFF header
  writeString(view, 0, "RIFF");
  view.setUint32(4, bufferLen - 8, true);
  writeString(view, 8, "WAVE");
  // fmt chunk
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);             // PCM
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * numChannels * 2, true); // byte rate
  view.setUint16(32, numChannels * 2, true);              // block align
  view.setUint16(34, 16, true);                            // bits per sample
  // data chunk
  writeString(view, 36, "data");
  view.setUint32(40, dataLen, true);
  floatTo16BitPCM(view, 44, mono);

  return new Blob([arrBuf], { type: "audio/wav" });
}

export async function convertBlobToWav(blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) throw new Error("AudioContext not supported");
  const ctx = new Ctx();
  try {
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0));
    const wav = audioBufferToWavBlob(audioBuffer);
    return wav;
  } finally {
    if (ctx.close) ctx.close();
  }
}
