// Records microphone audio as uncompressed 16-bit mono WAV.
//
// MediaRecorder would give webm/opus on Chrome and mp4/aac on Safari; lossy
// codecs smear exactly the acoustic detail we care about, so we capture raw
// PCM through an AudioWorklet and encode the WAV ourselves.

export class WavRecorder {
  async init() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        // Browser "voice call" processing distorts speech; keep it natural.
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
    });
    this.ctx = new AudioContext();
    await this.ctx.audioWorklet.addModule("capture-worklet.js");
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, "capture-processor");
    this.node.port.onmessage = (e) => {
      if (this.recording) this.chunks.push(e.data);
    };
    this.source.connect(this.node);
    this.recording = false;
    this.chunks = [];
  }

  async start() {
    if (this.ctx.state !== "running") await this.ctx.resume();
    this.chunks = [];
    this.recording = true;
  }

  stop() {
    this.recording = false;
    return encodeWav(this.chunks, this.ctx.sampleRate);
  }
}

function encodeWav(chunks, sampleRate) {
  const length = chunks.reduce((n, c) => n + c.length, 0);
  const buffer = new ArrayBuffer(44 + length * 2);
  const view = new DataView(buffer);
  const writeStr = (offset, s) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  };

  writeStr(0, "RIFF");
  view.setUint32(4, 36 + length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true); // fmt chunk size
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeStr(36, "data");
  view.setUint32(40, length * 2, true);

  let offset = 44;
  for (const chunk of chunks) {
    for (let i = 0; i < chunk.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, chunk[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
  }
  return new Blob([buffer], { type: "audio/wav" });
}
