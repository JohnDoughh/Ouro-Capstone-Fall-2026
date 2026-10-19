const state = {
  rater: null, assignment: null, loadEpoch: 0, pendingSave: null, saveBusy: false,
  study: 'annotation', playLimit: null, clip: null, clipAssignmentId: null,
  plays: 0, playing: false, unstartedPlay: false,
};
const $ = id => document.getElementById(id);
const REQUEST_DEADLINE_MS = 12000;
const PENDING_SAVE_KEY = 'ouro-eval-lab-pending-save-v1';
const MAX_SAVE_BYTES = 16384;
// The server runs one study. Each has its own endpoint and receipt field.
const STUDY_ENDPOINTS = {annotation: '/api/annotations/', intent: '/api/intent-responses/'};
const RECEIPT_KEYS = {annotation: 'annotation_id', intent: 'response_id'};
const INTENT_LABELS = {
  audience: 'who it is for', problem: 'the problem', product: 'the product',
  key_benefit: 'the main benefit', support: 'what backs it up',
  call_to_action: 'what it asks you to do', tone: 'the tone',
};

// Mirrors the server: a rater ID must never be a phone number.
const PHONE_LIKE = /(?<!\d)\d{3}[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)/;

function validRaterId(value) {
  const characters = [...value];
  return characters.length > 0 && characters.length <= 80 &&
    characters.every(character => /^[\p{L}\p{N}_-]$/u.test(character)) &&
    !PHONE_LIKE.test(value);
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
      typeof record.body !== 'string' || record.body.length > MAX_SAVE_BYTES ||
      !payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Session recovery record is invalid');
  }
  const query = `${record.assignmentId}?rater=${encodeURIComponent(record.rater)}`;
  record.study = Object.keys(STUDY_ENDPOINTS).find(study => record.url === STUDY_ENDPOINTS[study] + query);
  if (!record.study) throw new Error('Session recovery record is invalid');
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
  state.clip = null;
  state.clipAssignmentId = null;
  state.plays = 0;
  state.playing = false;
  state.unstartedPlay = false;
  $('play-row').classList.add('hidden');
  updatePlayControls();
}

function setJudgmentEditable(editable) {
  const form = $('annotation-form');
  for (const control of form.querySelectorAll('input, textarea')) {
    control.disabled = true;
  }
  if (!editable) return;
  // Only the active study's controls are enabled, so hidden required inputs
  // can never block a submission or travel with it.
  const active = `[data-study="${state.study}"]`;
  for (const control of form.querySelectorAll(`${active} input, ${active} textarea`)) {
    control.disabled = false;
  }
}

function showStudy(study) {
  state.study = study === 'intent' ? 'intent' : 'annotation';
  const intent = state.study === 'intent';
  $('annotation-fields').classList[intent ? 'add' : 'remove']('hidden');
  $('intent-fields').classList[intent ? 'remove' : 'add']('hidden');
  $('decision-kicker').textContent = intent ? 'Your independent recall' : 'Your independent judgment';
  $('decision-title').textContent = intent ? 'What was this ad trying to tell you?' : 'Should this artifact proceed?';
  $('submit').textContent = intent ? 'Submit answers' : 'Submit judgment';
}

function annotationBody(form) {
  const reason_codes = [...document.querySelectorAll('input[name=reason]:checked')].map(input => input.value);
  return {
    verdict: form.get('verdict'),
    confidence: Number(form.get('confidence')),
    severity: Number(form.get('severity')),
    defect_timestamps: String(form.get('defect_timestamps') || '').trim(),
    reason_codes,
    note: $('note').value,
  };
}

function intentBody(form) {
  if (state.clip && state.plays < 1) throw new Error('Play the clip before answering.');
  const components = {};
  for (const [field, label] of Object.entries(INTENT_LABELS)) {
    const recall = String(form.get(`${field}_recall`) || '').trim();
    const certainty = form.get(`${field}_certainty`);
    if (form.get(`${field}_could_not_tell`)) {
      if (recall) throw new Error(`Clear your answer or untick “Could not tell” for ${label}.`);
      components[field] = {recall: '', certainty: null, could_not_tell: true};
    } else {
      if (!recall || !certainty) {
        throw new Error(`Answer and rate how sure you are, or tick “Could not tell”, for ${label}.`);
      }
      components[field] = {recall, certainty: Number(certainty), could_not_tell: false};
    }
  }
  return {components, other_beats: String(form.get('other_beats') || '').trim(), play_count: state.plays};
}

function updatePlayControls() {
  const left = state.playLimit === null ? null : Math.max(state.playLimit - state.plays, 0);
  $('play-clip').disabled = !state.clip || state.playing || (left === 0 && !state.unstartedPlay);
  $('play-clip').textContent = state.plays ? 'Play again' : 'Play clip';
  $('plays-left').textContent = !state.clip ? ''
    : left === null ? `Played ${state.plays} times` : `${left} of ${state.playLimit} plays left`;
}

// Intent clips play only through this button, from the start, so every
// viewer gets the same counted exposure. There is no scrubbing or pausing.
// The server holds the count: it is restored on reload and recorded before
// each play, so re-entering an assignment never grants fresh plays.
function prepareClip(video, assignmentId, playsUsed) {
  state.clip = video;
  state.clipAssignmentId = assignmentId;
  state.plays = playsUsed;
  state.playing = false;
  state.unstartedPlay = false;
  video.addEventListener('ended', () => {
    if (state.clip !== video) return;
    state.playing = false;
    updatePlayControls();
  });
  video.addEventListener('contextmenu', event => event.preventDefault());
  $('play-row').classList.remove('hidden');
  updatePlayControls();
}

// A freeze is a known, final rejection: nothing was written and no retry can
// succeed. Unlike a lost acknowledgement or a 503, there is nothing to recover.
function showCollectionClosed(unsaved) {
  clearAssignment();
  $('error').textContent = '';
  $('retry-save').classList.add('hidden');
  $('retry-load').classList.add('hidden');
  $('progress').textContent = 'Collection closed';
  $('closed-unsaved').classList[unsaved ? 'remove' : 'add']('hidden');
  $('workspace').classList.add('hidden');
  $('closed').classList.remove('hidden');
}

async function recordPlay(clip) {
  const url = `/api/intent-plays/${state.clipAssignmentId}?rater=${encodeURIComponent(state.rater)}`;
  let reply;
  try {
    reply = await withDeadline(async signal => {
      const response = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        // Re-sending the same number after a lost reply replays, never double-counts.
        body: JSON.stringify({play_number: state.plays + 1}),
        signal,
      });
      return {response, body: await response.json()};
    }, 'Timed out recording the play');
  } catch (error) {
    if (state.clip === clip) $('error').textContent = `The play could not be recorded (${error.message || 'connection error'}); try again.`;
    return false;
  }
  if (state.clip !== clip) return false;
  const {response, body} = reply;
  if (response.status === 409 && body?.collection_closed === true) {
    showCollectionClosed(false);
    return false;
  }
  if (Number.isInteger(body?.plays_used)) state.plays = body.plays_used;
  if (!response.ok || !Number.isInteger(body?.plays_used)) {
    $('error').textContent = body?.error || 'The play could not be recorded; try again.';
    return false;
  }
  return true;
}

async function playClip() {
  const clip = state.clip;
  if (!clip || state.playing) return;
  if (!state.unstartedPlay && state.playLimit !== null && state.plays >= state.playLimit) return;
  state.playing = true;
  $('error').textContent = '';
  updatePlayControls();
  // Record the start first: the viewer never sees an exposure the server did not count.
  if (!state.unstartedPlay && !await recordPlay(clip)) {
    if (state.clip !== clip) return;
    state.playing = false;
    updatePlayControls();
    return;
  }
  if (state.clip !== clip) return;
  state.unstartedPlay = true;
  try {
    clip.currentTime = 0;
    await clip.play();
    if (state.clip !== clip) return;
    state.unstartedPlay = false;
  } catch {
    if (state.clip !== clip) return;
    state.playing = false;
    // The play is already counted, so the next press retries it without a new count.
    $('error').textContent = 'The clip could not start; press Play to try again.';
  }
  updatePlayControls();
}

$('signin-form').addEventListener('submit', async event => {
  event.preventDefault();
  const rater = $('rater').value.trim();
  if (!validRaterId(rater)) {
    $('signin-error').textContent = PHONE_LIKE.test(rater)
      ? 'Do not use a phone number. Use a pseudonymous rater ID such as rater-a.'
      : 'Use a pseudonymous rater ID of 1–80 letters, numbers, - or _.';
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
    showStudy(recovery.study);
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
$('play-clip').addEventListener('click', playClip);

$('annotation-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!state.assignment || state.pendingSave) return;
  $('error').textContent = '';
  $('submit').disabled = true;
  const form = new FormData(event.target);
  let body;
  try {
    body = state.study === 'intent' ? intentBody(form) : annotationBody(form);
  } catch (error) {
    // Nothing was frozen or sent; the viewer can correct the form.
    $('error').textContent = error.message;
    $('submit').disabled = false;
    return;
  }
  // Freeze these exact bytes before the first request. A lost acknowledgement
  // must never turn into a second, edited judgment for the same assignment.
  const pending = {
    assignmentId: state.assignment.assignment_id,
    url: `${STUDY_ENDPOINTS[state.study]}${state.assignment.assignment_id}?rater=${encodeURIComponent(state.rater)}`,
    body: JSON.stringify(body),
    study: state.study,
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
      // The API validates before writing and reserves 400 and a frozen
      // collection's 409 for definite no-write rejections. Any other failure
      // keeps the frozen judgment for an exact retry.
      if (response.status === 409 && body?.collection_closed === true) {
        pending.rejected = true;
        discardRecoveryRecord();
        state.pendingSave = null;
        showCollectionClosed(true);
        return;
      }
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
    if (!body || typeof body[RECEIPT_KEYS[pending.study]] !== 'string') {
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
    showStudy(body.study);
    state.playLimit = Number.isInteger(body.play_limit) ? body.play_limit : null;
    if (body.collection_closed === true) {
      showCollectionClosed(false);
      return;
    }
    if (!body.assignment) {
      $('workspace').classList.add('hidden');
      $('done').classList.remove('hidden');
      return;
    }
    await renderMedia(body.assignment, Number.isInteger(body.plays_used) ? body.plays_used : 0);
    if (state.loadEpoch !== loadEpoch) throw new Error('Assignment media load was interrupted');
    $('modality').textContent = body.assignment.modality;
    $('artifact-id').textContent = body.assignment.review_label || 'Review item';
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

async function renderMedia(item, playsUsed = 0) {
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
    const intent = state.study === 'intent';
    video.controls = !intent;
    video.playsInline = true;
    video.preload = intent ? 'auto' : 'metadata';
    video.setAttribute('aria-label', 'Synthetic video artifact to annotate');
    await waitForPlayableMedia(video, item, 'loadedmetadata');
    if (intent) prepareClip(video, item.assignment_id, playsUsed);
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
