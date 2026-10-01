const state = {rater: null, assignment: null, loadEpoch: 0, pendingSave: null, saveBusy: false};
const $ = id => document.getElementById(id);
const REQUEST_DEADLINE_MS = 12000;
const PENDING_SAVE_KEY = 'ouro-eval-lab-pending-save-v1';

function validRaterId(value) {
  const characters = [...value];
  return characters.length > 0 && characters.length <= 80 &&
    characters.every(character => /^[\p{L}\p{N}_-]$/u.test(character));
}

function readRecoveryRecord() {
  const raw = sessionStorage.getItem(PENDING_SAVE_KEY);
  if (raw === null) {
    // A readable store is not enough for a new judgment: writes must work
    // before its first POST. Existing recovery needs only read and remove.
    const probe = `${PENDING_SAVE_KEY}-probe`;
    sessionStorage.setItem(probe, '1');
    if (sessionStorage.getItem(probe) !== '1') throw new Error('Session recovery storage is unavailable');
    sessionStorage.removeItem(probe);
    return null;
  }
  const record = JSON.parse(raw);
  const payload = record && typeof record.body === 'string' ? JSON.parse(record.body) : null;
  if (!record || record.version !== 1 ||
      typeof record.rater !== 'string' || !validRaterId(record.rater) ||
      typeof record.assignmentId !== 'string' || !/^[A-Za-z0-9_-]{1,200}$/.test(record.assignmentId) ||
      typeof record.body !== 'string' || record.body.length > 8192 ||
      record.url !== `/api/annotations/${record.assignmentId}?rater=${encodeURIComponent(record.rater)}` ||
      !payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Session recovery record is invalid');
  }
  return record;
}

function persistRecoveryRecord(pending) {
  const record = JSON.stringify({
    version: 1, rater: state.rater, assignmentId: pending.assignmentId,
    url: pending.url, body: pending.body,
  });
  sessionStorage.setItem(PENDING_SAVE_KEY, record);
  if (sessionStorage.getItem(PENDING_SAVE_KEY) !== record) {
    throw new Error('Session recovery storage did not retain the judgment');
  }
}

function discardRecoveryRecord() {
  sessionStorage.removeItem(PENDING_SAVE_KEY);
  if (sessionStorage.getItem(PENDING_SAVE_KEY) !== null) {
    throw new Error('Session recovery storage did not clear the judgment');
  }
}

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
  setJudgmentEditable(false);
  $('modality').textContent = '';
  $('artifact-id').textContent = '';
  $('media').replaceChildren();
}

function setJudgmentEditable(editable) {
  for (const control of $('annotation-form').querySelectorAll('input, textarea')) {
    control.disabled = !editable;
  }
}

$('signin-form').addEventListener('submit', async event => {
  event.preventDefault();
  const rater = $('rater').value.trim();
  if (!validRaterId(rater)) {
    $('signin-error').textContent = 'Use a pseudonymous rater ID of 1–80 letters, numbers, - or _.';
    return;
  }
  let recovery;
  try {
    recovery = readRecoveryRecord();
  } catch {
    $('signin-error').textContent = 'This tab cannot safely recover an interrupted save. Enable session storage or ask the lab facilitator before continuing.';
    return;
  }
  if (recovery && recovery.rater !== rater) {
    $('signin-error').textContent = 'Another rater has an unfinished save in this tab. Sign in with that rater ID to recover it before continuing.';
    return;
  }
  $('signin-error').textContent = '';
  state.rater = rater;
  $('signin').classList.add('hidden');
  $('workspace').classList.remove('hidden');
  if (recovery) {
    state.pendingSave = {...recovery, form: $('annotation-form'), mediaFailed: true};
    clearAssignment();
    $('progress').textContent = 'Previous judgment needs confirmation';
    $('error').textContent = 'A prior save may have completed. Retry the same frozen judgment to confirm it before loading another assignment.';
    $('retry-save').classList.remove('hidden');
    return;
  }
  await loadNext();
});

$('retry-load').addEventListener('click', loadNext);
$('retry-save').addEventListener('click', sendPendingSave);

$('annotation-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!state.assignment || state.pendingSave) return;
  $('error').textContent = '';
  $('submit').disabled = true;
  const form = new FormData(event.target);
  const reason_codes = [...document.querySelectorAll('input[name=reason]:checked')].map(input => input.value);
  // Freeze these exact bytes before the first request. A lost acknowledgement
  // must never turn into a second, edited judgment for the same assignment.
  const pending = {
    assignmentId: state.assignment.assignment_id,
    url: `/api/annotations/${state.assignment.assignment_id}?rater=${encodeURIComponent(state.rater)}`,
    body: JSON.stringify({
      verdict: form.get('verdict'),
      confidence: Number(form.get('confidence')),
      severity: Number(form.get('severity')),
      defect_timestamps: String(form.get('defect_timestamps') || '').trim(),
      reason_codes,
      note: $('note').value,
    }),
    form: event.target,
    mediaFailed: false,
  };
  try {
    persistRecoveryRecord(pending);
  } catch {
    $('error').textContent = 'This tab could not preserve the judgment for recovery. No save was sent; reload after fixing session storage or ask the lab facilitator.';
    $('submit').disabled = true;
    setJudgmentEditable(false);
    return;
  }
  state.pendingSave = pending;
  setJudgmentEditable(false);
  await sendPendingSave();
});

async function sendPendingSave() {
  const pending = state.pendingSave;
  if (!pending || state.saveBusy) return;
  state.saveBusy = true;
  $('retry-save').classList.add('hidden');
  $('submit').disabled = true;
  $('error').textContent = '';
  try {
    const {response, body} = await withDeadline(async signal => {
      const response = await fetch(pending.url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: pending.body,
        signal,
      });
      return {response, body: await response.json()};
    }, 'Timed out waiting for the save acknowledgement');
    if (state.pendingSave !== pending) return;
    if (!response.ok) {
      // The API validates before writing and reserves 400 for a definite
      // rejection. Other failures can have an unknown commit outcome.
      if (response.status === 400) {
        pending.rejected = true;
        discardRecoveryRecord();
        state.pendingSave = null;
        if (pending.mediaFailed) {
          clearAssignment();
          $('error').textContent = 'Assignment media stopped loading during the rejected save; reload before judging';
          $('retry-load').classList.remove('hidden');
          return;
        }
        setJudgmentEditable(true);
        $('submit').disabled = !state.assignment;
        $('error').textContent = body.error || 'Judgment was rejected; correct it and submit again';
        return;
      }
      throw new Error(body.error || 'Save was not confirmed');
    }
    if (!body || typeof body.annotation_id !== 'string') {
      throw new Error('Save acknowledgement was incomplete');
    }
    pending.acknowledged = true;
    discardRecoveryRecord();
    state.pendingSave = null;
    pending.form.reset();
    await loadNext();
  } catch (error) {
    if (state.pendingSave !== pending) return;
    $('error').textContent = pending.acknowledged
      ? `Save was confirmed but the browser recovery record could not clear (${error.message || 'storage error'}). Retry the same judgment before continuing.`
      : pending.rejected
        ? `Save was rejected without a write, but the browser recovery record could not clear (${error.message || 'storage error'}). Retry the same judgment before continuing.`
      : `Save status is unknown (${error.message || 'connection error'}). Retry the same judgment before continuing.`;
    $('retry-save').classList.remove('hidden');
  } finally {
    state.saveBusy = false;
  }
}

async function loadNext() {
  if (state.pendingSave) {
    $('error').textContent = 'Confirm the previous save before loading another assignment';
    return;
  }
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
    setJudgmentEditable(true);
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
      if (state.pendingSave) {
        state.pendingSave.mediaFailed = true;
        return;
      }
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
