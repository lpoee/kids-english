const ASSET_VERSION = '4';

export function createStorySession(story) {
  const turns = new Map(story.turns.map(turn => [turn.id, turn]));
  let currentId = story.start;

  function current() {
    const turn = turns.get(currentId);
    if (!turn) throw new Error(`Unknown turn: ${currentId}`);
    return turn;
  }

  function moveTo(nextId) {
    if (!turns.has(nextId)) throw new Error(`Unknown turn: ${nextId}`);
    currentId = nextId;
    return current();
  }

  return {
    current,
    choices() {
      return current().choice?.options ?? [];
    },
    advance() {
      const nextId = current().next;
      if (!nextId) throw new Error('Story is complete');
      return moveTo(nextId);
    },
    choose(label) {
      const option = this.choices().find(candidate => candidate.label === label);
      if (!option) throw new Error(`Unknown choice: ${label}`);
      return moveTo(option.next);
    },
    isComplete() {
      const turn = current();
      return turn.next === null && !turn.choice;
    },
    restart() {
      currentId = story.start;
      return current();
    },
  };
}


export async function mountSocialPlayer({ dataUrl = `data/social_dialogues.json?v=${ASSET_VERSION}` } = {}) {
  const byId = id => document.getElementById(id);
  const response = await fetch(dataUrl);
  if (!response.ok) throw new Error('Unable to load social stories');
  const documentData = await response.json();
  const stories = documentData.stories;
  let storyIndex = 0;
  let session = createStorySession(stories[storyIndex]);
  let playbackId = 0;
  const storySelect = byId('social-story-select');
  const audio = byId('social-audio');
  const video = byId('social-video');

  stories.forEach((story, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = `${index + 1}. ${story.title}`;
    storySelect.append(option);
  });

  function stopAudio() {
    playbackId += 1;
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
  }

  function playCurrent() {
    const turn = session.current();
    if (!turn.audio) return;
    stopAudio();
    const acceptedId = playbackId;
    audio.src = `${turn.audio}?v=${ASSET_VERSION}`;
    audio.onended = () => {
      if (acceptedId === playbackId) renderActions();
    };
    audio.play().catch(error => console.warn('social audio blocked', error));
  }

  function actionButton(label, action, className = '') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `social-choice ${className}`.trim();
    button.textContent = label;
    button.addEventListener('click', action);
    return button;
  }

  function renderActions() {
    const turn = session.current();
    const container = byId('social-choices');
    container.replaceChildren();
    for (const option of session.choices()) {
      container.append(actionButton(option.label, () => {
        stopAudio();
        session.choose(option.label);
        renderTurn(true);
      }));
    }
    if (!turn.choice && turn.next) {
      container.append(actionButton('Continue', () => {
        stopAudio();
        session.advance();
        renderTurn(true);
      }, 'continue'));
    }
    if (session.isComplete()) {
      container.append(actionButton('Play again', () => {
        stopAudio();
        session.restart();
        renderTurn(false);
      }, 'continue'));
    }
  }

  function renderTurn(autoPlay) {
    const story = stories[storyIndex];
    const turn = session.current();
    const character = story.characters.find(item => item.id === turn.speaker);
    byId('social-title').textContent = story.title;
    byId('social-progress').textContent = `${storyIndex + 1} / ${stories.length}`;
    storySelect.value = String(storyIndex);
    byId('social-speaker').textContent = character?.name ?? '';
    byId('social-text').textContent = turn.text ?? 'Watch what is happening.';
    video.poster = turn.poster;
    video.src = `${turn.video}?v=${ASSET_VERSION}`;
    video.play().catch(() => {});
    renderActions();
    if (autoPlay && turn.audio) playCurrent();
  }

  function setMode(mode) {
    const social = mode === 'social';
    stopAudio();
    byId('phrase-panel').hidden = social;
    byId('social-panel').hidden = !social;
    byId('mode-phrases').classList.toggle('active', !social);
    byId('mode-social').classList.toggle('active', social);
    if (social) renderTurn(false);
  }

  byId('mode-phrases').addEventListener('click', () => setMode('phrases'));
  byId('phrase-panel').addEventListener('click', event => {
    if (!event.target.closest('#mode-social')) return;
    window.stopAudioPlayback?.();
    setMode('social');
  });
  byId('social-video-card').addEventListener('click', playCurrent);
  byId('social-replay').addEventListener('click', playCurrent);
  byId('social-restart').addEventListener('click', () => {
    stopAudio();
    session.restart();
    renderTurn(false);
  });
  storySelect.addEventListener('change', () => {
    stopAudio();
    storyIndex = Number(storySelect.value);
    session = createStorySession(stories[storyIndex]);
    renderTurn(false);
  });
  byId('social-next').addEventListener('click', () => {
    stopAudio();
    storyIndex = (storyIndex + 1) % stories.length;
    session = createStorySession(stories[storyIndex]);
    renderTurn(false);
  });

  renderTurn(false);
}
