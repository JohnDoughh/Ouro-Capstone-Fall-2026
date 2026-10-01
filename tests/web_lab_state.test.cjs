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

const item = id => ({assignment_id: id, artifact_id: id, modality: 'image', mime_type: 'image/png', media_url: `/media/${id}`});

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
