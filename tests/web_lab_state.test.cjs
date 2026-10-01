const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const appSource = fs.readFileSync(path.join(__dirname, '..', 'ouro_eval_lab', 'web', 'app.js'), 'utf8');

function harness(replies, mediaModes = []) {
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
        replaceChildren() { this.children = []; },
        append(child) { this.children.push(child); },
        reset() { this.resetCount = (this.resetCount || 0) + 1; },
        setAttribute() {},
      });
    }
    return elements.get(id);
  }
  const context = vm.createContext({
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
      requests.push({url, method: options?.method || 'GET'});
      const reply = replies.shift();
      if (!reply) throw new Error('unexpected request');
      const result = typeof reply === 'function' ? await reply(options) : await reply;
      if (result instanceof Error) throw result;
      if (result.text) return result;
      return {ok: result.ok, json: async () => result.body};
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
  const submitEvent = target => ({target, preventDefault() {}});
  return {
    element,
    requests,
    replies,
    assignment: () => vm.runInContext('state.assignment', context),
    signIn: () => element('signin-form').listeners.submit(submitEvent(element('signin-form'))),
    submit: () => element('annotation-form').listeners.submit(submitEvent(element('annotation-form'))),
    retry: () => element('retry-load').listeners.click(),
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
