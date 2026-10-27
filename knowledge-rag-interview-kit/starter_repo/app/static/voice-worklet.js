// Capture PCM on the audio thread. Unlike ScriptProcessorNode, AudioWorklet is current.
class VoiceCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(4096);
    this.used = 0;
    this.active = true;
    this.port.onmessage = ({ data }) => {
      if (data === 'stop') {
        this.active = false;
        this.flush();
        this.port.postMessage({ stopped: true });
      }
    };
  }
  flush() {
    if (!this.used) return;
    const samples = this.buffer.slice(0, this.used);
    this.port.postMessage({ samples }, [samples.buffer]);
    this.used = 0;
  }
  process(inputs) {
    if (!this.active) return false;
    const input = inputs[0]?.[0];
    if (input) {
      for (let i = 0; i < input.length; i++) {
        this.buffer[this.used++] = input[i];
        if (this.used === this.buffer.length) this.flush();
      }
    }
    return true; // Outputs are silence: never play the microphone back to speakers.
  }
}
registerProcessor('voice-capture', VoiceCapture);
