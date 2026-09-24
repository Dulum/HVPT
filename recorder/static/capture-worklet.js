// Runs on the audio thread: forwards raw mono samples to the main thread.
class CaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) this.port.postMessage(channel.slice(0));
    return true;
  }
}

registerProcessor("capture-processor", CaptureProcessor);
