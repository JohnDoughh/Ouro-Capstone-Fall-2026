const state = {rater: null, assignment: null, loadEpoch: 0};
const $ = id => document.getElementById(id);
const REQUEST_DEADLINE_MS = 12000;

async function withDeadline(operation, message) {
  const controller = new AbortController();
  let timer;
  try {
    return await Promise.race([
      operation(controller.signal),
      new Promise((_, reject) => {
        timer = setTimeout(() => {
          reject(new Error(message));
          controller.abort();
        }, REQUEST_DEADLINE_MS);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

function clearAssignment() {
  state.loadEpoch++;
  state.assignment = null;
  $('submit').disabled = true;
  $('modality').textContent = '';
  $('artifact-id').textContent = '';
  $('media').replaceChildren();
}

$('signin-form').addEventListener('submit', async event => {
  event.preventDefault();
  state.rater = $('rater').value.trim();
  $('signin').classList.add('hidden');
  $('workspace').classList.remove('hidden');
  await loadNext();
});

$('retry-load').addEventListener('click', loadNext);

$('annotation-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!state.assignment) return;
  $('error').textContent = '';
  $('submit').disabled = true;
  try {
    const form = new FormData(event.target);
    const reason_codes = [...document.querySelectorAll('input[name=reason]:checked')].map(input => input.value);
    const response = await fetch(
      `/api/annotations/${state.assignment.assignment_id}?rater=${encodeURIComponent(state.rater)}`,
      {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          verdict: form.get('verdict'),
          confidence: Number(form.get('confidence')),
          severity: Number(form.get('severity')),
          defect_timestamps: String(form.get('defect_timestamps') || '').trim(),
          reason_codes,
          note: $('note').value,
        }),
      },
    );
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Submission failed');
    event.target.reset();
    await loadNext();
  } catch (error) {
    $('error').textContent = error.message || 'Submission failed';
  } finally {
    $('submit').disabled = !state.assignment;
  }
});

async function loadNext() {
  // A successful submission has already completed the previous assignment.
  // Never leave it actionable while the next request is pending or failed.
  clearAssignment();
  const loadEpoch = state.loadEpoch;
  $('retry-load').classList.add('hidden');
  $('error').textContent = '';
  try {
    const {response, body} = await withDeadline(async signal => {
      const response = await fetch(`/api/next?rater=${encodeURIComponent(state.rater)}`, {signal});
      return {response, body: await response.json()};
    }, 'Timed out loading the next assignment');
    if (state.loadEpoch !== loadEpoch) return;
    if (!response.ok) throw new Error(body.error || 'Unable to load the next assignment');
    $('progress').textContent = `${body.progress.completed} / ${body.progress.total} complete`;
    if (!body.assignment) {
      $('workspace').classList.add('hidden');
      $('done').classList.remove('hidden');
      return;
    }
    await renderMedia(body.assignment);
    if (state.loadEpoch !== loadEpoch) throw new Error('Assignment media load was interrupted');
    $('modality').textContent = body.assignment.modality;
    $('artifact-id').textContent = body.assignment.artifact_id;
    state.assignment = body.assignment;
    $('submit').disabled = false;
  } catch (error) {
    if (state.loadEpoch !== loadEpoch) return;
    clearAssignment();
    $('error').textContent = error.message || 'Unable to load the next assignment';
    $('retry-load').classList.remove('hidden');
  }
}

async function waitForPlayableMedia(element, item, readyEvent) {
  const loadEpoch = state.loadEpoch;
  await withDeadline(signal => new Promise((resolve, reject) => {
    let finished = false;
    const cleanup = () => {
      element.removeEventListener(readyEvent, onReady);
      element.removeEventListener('error', onError);
      signal.removeEventListener('abort', onAbort);
    };
    const onLateError = () => {
      if (state.loadEpoch !== loadEpoch) return;
      clearAssignment();
      $('error').textContent = 'Assignment media stopped loading; retry before judging';
      $('retry-load').classList.remove('hidden');
    };
    const onError = () => {
      if (finished) return;
      finished = true;
      cleanup();
      reject(new Error('Unable to load assignment media'));
    };
    const onAbort = () => {
      if (finished) return;
      finished = true;
      cleanup();
      element.removeAttribute('src');
      if (typeof element.load === 'function') element.load();
      reject(new Error('Timed out loading assignment media'));
    };
    const onReady = async () => {
      try {
        if (typeof element.decode === 'function') await element.decode();
        if (finished || signal.aborted) return;
        finished = true;
        cleanup();
        element.addEventListener('error', onLateError);
        resolve();
      } catch {
        onError();
      }
    };
    element.addEventListener(readyEvent, onReady);
    element.addEventListener('error', onError);
    signal.addEventListener('abort', onAbort, {once: true});
    element.src = item.media_url;
    $('media').append(element);
  }), 'Timed out loading assignment media');
}

async function renderMedia(item) {
  const media = $('media');
  media.replaceChildren();
  if (item.mime_type.startsWith('image/')) {
    const img = document.createElement('img');
    img.alt = 'Synthetic artifact to annotate';
    await waitForPlayableMedia(img, item, 'load');
  } else if (item.mime_type.startsWith('audio/')) {
    const audio = document.createElement('audio');
    audio.controls = true;
    await waitForPlayableMedia(audio, item, 'loadedmetadata');
  } else if (item.mime_type.startsWith('video/')) {
    const video = document.createElement('video');
    video.controls = true;
    video.playsInline = true;
    video.preload = 'metadata';
    video.setAttribute('aria-label', 'Synthetic video artifact to annotate');
    await waitForPlayableMedia(video, item, 'loadedmetadata');
  } else {
    const pre = document.createElement('pre');
    pre.textContent = 'Loading synthetic artifact…';
    media.append(pre);
    const content = await withDeadline(async signal => {
      const response = await fetch(item.media_url, {signal});
      if (!response.ok) throw new Error('Unable to load assignment media');
      return response.text();
    }, 'Timed out loading assignment media');
    pre.textContent = content;
  }
}
