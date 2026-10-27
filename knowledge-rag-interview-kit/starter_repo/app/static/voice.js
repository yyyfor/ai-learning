// All model/storage calls use our backend. No browser speech service or cloud ASR.
(() => {
  let setup = null, starting = false, recording = false, stopping = false, working = false;
  let processing = false, failed = false, autoSummary = false, savedId = null;
  let context = null, stream = null, source = null, capture = null, stopAck = null;
  let frames = [], chunkFrames = [], chunkLength = 0, totalSamples = 0, rate = 16000;
  let queue = [], completedSeconds = 0, audioUrl = null;
  let captureRequest = 0;
  const maxSeconds = 600;
  const transcript = $('voice-transcript');
  const summary = $('voice-summary');

  const busy = () => starting || recording || stopping || working || processing || queue.length > 0;
  function message(text, error = false) {
    $('voice-message').textContent = text;
    $('voice-message').classList.toggle('error', error);
  }
  function changed() {
    savedId = null;
    $('voice-saved').replaceChildren();
    controls();
  }
  function controls() {
    const locked = busy();
    $('voice-start').disabled = locked || !setup?.transcription_ready;
    $('voice-stop').disabled = !(recording || starting) || stopping;
    $('voice-stop').textContent = starting ? 'Cancel microphone request' : 'Stop recording';
    $('voice-start').textContent = totalSamples ? 'Continue recording' : 'Start recording';
    $('voice-retry').hidden = !failed;
    $('voice-retry').disabled = processing || recording || working;
    $('voice-summarize').disabled = locked || !transcript.value.trim() || !setup?.summary_ready;
    $('voice-save').disabled = locked || !transcript.value.trim() || Boolean(savedId);
    $('voice-clear').disabled = starting || recording || stopping || processing || working;
    $('voice-language').disabled = locked;
    $('voice-title').disabled = working;
    $('voice-file').disabled = locked || !setup?.transcription_ready;
    transcript.readOnly = locked;
    summary.readOnly = locked;
    $('voice-refresh').disabled = locked;
    $('voice-state').textContent = starting ? 'Requesting microphone' : recording ? 'Recording' :
      stopping ? 'Stopping microphone' : failed ? 'Transcription paused' : processing ? 'Transcribing' : working ? 'Working' : 'Ready';
    $('voice-state').classList.toggle('recording', recording);
    $('voice-progress').textContent = `${Math.floor(totalSamples / rate)}s captured · ${Math.floor(completedSeconds)}s transcribed · ${queue.length} chunk(s) waiting`;
  }
  async function loadStatus() {
    try {
      setup = await api('/voice/status');
      $('voice-setup-status').textContent = [
        setup.transcription_ready ? `Speech: ${setup.speech_model} · local CPU` : setup.transcription_problem,
        setup.summary_ready ? `Summary: ${setup.summary_model} · local Ollama` : setup.summary_problem,
      ].join(' | ');
      $('voice-setup').open = !setup.transcription_ready || !setup.summary_ready;
    } catch (error) {
      setup = null;
      $('voice-setup-status').textContent = errorMessage(error);
    }
    controls();
  }
  function wav(parts, sampleRate) {
    const count = parts.reduce((sum, part) => sum + part.length, 0);
    const buffer = new ArrayBuffer(44 + count * 2), view = new DataView(buffer);
    const word = (offset, value) => [...value].forEach((char, i) => view.setUint8(offset + i, char.charCodeAt(0)));
    word(0, 'RIFF'); view.setUint32(4, 36 + count * 2, true); word(8, 'WAVE');
    word(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
    view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    word(36, 'data'); view.setUint32(40, count * 2, true);
    let offset = 44;
    for (const part of parts) for (const value of part) {
      const sample = Math.max(-1, Math.min(1, value));
      view.setInt16(offset, sample < 0 ? sample * 32768 : sample * 32767, true); offset += 2;
    }
    return new Blob([buffer], { type: 'audio/wav' });
  }
  function enqueue() {
    if (!chunkLength) return;
    queue.push(wav(chunkFrames, rate));
    chunkFrames = []; chunkLength = 0;
    controls();
    void drain();
  }
  function receive(samples) {
    if (!samples.length) return;
    frames.push(samples); chunkFrames.push(samples);
    totalSamples += samples.length; chunkLength += samples.length;
    let energy = 0;
    for (const value of samples) energy += value * value;
    $('voice-level').value = Math.min(1, Math.sqrt(energy / samples.length) * 5);
    if (chunkLength >= rate * 8) enqueue();
    controls();
    if (recording && (totalSamples >= maxSeconds * rate || queue.length >= 8)) {
      message(queue.length >= 8 ? 'Speech processing is falling behind. Recording stopped; pending audio is retained.' : '10-minute recording limit reached. Finishing this recording.');
      void stop();
    }
  }
  async function drain() {
    if (processing || failed) return;
    const hadWork = queue.length > 0;
    processing = true; controls();
    try {
      while (queue.length && !failed) {
        const data = new FormData();
        data.append('file', queue[0], 'chunk.wav');
        data.append('language', $('voice-language').value);
        const result = await api('/voice/transcribe', { method: 'POST', body: data, timeout: 180000 });
        const next = [transcript.value.trim(), result.text].filter(Boolean).join('\n');
        if (next.length > 24000) throw new Error('Transcript limit reached. Download your audio and start a new note.');
        transcript.value = next;
        transcript.scrollTop = transcript.scrollHeight;
        completedSeconds += result.duration_seconds;
        queue.shift(); changed();
        $('voice-latency').textContent = `Last ${result.duration_seconds}s chunk processed in ${result.processing_seconds}s${result.text ? '' : ' · no speech detected'}`;
      }
    } catch (error) {
      failed = true; autoSummary = false;
      message(`${errorMessage(error)} Pending audio is kept in this page. Use Retry or download the recording.`, true);
      if (recording) await stop();
    } finally {
      processing = false; controls();
      if (!recording && !stopping && !failed && autoSummary) {
        autoSummary = false;
        if (transcript.value.trim() && setup?.summary_ready) void summarize();
        else message(transcript.value.trim() ? 'Transcription complete. Start local Ollama to generate a summary.' : 'No speech detected. Try speaking closer to the microphone.');
      } else if (hadWork && !recording && !stopping && !failed) {
        message(transcript.value.trim() ? 'Transcription complete. Review the text, then generate a summary or save.' : 'No speech detected. Try speaking closer to the microphone.');
      }
    }
  }
  async function start() {
    if (busy()) return;
    if (totalSamples >= maxSeconds * rate) { message('Start a new note to record more than 10 minutes.', true); return; }
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
      message('Microphone capture needs a supported browser at localhost or HTTPS. Open this page in Chrome/Safari, or upload an audio file.', true); return;
    }
    starting = true; autoSummary = false; controls();
    const request = ++captureRequest;
    let requestedContext = null, requestedStream = null;
    message('Allow microphone access in your browser. Recording begins only after permission is granted.');
    try {
      requestedContext = new AudioContext({ sampleRate: 16000 });
      context = requestedContext;
      await requestedContext.resume();
      if (request !== captureRequest) return;
      requestedStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      if (request !== captureRequest) { requestedStream.getTracks().forEach(track => track.stop()); return; }
      stream = requestedStream;
      await requestedContext.audioWorklet.addModule('/static/voice-worklet.js?v=20261025-2');
      if (request !== captureRequest) { requestedStream.getTracks().forEach(track => track.stop()); return; }
      rate = context.sampleRate;
      source = context.createMediaStreamSource(stream);
      capture = new AudioWorkletNode(context, 'voice-capture');
      capture.port.onmessage = ({ data }) => {
        if (data.samples) receive(data.samples);
        if (data.stopped && stopAck) stopAck();
      };
      source.connect(capture); capture.connect(context.destination);
      recording = true;
      summary.value = ''; changed();
      for (const track of stream.getTracks()) track.addEventListener('ended', () => {
        if (recording) { message('Microphone disconnected. Finishing the audio already captured.', true); void stop(); }
      });
      message('Recording locally. Transcript updates after each ~8-second chunk.');
    } catch (error) {
      requestedStream?.getTracks().forEach(track => track.stop());
      if (requestedContext && requestedContext.state !== 'closed') await requestedContext.close();
      if (request !== captureRequest) return;
      context = stream = source = capture = null;
      const help = error.name === 'NotAllowedError' ? 'Microphone permission was denied. Allow it in browser/site settings, or upload an audio file.' :
        error.name === 'NotFoundError' ? 'No microphone found. Connect one or upload an audio file.' : errorMessage(error);
      message(help, true);
    } finally { if (request === captureRequest) { starting = false; controls(); } }
  }
  async function stop() {
    if (starting) {
      captureRequest++;
      starting = false;
      stream?.getTracks().forEach(track => track.stop());
      const oldContext = context;
      context = stream = source = capture = null;
      if (oldContext && oldContext.state !== 'closed') await oldContext.close();
      message('Microphone request canceled. No recording will start from this request.');
      controls(); return;
    }
    if (!recording || stopping) return;
    recording = false; stopping = true; controls();
    autoSummary = $('voice-auto-summary').checked && !failed;
    // Flush the last partial buffer before stopping tracks; do not lose the final words.
    if (capture) await new Promise(resolve => {
      const timer = setTimeout(resolve, 1000);
      stopAck = () => { clearTimeout(timer); resolve(); };
      capture.port.postMessage('stop');
    });
    stream?.getTracks().forEach(track => track.stop());
    source?.disconnect(); capture?.disconnect();
    if (context && context.state !== 'closed') await context.close();
    context = stream = source = capture = stopAck = null;
    $('voice-level').value = 0;
    enqueue();
    stopping = false;
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    if (frames.length) {
      audioUrl = URL.createObjectURL(wav(frames, rate));
      $('voice-download').href = audioUrl; $('voice-download').hidden = false;
    }
    controls();
    if (!failed) { message('Microphone stopped. Finishing pending transcription.'); void drain(); }
  }
  function summaryText(value) {
    const lines = [value.overview];
    const list = (heading, values) => { if (values.length) lines.push(`\n${heading}`, ...values.map(item => `- ${item}`)); };
    list('Key points', value.key_points); list('Decisions', value.decisions);
    list('Action items', value.action_items.map(item => `${item.task}${item.owner ? ` — ${item.owner}` : ''}${item.due ? ` · ${item.due}` : ''}${item.evidence ? `\n  Evidence: ${item.evidence}` : ''}`));
    list('Open questions', value.open_questions);
    return lines.join('\n');
  }
  async function summarize() {
    if (busy() || !transcript.value.trim()) return;
    working = true; controls(); message('Generating notes with local Ollama. Longer transcripts are summarized in parts.');
    try {
      const result = await api('/voice/summary', { method: 'POST', timeout: 1800000,
        body: JSON.stringify({ transcript: transcript.value.trim(), language: $('voice-language').value }) });
      summary.value = summaryText(result.summary);
      changed(); message(`Summary ready · ${result.model} · ${result.parts} transcript part(s). Review it before saving. ${(result.warnings || []).join(' ')}`);
    } catch (error) { message(errorMessage(error), true); }
    finally { working = false; controls(); }
  }
  async function save() {
    if (busy() || savedId || !transcript.value.trim()) return;
    const title = $('voice-title').value.trim();
    if (!title) { $('voice-title').reportValidity(); return; }
    working = true; controls();
    try {
      const result = await api('/documents', { method: 'POST', body: JSON.stringify({
        title, source: 'voice-notes', tags: ['voice', 'meeting-notes'],
        content: [summary.value.trim() ? `Summary (draft)\n${summary.value.trim()}` : '', `Transcript\n${transcript.value.trim()}`].filter(Boolean).join('\n\n'),
        metadata: { speech_model: setup?.speech_model, summary_model: setup?.summary_model,
          recorded_seconds: Math.round(totalSamples / rate), kind: 'voice-note', review_status: 'draft' },
      }) });
      savedId = result.id; window.labWorkspace?.invalidateDocuments();
      const open = element('button', '', 'Open saved document');
      open.addEventListener('click', () => showDocument(result.id));
      const index = element('button', '', 'Index for RAG');
      index.addEventListener('click', async () => {
        if (busy()) return;
        working = true; controls(); index.disabled = true;
        try {
          await api(`/rag/documents/${result.id}/index`, { method: 'POST', body: JSON.stringify({ strategy: 'recursive', chunk_size: 800, chunk_overlap: 80 }), timeout: 180000 });
          index.textContent = 'Indexed for RAG'; message('Voice note is ready to query in RAG answers.');
        } catch (error) { index.disabled = false; message(errorMessage(error), true); }
        finally { working = false; controls(); }
      });
      $('voice-saved').replaceChildren(element('span', 'helper', 'Saved as a draft document.'), open, index);
      message('Saved to the document library. You can index it for RAG next.');
    } catch (error) { message(errorMessage(error), true); }
    finally { working = false; controls(); }
  }
  async function importAudio(file) {
    if (!file || busy()) return;
    if (file.size > 20 * 1024 * 1024) { message('Choose an audio file up to 20 MiB and 10 minutes.', true); return; }
    working = true; controls(); message('Reading audio locally…');
    let decoder;
    try {
      decoder = new AudioContext({ sampleRate: 16000 });
      const audio = await decoder.decodeAudioData(await file.arrayBuffer());
      if (audio.duration + totalSamples / rate > maxSeconds) throw new Error('A voice note can contain up to 10 minutes of audio. Start a new note first.');
      const offline = new OfflineAudioContext(1, Math.ceil(audio.duration * rate), rate);
      const input = offline.createBufferSource(); input.buffer = audio; input.connect(offline.destination); input.start();
      const mono = (await offline.startRendering()).getChannelData(0);
      summary.value = ''; changed();
      // Queue every chunk in order; file import needs no microphone permission.
      for (let i = 0; i < mono.length; i += rate * 8) {
        const samples = mono.slice(i, i + rate * 8); frames.push(samples); totalSamples += samples.length;
        queue.push(wav([samples], rate));
      }
      autoSummary = $('voice-auto-summary').checked;
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audioUrl = URL.createObjectURL(wav(frames, rate));
      $('voice-download').href = audioUrl; $('voice-download').hidden = false;
      message('Audio loaded. Transcribing with the local speech model.');
    } catch (error) { message(`Could not read audio: ${errorMessage(error)}`, true); }
    finally { if (decoder) await decoder.close(); working = false; $('voice-file').value = ''; controls(); void drain(); }
  }
  function clear() {
    frames = []; chunkFrames = []; chunkLength = totalSamples = completedSeconds = 0;
    queue = []; failed = false; autoSummary = false;
    transcript.value = summary.value = ''; $('voice-latency').textContent = '';
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    audioUrl = null; $('voice-download').hidden = true; $('voice-download').removeAttribute('href');
    changed(); message('Ready for a new voice note.');
  }
  $('voice-start').addEventListener('click', start);
  $('voice-stop').addEventListener('click', stop);
  $('voice-refresh').addEventListener('click', loadStatus);
  $('voice-summarize').addEventListener('click', summarize);
  $('voice-save').addEventListener('click', save);
  $('voice-save-form').addEventListener('submit', event => { event.preventDefault(); void save(); });
  $('voice-clear').addEventListener('click', () => {
    if ((transcript.value || frames.length) && !confirm('Clear this note and the audio kept in this page? Download or save it first if needed.')) return;
    clear();
  });
  $('voice-retry').addEventListener('click', () => { failed = false; message('Retrying pending audio…'); void drain(); });
  transcript.addEventListener('input', () => { summary.value = ''; changed(); });
  summary.addEventListener('input', changed);
  $('voice-title').addEventListener('input', changed);
  $('voice-file').addEventListener('change', event => importAudio(event.target.files[0]));
  $('voice-drop').addEventListener('dragover', event => event.preventDefault());
  $('voice-drop').addEventListener('drop', event => { event.preventDefault(); void importAudio(event.dataTransfer.files[0]); });
  window.addEventListener('beforeunload', event => {
    if (busy() || (transcript.value && !savedId)) { event.preventDefault(); event.returnValue = ''; }
  });
  window.addEventListener('pagehide', () => stream?.getTracks().forEach(track => track.stop()));
  window.voiceWorkspace = {
    isBusy: busy,
    resetAccess: clear,
    navigate(view) {
      if (view === 'voice' && !busy()) void loadStatus();
      if (view !== 'voice' && (recording || starting)) void stop();
    },
  };
  controls();
  if (state.view === 'voice') void loadStatus();
})();
