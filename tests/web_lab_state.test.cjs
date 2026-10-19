const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const appSource = fs.readFileSync(path.join(__dirname, '..', 'ouro_eval_lab', 'web', 'app.js'), 'utf8');

function harness(replies, mediaModes = [], storage = {entries: new Map()}) {
  const elements = new Map();
  const requests = [];
  const timers = [];
  function element(id) {
    if (!elements.has(id)) {
      const classes = new Set();
      elements.set(id, {
        value: '', textContent: '', disabled: false, children: [], listeners: {},
        classList: {
          add: name => classes.add(name),
          remove: name => classes.delete(name),
          contains: name => classes.has(name),
        },
        addEventListener(name, handler) { this.listeners[name] = handler; },
        querySelectorAll() { return this.controls || []; },
        replaceChildren() { this.children = []; },
        append(child) { this.children.push(child); },
        reset() { this.resetCount = (this.resetCount || 0) + 1; },
        setAttribute() {},
      });
    }
    return elements.get(id);
  }
  const context = vm.createContext({
    sessionStorage: {
      getItem(key) {
        if (storage.failRead) throw new Error('storage read denied');
        return storage.entries.has(key) ? storage.entries.get(key) : null;
      },
      setItem(key, value) {
        if (storage.failWrite || (storage.failRecordWrite && !key.endsWith('-probe'))) {
          throw new Error('storage write denied');
        }
        storage.entries.set(key, String(value));
      },
      removeItem(key) {
        if (storage.failRemove) throw new Error('storage removal denied');
        storage.entries.delete(key);
      },
    },
    document: {
      getElementById: element,
      querySelectorAll: () => [],
      createElement: tag => {
        const listeners = new Map();
        const node = {
          tag, setAttribute() {}, removeAttribute() {}, load() {},
          play() { node.played = (node.played || 0) + 1; return Promise.resolve(); },
          addEventListener(name, callback) {
            if (!listeners.has(name)) listeners.set(name, new Set());
            listeners.get(name).add(callback);
          },
          removeEventListener(name, callback) { listeners.get(name)?.delete(callback); },
          emit(name) { for (const callback of [...(listeners.get(name) || [])]) callback(); },
        };
        Object.defineProperty(node, 'src', {set(value) {
          node.source = value;
          if (!['img', 'audio', 'video'].includes(tag)) return;
          const mode = mediaModes.shift() || 'ready';
          if (tag === 'img') node.decode = async () => {
            if (mode === 'decode-error') throw new Error('decode failed');
          };
          if (mode === 'pending') return;
          Promise.resolve().then(() => node.emit(mode === 'error' ? 'error' : tag === 'img' ? 'load' : 'loadedmetadata'));
        }});
        return node;
      },
    },
    FormData: class { constructor(form) { this.form = form; } get(name) { return this.form.fields[name]; } },
    fetch: async (url, options) => {
      requests.push({url, method: options?.method || 'GET', body: options?.body});
      const reply = replies.shift();
      if (!reply) throw new Error('unexpected request');
      const result = typeof reply === 'function' ? await reply(options) : await reply;
      if (result instanceof Error) throw result;
      if (result.text || result.json) return result;
      return {ok: result.ok, status: result.status, json: async () => result.body};
    },
    AbortController,
    setTimeout: callback => {
      const timer = {callback, active: true};
      timers.push(timer);
      return timer;
    },
    clearTimeout: timer => { if (timer) timer.active = false; },
    encodeURIComponent,
  });
  vm.runInContext(appSource, context, {filename: 'app.js'});
  element('rater').value = 'rater-a';
  element('annotation-form').fields = {
    verdict: 'HOLD', confidence: '4', severity: '2', defect_timestamps: '',
  };
  element('annotation-form').controls = Array.from({length: 4}, () => ({disabled: false}));
  const submitEvent = target => ({target, preventDefault() {}});
  return {
    element,
    requests,
    replies,
    storage,
    assignment: () => vm.runInContext('state.assignment', context),
    signIn: () => element('signin-form').listeners.submit(submitEvent(element('signin-form'))),
    submit: () => element('annotation-form').listeners.submit(submitEvent(element('annotation-form'))),
    retry: () => element('retry-load').listeners.click(),
    retrySave: () => element('retry-save').listeners.click(),
    expireTimeouts: () => {
      for (const timer of timers) {
        if (timer.active) {
          timer.active = false;
          timer.callback();
        }
      }
    },
  };
}

async function flushAsync() {
  for (let index = 0; index < 20; index++) await Promise.resolve();
}

function next(assignment, completed = 0) {
  return {ok: true, body: {assignment, progress: {completed, total: 2}}};
}

const item = id => ({assignment_id: id, review_label: 'Item 001', modality: 'image', mime_type: 'image/png', media_url: `/media/${id}`});

test('reviewer label is neutral and saves still use the original assignment', async () => {
  const lab = harness([
    next({...item('opaque-id'), artifact_id: 'SYN-ORBIT-CLEAN'}),
    {ok: true, body: {annotation_id: 'saved'}}, next(null, 1),
  ]);
  await lab.signIn();
  assert.equal(lab.element('artifact-id').textContent, 'Item 001');
  await lab.submit();
  const saved = lab.requests.find(request => request.method === 'POST');
  assert.equal(saved.url, '/api/annotations/opaque-id?rater=rater-a');
  assert.equal(saved.body.includes('SYN-ORBIT-CLEAN'), false);
});

test('missing presentation label never falls back to an answer-revealing source ID', async () => {
  const lab = harness([next({...item('opaque-id'), review_label: undefined, artifact_id: 'SYN-ORBIT-CLEAN'})]);
  await lab.signIn();
  assert.equal(lab.element('artifact-id').textContent, 'Review item');
});

test('failed next load after save cannot resubmit the completed assignment', async () => {
  const lab = harness([next(item('a')), {ok: true, body: {annotation_id: 'saved'}},
    {ok: false, body: {error: 'next unavailable'}}]);
  await lab.signIn();
  assert.equal(lab.assignment().assignment_id, 'a');
  assert.equal(lab.element('submit').disabled, false);
  await lab.submit();
  assert.equal(lab.assignment(), null);
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.element('media').children.length, 0);
  assert.equal(lab.element('retry-load').classList.contains('hidden'), false);
  await lab.submit();
  assert.equal(lab.requests.filter(request => request.method === 'POST').length, 1);

  lab.replies.push(next(item('b'), 1));
  await lab.retry();
  assert.equal(lab.assignment().assignment_id, 'b');
  assert.equal(lab.element('submit').disabled, false);
  assert.equal(lab.element('retry-load').classList.contains('hidden'), true);
});

test('ambiguous save freezes the exact judgment and only retries those bytes', async () => {
  let resolveLateSave;
  const firstSave = new Promise(resolve => { resolveLateSave = resolve; });
  const lab = harness([
    next(item('a')),
    firstSave,
    {ok: true, body: {annotation_id: 'saved-a', replayed: true}},
    next(item('b'), 1),
  ]);
  await lab.signIn();
  const initialSave = lab.submit();
  await flushAsync();
  assert.equal(lab.requests.filter(request => request.method === 'POST').length, 1);
  assert.equal(lab.element('submit').disabled, true);
  assert.ok(lab.element('annotation-form').controls.every(control => control.disabled));

  lab.expireTimeouts();
  await initialSave;
  assert.equal(lab.assignment().assignment_id, 'a');
  assert.equal(lab.element('retry-save').classList.contains('hidden'), false);
  assert.equal(lab.element('submit').disabled, true);
  assert.ok(lab.element('annotation-form').controls.every(control => control.disabled));

  // Even a synthetic value change cannot produce an edited POST while the
  // original outcome is unknown. Loading a different assignment is held too.
  lab.element('annotation-form').fields.verdict = 'PASS';
  await lab.submit();
  await lab.retry();
  assert.equal(lab.requests.filter(request => request.method === 'POST').length, 1);
  assert.equal(lab.requests.filter(request => request.method === 'GET').length, 1);

  await lab.retrySave();
  const saves = lab.requests.filter(request => request.method === 'POST');
  assert.equal(saves.length, 2);
  assert.equal(saves[1].url, saves[0].url);
  assert.equal(saves[1].body, saves[0].body);
  assert.equal(JSON.parse(saves[1].body).verdict, 'HOLD');
  assert.equal(lab.assignment().assignment_id, 'b');
  assert.equal(lab.element('submit').disabled, false);
  assert.ok(lab.element('annotation-form').controls.every(control => !control.disabled));
  assert.equal(lab.element('annotation-form').resetCount, 1);

  // The first transport's eventual response cannot rewind the new assignment.
  resolveLateSave({ok: false, status: 409, body: {error: 'late conflict'}});
  await flushAsync();
  assert.equal(lab.assignment().assignment_id, 'b');
  assert.equal(lab.element('annotation-form').resetCount, 1);
});

test('save deadline covers response JSON, not only the POST transport', async () => {
  const lab = harness([
    next(item('a')),
    {ok: true, json: () => new Promise(() => {})},
  ]);
  await lab.signIn();
  const saving = lab.submit();
  await flushAsync();
  lab.expireTimeouts();
  await saving;
  assert.equal(lab.assignment().assignment_id, 'a');
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.element('retry-save').classList.contains('hidden'), false);
});

test('rapid retry clicks cannot dispatch concurrent saves', async () => {
  const lab = harness([
    next(item('a')),
    new Promise(() => {}),
    new Promise(() => {}),
  ]);
  await lab.signIn();
  const original = lab.submit();
  await flushAsync();
  lab.expireTimeouts();
  await original;
  const retry = lab.retrySave();
  await flushAsync();
  await lab.retrySave();
  assert.equal(lab.requests.filter(request => request.method === 'POST').length, 2);
  lab.expireTimeouts();
  await retry;
  assert.equal(lab.element('retry-save').classList.contains('hidden'), false);
  assert.equal(lab.element('submit').disabled, true);
});

test('reload restores an uncertain save for the same rater and retries exact bytes', async () => {
  const storage = {entries: new Map()};
  let resolveLateSave;
  const firstSave = new Promise(resolve => { resolveLateSave = resolve; });
  const beforeReload = harness([next(item('a')), firstSave], [], storage);
  beforeReload.element('rater').value = 'rater-é';
  await beforeReload.signIn();
  const original = beforeReload.submit();
  await flushAsync();
  const originalRequest = beforeReload.requests.find(request => request.method === 'POST');
  assert.ok(storage.entries.has('ouro-eval-lab-pending-save-v1'));
  beforeReload.expireTimeouts();
  await original;

  // A full/now-write-protected store must still allow recovery of an already
  // persisted judgment; replay does not create a new local record.
  storage.failWrite = true;
  const afterReload = harness([
    {ok: true, body: {annotation_id: 'saved-a', replayed: true}},
    next(item('b'), 1),
  ], [], storage);
  afterReload.element('rater').value = 'rater-é';
  await afterReload.signIn();
  assert.equal(afterReload.requests.length, 0);
  assert.equal(afterReload.assignment(), null);
  assert.equal(afterReload.element('submit').disabled, true);
  assert.ok(afterReload.element('annotation-form').controls.every(control => control.disabled));
  assert.equal(afterReload.element('retry-save').classList.contains('hidden'), false);
  await afterReload.submit();
  await afterReload.retry();
  assert.equal(afterReload.requests.length, 0);

  await afterReload.retrySave();
  const replay = afterReload.requests.find(request => request.method === 'POST');
  assert.equal(replay.url, originalRequest.url);
  assert.match(replay.url, /rater=rater-%C3%A9/);
  assert.equal(replay.body, originalRequest.body);
  assert.equal(afterReload.assignment().assignment_id, 'b');
  assert.equal(storage.entries.has('ouro-eval-lab-pending-save-v1'), false);

  resolveLateSave({ok: true, body: {annotation_id: 'saved-a'}});
  await flushAsync();
  assert.equal(afterReload.assignment().assignment_id, 'b');
});

test('restored save rejected without write must reload media before editing', async () => {
  const storage = {entries: new Map()};
  const beforeReload = harness([next(item('a')), new Promise(() => {})], [], storage);
  await beforeReload.signIn();
  const original = beforeReload.submit();
  await flushAsync();
  beforeReload.expireTimeouts();
  await original;

  const afterReload = harness([
    {ok: false, status: 400, body: {error: 'invalid judgment'}},
    next(item('a')),
  ], [], storage);
  await afterReload.signIn();
  await afterReload.retrySave();
  assert.equal(storage.entries.has('ouro-eval-lab-pending-save-v1'), false);
  assert.equal(afterReload.assignment(), null);
  assert.equal(afterReload.element('submit').disabled, true);
  assert.equal(afterReload.element('retry-load').classList.contains('hidden'), false);
  assert.equal(afterReload.requests.filter(request => request.method === 'GET').length, 0);
  await afterReload.retry();
  assert.equal(afterReload.assignment().assignment_id, 'a');
});

test('mismatched rater and unavailable recovery storage fail closed', async () => {
  const storage = {entries: new Map()};
  const beforeReload = harness([next(item('a')), new Promise(() => {})], [], storage);
  await beforeReload.signIn();
  const original = beforeReload.submit();
  await flushAsync();
  beforeReload.expireTimeouts();
  await original;

  const wrongRater = harness([], [], storage);
  wrongRater.element('rater').value = 'other-rater';
  await wrongRater.signIn();
  assert.equal(wrongRater.requests.length, 0);
  assert.match(wrongRater.element('signin-error').textContent, /unfinished save/);

  const unavailable = harness([], [], {entries: new Map(), failWrite: true});
  await unavailable.signIn();
  assert.equal(unavailable.requests.length, 0);
  assert.match(unavailable.element('signin-error').textContent, /cannot safely recover/);

  const corrupt = harness([], [], {entries: new Map([['ouro-eval-lab-pending-save-v1', '{broken']])});
  await corrupt.signIn();
  assert.equal(corrupt.requests.length, 0);
  assert.match(corrupt.element('signin-error').textContent, /cannot safely recover/);

  const cannotPersist = harness([next(item('a'))], [], {entries: new Map(), failRecordWrite: true});
  await cannotPersist.signIn();
  await cannotPersist.submit();
  assert.equal(cannotPersist.requests.filter(request => request.method === 'POST').length, 0);
  assert.equal(cannotPersist.element('submit').disabled, true);
  assert.match(cannotPersist.element('error').textContent, /No save was sent/);
});

test('confirmed save cannot advance until its local recovery record clears', async () => {
  const storage = {entries: new Map(), failRemove: false};
  const lab = harness([
    next(item('a')),
    {ok: true, body: {annotation_id: 'saved-a'}},
    {ok: true, body: {annotation_id: 'saved-a', replayed: true}},
    next(item('b'), 1),
  ], [], storage);
  await lab.signIn();
  storage.failRemove = true;
  await lab.submit();
  assert.equal(lab.assignment().assignment_id, 'a');
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.element('retry-save').classList.contains('hidden'), false);
  assert.match(lab.element('error').textContent, /Save was confirmed/);
  assert.equal(lab.requests.filter(request => request.method === 'GET').length, 1);
  storage.failRemove = false;
  await lab.retrySave();
  assert.equal(lab.assignment().assignment_id, 'b');
  assert.equal(storage.entries.has('ouro-eval-lab-pending-save-v1'), false);
});

test('explicit no-write validation rejection permits correction, conflict does not', async () => {
  const lab = harness([
    next(item('a')),
    {ok: false, status: 400, body: {error: 'invalid severity'}},
    {ok: false, status: 409, body: {error: 'different saved judgment'}},
  ]);
  await lab.signIn();
  await lab.submit();
  assert.equal(lab.element('submit').disabled, false);
  assert.ok(lab.element('annotation-form').controls.every(control => !control.disabled));
  assert.equal(lab.element('retry-save').classList.contains('hidden'), true);
  await lab.submit();
  assert.equal(lab.element('submit').disabled, true);
  assert.ok(lab.element('annotation-form').controls.every(control => control.disabled));
  assert.equal(lab.element('retry-save').classList.contains('hidden'), false);
});

for (const [modality, mime, readyEvent] of [
  ['image', 'image/png', 'load'],
  ['audio', 'audio/wav', 'loadedmetadata'],
  ['video', 'video/mp4', 'loadedmetadata'],
]) {
  test(`${modality} failure during a rejected save requires a fresh load`, async () => {
    let rejectSave;
    const delayedRejection = new Promise(resolve => { rejectSave = resolve; });
    const mediaItem = {...item(`${modality}-a`), modality, mime_type: mime};
    const lab = harness([next(mediaItem), delayedRejection, next(item('b'))]);
    await lab.signIn();
    assert.equal(lab.assignment().assignment_id, mediaItem.assignment_id);
    const saving = lab.submit();
    await flushAsync();
    lab.element('media').children[0].emit('error');
    assert.equal(lab.element('submit').disabled, true);
    assert.ok(lab.element('annotation-form').controls.every(control => control.disabled));

    rejectSave({ok: false, status: 400, body: {error: 'invalid judgment'}});
    await saving;
    assert.equal(lab.assignment(), null);
    assert.equal(lab.element('submit').disabled, true);
    assert.ok(lab.element('annotation-form').controls.every(control => control.disabled));
    assert.equal(lab.element('retry-load').classList.contains('hidden'), false);
    assert.equal(lab.element('retry-save').classList.contains('hidden'), true);
    assert.equal(lab.element('media').children.length, 0);
    assert.equal(lab.element('annotation-form').resetCount || 0, 0);
    assert.equal(lab.requests.filter(request => request.method === 'GET').length, 1);

    await lab.retry();
    assert.equal(lab.assignment().assignment_id, 'b');
    assert.equal(lab.element('submit').disabled, false);
  });
}

test('first load network failure stays held and can be retried', async () => {
  const lab = harness([new Error('network unavailable')]);
  await lab.signIn();
  assert.equal(lab.assignment(), null);
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.element('retry-load').classList.contains('hidden'), false);
  lab.replies.push(next(item('a')));
  await lab.retry();
  assert.equal(lab.assignment().assignment_id, 'a');
});

test('completed queue never leaves a submit-ready assignment', async () => {
  const lab = harness([next(null, 2)]);
  await lab.signIn();
  assert.equal(lab.assignment(), null);
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.element('workspace').classList.contains('hidden'), true);
  assert.equal(lab.element('done').classList.contains('hidden'), false);
});

test('pending text media times out to retry and cannot restore a stale assignment', async () => {
  let resolveLateMedia;
  const pendingMedia = new Promise(resolve => { resolveLateMedia = resolve; });
  const textItem = {...item('text-a'), modality: 'text', mime_type: 'text/plain'};
  const lab = harness([next(textItem), pendingMedia]);
  const firstLoad = lab.signIn();
  await flushAsync();
  assert.equal(lab.requests.length, 2);
  assert.equal(lab.assignment(), null);
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.element('retry-load').classList.contains('hidden'), true);

  lab.expireTimeouts();
  await firstLoad;
  assert.equal(lab.assignment(), null);
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.element('retry-load').classList.contains('hidden'), false);

  resolveLateMedia({ok: true, text: async () => 'late synthetic text'});
  await flushAsync();
  assert.equal(lab.element('media').children.length, 0);
  assert.equal(lab.assignment(), null);

  lab.replies.push(next(item('b')));
  await lab.retry();
  assert.equal(lab.assignment().assignment_id, 'b');
  assert.equal(lab.element('submit').disabled, false);
});

test('pending next request times out to retry without enabling submission', async () => {
  const lab = harness([new Promise(() => {})]);
  const firstLoad = lab.signIn();
  await flushAsync();
  assert.equal(lab.requests.length, 1);
  lab.expireTimeouts();
  await firstLoad;
  assert.equal(lab.assignment(), null);
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.element('retry-load').classList.contains('hidden'), false);
});

for (const [modality, mime] of [
  ['image', 'image/png'], ['audio', 'audio/wav'], ['video', 'video/mp4'],
]) {
  test(`${modality} media must load before Submit is enabled`, async () => {
    const mediaItem = {...item(`${modality}-a`), modality, mime_type: mime};
    const lab = harness([next(mediaItem)], ['pending']);
    const firstLoad = lab.signIn();
    await flushAsync();
    assert.equal(lab.assignment(), null);
    assert.equal(lab.element('submit').disabled, true);
    const node = lab.element('media').children[0];
    assert.equal(node.source, mediaItem.media_url);
    node.emit(modality === 'image' ? 'load' : 'loadedmetadata');
    await firstLoad;
    assert.equal(lab.assignment().assignment_id, mediaItem.assignment_id);
    assert.equal(lab.element('submit').disabled, false);
  });

  test(`${modality} media error remains held and offers retry`, async () => {
    const mediaItem = {...item(`${modality}-bad`), modality, mime_type: mime};
    const lab = harness([next(mediaItem)], ['error']);
    await lab.signIn();
    assert.equal(lab.assignment(), null);
    assert.equal(lab.element('submit').disabled, true);
    assert.equal(lab.element('retry-load').classList.contains('hidden'), false);
  });
}

test('late playable-media events cannot revive a timed-out assignment', async () => {
  const mediaItem = {...item('video-pending'), modality: 'video', mime_type: 'video/mp4'};
  const lab = harness([next(mediaItem)], ['pending']);
  const firstLoad = lab.signIn();
  await flushAsync();
  const oldNode = lab.element('media').children[0];
  lab.expireTimeouts();
  await firstLoad;
  oldNode.emit('loadedmetadata');
  await flushAsync();
  assert.equal(lab.assignment(), null);
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.element('retry-load').classList.contains('hidden'), false);
});

test('image decode failure leaves the assignment held', async () => {
  const lab = harness([next(item('image-bad'))], ['decode-error']);
  await lab.signIn();
  assert.equal(lab.assignment(), null);
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.element('retry-load').classList.contains('hidden'), false);
});

test('playback error after metadata revokes the current assignment only', async () => {
  const mediaItem = {...item('video-a'), modality: 'video', mime_type: 'video/mp4'};
  const lab = harness([next(mediaItem)]);
  await lab.signIn();
  assert.equal(lab.assignment().assignment_id, mediaItem.assignment_id);
  lab.element('media').children[0].emit('error');
  assert.equal(lab.assignment(), null);
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.element('retry-load').classList.contains('hidden'), false);
});

test('an older next response cannot replace a newer loaded assignment', async () => {
  let resolveOld;
  const oldResponse = new Promise(resolve => { resolveOld = resolve; });
  const lab = harness([oldResponse, next(item('new'))]);
  const firstLoad = lab.signIn();
  await flushAsync();
  await lab.retry();
  assert.equal(lab.assignment().assignment_id, 'new');
  resolveOld(next(item('old')));
  await firstLoad;
  assert.equal(lab.assignment().assignment_id, 'new');
  assert.equal(lab.element('submit').disabled, false);
});

test('an older media failure cannot clear a newer loaded assignment', async () => {
  const oldItem = {...item('old-video'), modality: 'video', mime_type: 'video/mp4'};
  const lab = harness([next(oldItem), next(item('new'))], ['pending']);
  const firstLoad = lab.signIn();
  await flushAsync();
  const oldNode = lab.element('media').children[0];
  await lab.retry();
  assert.equal(lab.assignment().assignment_id, 'new');
  oldNode.emit('error');
  await firstLoad;
  assert.equal(lab.assignment().assignment_id, 'new');
  assert.equal(lab.element('submit').disabled, false);
});

test('a phone number is refused as a rater ID before any request', async () => {
  for (const rater of ['305-555-0100', '3055550100', 'rater_3055550100']) {
    const lab = harness([]);
    lab.element('rater').value = rater;
    await lab.signIn();
    assert.equal(lab.requests.length, 0);
    assert.match(lab.element('signin-error').textContent, /Do not use a phone number/);
  }
  const lab = harness([next(item('a'))]);
  lab.element('rater').value = 'viewer-20261014';
  await lab.signIn();
  assert.equal(lab.assignment().assignment_id, 'a');
});

// Team C intent study (Stage 1). All answers below are synthetic test data.
const INTENT_FIELDS = ['audience', 'problem', 'product', 'key_benefit', 'support', 'call_to_action', 'tone'];
const clip = id => ({...item(id), modality: 'video', mime_type: 'video/mp4'});

function intentNext(assignment, completed = 0, playsUsed = 0) {
  return {ok: true, body: {
    assignment, progress: {completed, total: 4}, study: 'intent', play_limit: 2,
    plays_used: assignment ? playsUsed : null,
  }};
}

// The server's receipt for a recorded play start.
const played = (n, replayed = false) => ({ok: true, status: replayed ? 200 : 201, body: {
  play_id: `play-${n}`, play_number: n, plays_used: n, ...(replayed ? {replayed: true} : {}),
}});
const responsePosts = lab => lab.requests.filter(request => request.url.startsWith('/api/intent-responses/'));
const playPosts = lab => lab.requests.filter(request => request.url.startsWith('/api/intent-plays/'));

function fillIntent(lab, overrides = {}) {
  const fields = {other_beats: ''};
  for (const field of INTENT_FIELDS) {
    fields[`${field}_recall`] = `Synthetic ${field}`;
    fields[`${field}_certainty`] = '3';
  }
  fields.tone_recall = '';
  fields.tone_certainty = null;
  fields.tone_could_not_tell = '1';
  lab.element('annotation-form').fields = {...fields, ...overrides};
}

async function watch(lab) {
  await lab.element('play-clip').listeners.click();
  lab.element('media').children[0].emit('ended');
}

test('intent study plays a limited clip and posts recall to its own endpoint', async () => {
  const lab = harness([
    intentNext(clip('a')),
    played(1), played(2),
    {ok: true, body: {response_id: 'response-a', completed_at: 'synthetic'}},
    intentNext(null, 1),
  ]);
  await lab.signIn();
  assert.equal(lab.element('intent-fields').classList.contains('hidden'), false);
  assert.equal(lab.element('annotation-fields').classList.contains('hidden'), true);
  assert.equal(lab.element('decision-title').textContent, 'What was this ad trying to tell you?');
  const video = lab.element('media').children[0];
  assert.equal(video.controls, false);
  assert.equal(lab.element('play-row').classList.contains('hidden'), false);
  assert.equal(lab.element('plays-left').textContent, '2 of 2 plays left');

  fillIntent(lab);
  await lab.submit();
  assert.equal(responsePosts(lab).length, 0);
  assert.match(lab.element('error').textContent, /Play the clip/);
  assert.equal(lab.element('submit').disabled, false);

  await lab.element('play-clip').listeners.click();
  assert.equal(lab.element('play-clip').disabled, true);
  video.emit('ended');
  assert.equal(lab.element('play-clip').disabled, false);
  await watch(lab);
  assert.equal(lab.element('play-clip').disabled, true);
  assert.equal(lab.element('plays-left').textContent, '0 of 2 plays left');
  await lab.element('play-clip').listeners.click();
  assert.equal(video.played, 2);
  assert.deepEqual(playPosts(lab).map(request => [request.url, JSON.parse(request.body)]), [
    ['/api/intent-plays/a?rater=rater-a', {play_number: 1}],
    ['/api/intent-plays/a?rater=rater-a', {play_number: 2}],
  ]);

  await lab.submit();
  const saves = responsePosts(lab);
  assert.equal(saves.length, 1);
  assert.equal(saves[0].url, '/api/intent-responses/a?rater=rater-a');
  const body = JSON.parse(saves[0].body);
  assert.deepEqual(Object.keys(body).sort(), ['components', 'other_beats', 'play_count']);
  assert.equal(body.play_count, 2);
  assert.deepEqual(Object.keys(body.components), INTENT_FIELDS);
  assert.deepEqual(body.components.support, {recall: 'Synthetic support', certainty: 3, could_not_tell: false});
  assert.deepEqual(body.components.tone, {recall: '', certainty: null, could_not_tell: true});
  assert.equal(lab.element('done').classList.contains('hidden'), false);
});

test('incomplete or contradictory intent answers stay local and send nothing', async () => {
  const lab = harness([intentNext(clip('a')), played(1)]);
  await lab.signIn();
  await watch(lab);
  for (const [overrides, message] of [
    [{tone_recall: 'calm'}, /untick “Could not tell” for the tone/],
    [{support_certainty: null}, /rate how sure you are.*what backs it up/],
    [{product_recall: '   '}, /rate how sure you are.*the product/],
  ]) {
    fillIntent(lab, overrides);
    await lab.submit();
    assert.match(lab.element('error').textContent, message);
    assert.equal(lab.element('submit').disabled, false);
  }
  assert.equal(responsePosts(lab).length, 0);
  assert.equal(lab.storage.entries.has('ouro-eval-lab-pending-save-v1'), false);
});

test('interrupted intent save recovers in intent mode with the same bytes', async () => {
  const storage = {entries: new Map()};
  const beforeReload = harness([intentNext(clip('a')), played(1), new Promise(() => {})], [], storage);
  await beforeReload.signIn();
  await watch(beforeReload);
  fillIntent(beforeReload);
  const original = beforeReload.submit();
  await flushAsync();
  const [originalRequest] = responsePosts(beforeReload);
  beforeReload.expireTimeouts();
  await original;

  const afterReload = harness([
    {ok: true, body: {response_id: 'response-a', replayed: true}},
    intentNext(clip('b'), 1),
  ], [], storage);
  await afterReload.signIn();
  assert.equal(afterReload.requests.length, 0);
  assert.equal(afterReload.element('intent-fields').classList.contains('hidden'), false);
  await afterReload.retrySave();
  const [replay] = responsePosts(afterReload);
  assert.equal(replay.url, originalRequest.url);
  assert.equal(replay.body, originalRequest.body);
  assert.equal(afterReload.assignment().assignment_id, 'b');
  assert.equal(storage.entries.has('ouro-eval-lab-pending-save-v1'), false);
});

test('an annotation receipt never confirms an intent save', async () => {
  const lab = harness([intentNext(clip('a')), played(1), {ok: true, body: {annotation_id: 'wrong-kind'}}]);
  await lab.signIn();
  await watch(lab);
  fillIntent(lab);
  await lab.submit();
  assert.equal(lab.assignment().assignment_id, 'a');
  assert.match(lab.element('error').textContent, /Save status is unknown/);
  assert.equal(lab.element('retry-save').classList.contains('hidden'), false);
});

test('reload restores the durable play count instead of granting fresh plays', async () => {
  // Reviewer repro: exhaust both plays, reload, sign in again as the same rater.
  const before = harness([intentNext(clip('a')), played(1), played(2)]);
  await before.signIn();
  await watch(before);
  await watch(before);
  assert.equal(before.element('plays-left').textContent, '0 of 2 plays left');

  const after = harness([
    intentNext(clip('a'), 0, 2),
    {ok: true, body: {response_id: 'response-a'}},
    intentNext(null, 1),
  ]);
  await after.signIn();
  const video = after.element('media').children[0];
  assert.equal(after.element('plays-left').textContent, '0 of 2 plays left');
  assert.equal(after.element('play-clip').disabled, true);
  assert.equal(after.element('play-clip').textContent, 'Play again');
  await after.element('play-clip').listeners.click();
  assert.equal(video.played, undefined);
  assert.equal(playPosts(after).length, 0);

  // The saved response reports every play that started, across both page loads.
  fillIntent(after);
  await after.submit();
  assert.equal(JSON.parse(responsePosts(after)[0].body).play_count, 2);
});

test('a partly used clip resumes at the next server play number', async () => {
  const lab = harness([intentNext(clip('a'), 0, 1), played(2)]);
  await lab.signIn();
  assert.equal(lab.element('plays-left').textContent, '1 of 2 plays left');
  await watch(lab);
  assert.deepEqual(JSON.parse(playPosts(lab)[0].body), {play_number: 2});
  assert.equal(lab.element('plays-left').textContent, '0 of 2 plays left');
});

test('a lost play receipt never plays unrecorded and retries the same play number', async () => {
  const lab = harness([intentNext(clip('a')), new Error('network unavailable'), played(1, true)]);
  await lab.signIn();
  const video = lab.element('media').children[0];
  await lab.element('play-clip').listeners.click();
  assert.equal(video.played, undefined);
  assert.match(lab.element('error').textContent, /could not be recorded/);
  assert.equal(lab.element('play-clip').disabled, false);
  assert.equal(lab.element('plays-left').textContent, '2 of 2 plays left');

  await lab.element('play-clip').listeners.click();
  assert.equal(video.played, 1);
  assert.deepEqual(playPosts(lab).map(request => JSON.parse(request.body).play_number), [1, 1]);
  assert.equal(lab.element('plays-left').textContent, '1 of 2 plays left');
});

test('a server play refusal adopts the durable count and does not play', async () => {
  const lab = harness([
    intentNext(clip('a')),
    {ok: false, status: 409, body: {error: 'play limit of 2 reached', plays_used: 2}},
  ]);
  await lab.signIn();
  const video = lab.element('media').children[0];
  await lab.element('play-clip').listeners.click();
  assert.equal(video.played, undefined);
  assert.match(lab.element('error').textContent, /play limit of 2 reached/);
  assert.equal(lab.element('plays-left').textContent, '0 of 2 plays left');
  assert.equal(lab.element('play-clip').disabled, true);
});

test('a counted play that fails to start retries without a second count', async () => {
  const lab = harness([intentNext(clip('a')), played(1)]);
  await lab.signIn();
  const video = lab.element('media').children[0];
  const play = video.play;
  video.play = () => Promise.reject(new Error('autoplay blocked'));
  await lab.element('play-clip').listeners.click();
  assert.match(lab.element('error').textContent, /could not start/);
  assert.equal(lab.element('play-clip').disabled, false);
  video.play = play;
  await lab.element('play-clip').listeners.click();
  assert.equal(video.played, 1);
  assert.equal(playPosts(lab).length, 1);
  assert.equal(lab.element('plays-left').textContent, '1 of 2 plays left');
});

const closedReply = {ok: false, status: 409, body: {
  error: 'intent responses are frozen for reveal; collection is closed', collection_closed: true,
}};

function assertClosed(lab, {unsaved}) {
  assert.equal(lab.element('closed').classList.contains('hidden'), false);
  assert.equal(lab.element('closed-unsaved').classList.contains('hidden'), !unsaved);
  assert.equal(lab.element('workspace').classList.contains('hidden'), true);
  assert.equal(lab.element('retry-save').classList.contains('hidden'), true);
  assert.equal(lab.element('retry-load').classList.contains('hidden'), true);
  assert.doesNotMatch(lab.element('error').textContent, /Save status is unknown/);
  assert.equal(lab.element('error').textContent, '');
  assert.equal(lab.assignment(), null);
  assert.equal(lab.element('submit').disabled, true);
  assert.equal(lab.storage.entries.has('ouro-eval-lab-pending-save-v1'), false);
}

test('a save refused by a frozen collection is a final closed state, not an unknown one', async () => {
  // Reviewer repro: after a valid freeze, submit the next open assignment.
  const lab = harness([intentNext(clip('b'), 1), played(1), closedReply]);
  await lab.signIn();
  await watch(lab);
  fillIntent(lab);
  await lab.submit();
  assertClosed(lab, {unsaved: true});
  await lab.retrySave();
  await lab.submit();
  assert.equal(responsePosts(lab).length, 1);
});

test('a conflicting 409 without the closed flag still holds the frozen judgment', async () => {
  const lab = harness([
    intentNext(clip('a')), played(1),
    {ok: false, status: 409, body: {error: 'assignment already completed with a different response'}},
  ]);
  lab.element('closed').classList.add('hidden');  // as in index.html
  await lab.signIn();
  await watch(lab);
  fillIntent(lab);
  await lab.submit();
  assert.equal(lab.element('closed').classList.contains('hidden'), true);
  assert.equal(lab.element('retry-save').classList.contains('hidden'), false);
  assert.equal(lab.storage.entries.has('ouro-eval-lab-pending-save-v1'), true);
});

test('a recovered save that meets a freeze clears recovery and closes', async () => {
  const storage = {entries: new Map()};
  const beforeReload = harness([intentNext(clip('a')), played(1), new Promise(() => {})], [], storage);
  await beforeReload.signIn();
  await watch(beforeReload);
  fillIntent(beforeReload);
  const original = beforeReload.submit();
  await flushAsync();
  beforeReload.expireTimeouts();
  await original;
  assert.match(beforeReload.element('error').textContent, /Save status is unknown/);

  const afterReload = harness([closedReply], [], storage);
  await afterReload.signIn();
  await afterReload.retrySave();
  assertClosed(afterReload, {unsaved: true});
});

test('an exact retry confirmed after the freeze still advances normally', async () => {
  const lab = harness([
    intentNext(clip('a')), played(1), new Promise(() => {}),
    {ok: true, status: 200, body: {response_id: 'response-a', replayed: true}},
    {ok: true, body: {assignment: null, progress: {completed: 1, total: 4}, study: 'intent',
      play_limit: 2, plays_used: null, collection_closed: true}},
  ]);
  await lab.signIn();
  await watch(lab);
  fillIntent(lab);
  const original = lab.submit();
  await flushAsync();
  lab.expireTimeouts();
  await original;
  await lab.retrySave();
  assertClosed(lab, {unsaved: false});
  assert.equal(responsePosts(lab).length, 2);
});

test('loading after the freeze shows the closed state instead of a clip', async () => {
  const lab = harness([{ok: true, body: {
    assignment: null, progress: {completed: 1, total: 4}, study: 'intent',
    play_limit: 2, plays_used: null, collection_closed: true,
  }}]);
  lab.element('done').classList.add('hidden');  // as in index.html
  await lab.signIn();
  assertClosed(lab, {unsaved: false});
  assert.equal(lab.element('done').classList.contains('hidden'), true);
  assert.equal(lab.element('media').children.length, 0);
});

test('a play refused by a frozen collection closes without playing', async () => {
  const lab = harness([intentNext(clip('a')), {...closedReply, body: {...closedReply.body, plays_used: 0}}]);
  await lab.signIn();
  const video = lab.element('media').children[0];
  await lab.element('play-clip').listeners.click();
  assert.equal(video.played, undefined);
  assertClosed(lab, {unsaved: false});
});
