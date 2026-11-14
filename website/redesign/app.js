const demo = document.querySelector('.demo');
const record = document.querySelector('#record');

const transcript = document.querySelector('#transcript');
const status = document.querySelector('#state');
const motion = matchMedia('(prefers-reduced-motion: reduce)');
const examples = {
  developer: ['Code editor', 'open the git hub actions log and run get user by id camel case', ['Open the ', 'GitHub', ' Actions log and run ', 'getUserById', '.']],
  email: ['Email client', 'hi alex comma new paragraph the draft is ready for review', ['Hi Alex,\n\nThe draft is ready for review.']],
  chat: ['Chat app', 'let’s ship friday scratch that let’s ship monday', ['Let’s ship Monday.']],
};
let phase = 'idle';
let input;
let timer;
let profile = 'developer';

function setPhase(next, message) {
  phase = next;
  demo.dataset.phase = next;
  status.textContent = message;
}
function cancel(message) {
  clearTimeout(timer);
  input = undefined;
  transcript.textContent = 'Your transcript appears here.';
  setPhase('idle', message);
}
function start(source) {
  cancel('Ready');
  input = source;
  setPhase('recording', 'Recording example…');
}
function finish() {
  if (phase !== 'recording') return;
  input = undefined;
  setPhase('processing', 'Formatting example…');
  timer = setTimeout(() => {
    const parts = examples[profile][2];
    transcript.replaceChildren(...parts.map((part, index) => {
      if (index % 2 === 0) return document.createTextNode(part);
      const mark = document.createElement('mark');
      mark.textContent = part;
      return mark;
    }));
    setPhase('complete', 'Inserted text. ' + transcript.textContent);
  }, motion.matches ? 0 : 320);
}
demo.querySelector('.profiles').addEventListener('change', event => {
  profile = event.target.value;
  const [app, spoken] = examples[profile];
  document.querySelector('#active-app').textContent = app;
  document.querySelector('#spoken').textContent = spoken;
  cancel('Ready');
});
record.addEventListener('keydown', event => {
  if (event.code !== 'Space') return;
  event.preventDefault();
  if (!event.repeat) start('keyboard');
});
record.addEventListener('keyup', event => {
  if (event.code !== 'Space') return;
  event.preventDefault();
  if (input === 'keyboard') finish();
});
record.addEventListener('blur', () => {
  if (input === 'keyboard') cancel('Cancelled');
});
record.addEventListener('pointerdown', event => {
  if (!event.isPrimary || event.button !== 0) return;
  record.setPointerCapture(event.pointerId);
  start(event.pointerId);
});
record.addEventListener('pointerup', event => {
  if (input === event.pointerId) finish();
});
for (const name of ['pointercancel', 'lostpointercapture']) {
  record.addEventListener(name, event => {
    if (input === event.pointerId) cancel('Cancelled');
  });
}
function playExample() {
  start('play');
  timer = setTimeout(finish, motion.matches ? 0 : 680);
}
record.addEventListener('click', event => {
  if (event.detail === 0 && phase !== 'processing') playExample();
});

for (const link of document.querySelectorAll('[data-example]')) {
  link.addEventListener('click', event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const radio = demo.querySelector(`input[value="${link.dataset.example}"]`);
    radio.checked = true;
    radio.dispatchEvent(new Event('change', { bubbles: true }));
    playExample();
    history.pushState(null, '', '#demo');
    document.querySelector('#demo').scrollIntoView({ behavior: motion.matches ? 'instant' : 'smooth' });
    record.focus({ preventScroll: true });
  });
}

const menu = document.querySelector('.menu-trigger');
const nav = document.querySelector('#nav-links');
function closeMenu() { menu.setAttribute('aria-expanded', 'false'); }
menu.addEventListener('click', () => {
  menu.setAttribute('aria-expanded', String(menu.getAttribute('aria-expanded') === 'false'));
});
nav.addEventListener('click', event => {
  if (event.target.closest('a')) closeMenu();
});
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  if (phase === 'recording' || phase === 'processing') cancel('Cancelled');
  if (menu.getAttribute('aria-expanded') === 'true') {
    closeMenu();
    menu.focus();
  }
});

const workflow = document.querySelector('.workflow-visual');
const steps = [...document.querySelectorAll('.steps li')];
const workflowSection = document.querySelector('.workflow');
const hero = document.querySelector('.hero');
const photo = document.querySelector('.hero-image img');
const progress = workflow.querySelector('.progress span');
const sample = document.querySelector('.hero-sample');
const finePointer = matchMedia('(hover: hover) and (pointer: fine)');
const pointer = { x: 0, y: 0 };
let workflowVisible = false;
let heroVisible = true;
let frame;
function paint() {
  frame = undefined;
  if (workflowVisible) {
    const marker = innerHeight * .57;
    const index = Math.max(0, steps.findLastIndex(step => step.getBoundingClientRect().top <= marker));
    if (+workflow.dataset.step !== index) {
      workflow.dataset.step = index;
      steps.forEach((step, position) => step.classList.toggle('active', position === index));
      document.querySelector('#step-number').textContent = '0' + (index + 1) + ' / 04';
    }
    progress.style.transform = 'scaleX(' + (index + 1) / steps.length + ')';
  }
  if (heroVisible && !motion.matches) {
    const offset = Math.max(0, -hero.getBoundingClientRect().top);
    const { x, y } = pointer;
    photo.style.transform = `translate3d(${x * -14}px, ${offset * .14 - y * 10}px, 0) scale(1.11)`;
    sample.style.transform = `perspective(680px) rotateX(${y * -10}deg) rotateY(${x * 13}deg) translateY(${offset * -.08}px)`;
  }
}
function schedule() { frame ??= requestAnimationFrame(paint); }
const visibility = new IntersectionObserver(entries => {
  for (const { target, isIntersecting } of entries) {
    target.classList.toggle('is-visible', isIntersecting);
    if (target === workflowSection) {
      workflowVisible = isIntersecting;
      workflow.classList.toggle('is-visible', isIntersecting);
    }
    if (target === hero) heroVisible = isIntersecting;
  }
  schedule();
});
for (const element of [hero, workflowSection, sample]) visibility.observe(element);
hero.addEventListener('pointermove', event => {
  if (motion.matches || !finePointer.matches || event.pointerType !== 'mouse') return;
  const bounds = hero.getBoundingClientRect();
  pointer.x = (event.clientX - bounds.left) / bounds.width * 2 - 1;
  pointer.y = (event.clientY - bounds.top) / bounds.height * 2 - 1;
  schedule();
}, { passive: true });
hero.addEventListener('pointerleave', () => {
  pointer.x = 0;
  pointer.y = 0;
  schedule();
});
const reveal = new IntersectionObserver(entries => {
  for (const { target, isIntersecting } of entries) {
    if (!isIntersecting) continue;
    target.classList.add('has-entered');
    if (!motion.matches && target.hasAttribute('data-reveal')) target.animate([{ opacity: .4, transform: 'translateY(14px)' }, { opacity: 1, transform: 'none' }], { duration: 540, easing: 'cubic-bezier(.22,1,.36,1)' });
    reveal.unobserve(target);
  }
}, { threshold: .18 });
const appRow = document.querySelector('.app-row');
const appTrack = appRow.querySelector('.app-track');
const appCopy = appTrack.firstElementChild.cloneNode(true);
appCopy.removeAttribute('aria-label');
appCopy.setAttribute('aria-hidden', 'true');
appTrack.append(appCopy);
appRow.classList.add('is-marquee');
visibility.observe(appRow);
for (const element of document.querySelectorAll('[data-reveal], [data-timing]')) reveal.observe(element);
if (!motion.matches) {
  document.querySelector('.hero h1').animate([{ opacity: .2, transform: 'translateY(22px)' }, { opacity: 1, transform: 'none' }], { duration: 860, easing: 'cubic-bezier(.22,1,.36,1)' });
}
window.addEventListener('scroll', schedule, { passive: true });
window.addEventListener('resize', schedule);
motion.addEventListener('change', () => {
  if (motion.matches) {
    photo.style.removeProperty('transform');
    sample.style.removeProperty('transform');
    pointer.x = pointer.y = 0;
    document.getAnimations().forEach(animation => animation.cancel());
  }
  schedule();
});




const field = document.querySelector('.signal-field');
const ink = field.getContext('2d');
if (ink) {
  let inView = false;
  let signalFrame;
  const shapes = {
    idle: [10, '#c9b887'],
    recording: [33, '#f9d889'],
    processing: [19, '#f7e3b3'],
    complete: [5, '#e5ce98'],
  };
  let amplitude = shapes.idle[0];
  function drawSignal(time) {
    signalFrame = undefined;
    const [target, color] = shapes[phase];
    amplitude = motion.matches ? target : amplitude + (target - amplitude) * .12;
    const angle = motion.matches ? 0 : time * .0016;
    const { width, height } = field;
    ink.clearRect(0, 0, width, height);
    ink.strokeStyle = color;
    for (let row = 8; row >= 0; row--) {
      const z = row * 17;
      const scale = 410 / (410 + z);
      ink.globalAlpha = .84 - row * .083;
      ink.lineWidth = row === 0 ? 1.8 : 1;
      ink.beginPath();
      for (let column = 0; column <= 72; column++) {
        const u = column / 72;
        const envelope = Math.sin(u * Math.PI) ** 1.7;
        const signal = Math.sin(u * 24 - angle + row * .44) + .34 * Math.sin(u * 49 + angle);
        const x = width / 2 + ((u - .5) * (width - 18) + z * .15) * scale;
        const y = height * .62 + (signal * amplitude * envelope - z * .36) * scale;
        if (column === 0) ink.moveTo(x, y);
        else ink.lineTo(x, y);
      }
      ink.stroke();
    }
    if (inView && !motion.matches) signalFrame = requestAnimationFrame(drawSignal);
  }
  function refreshSignal() {
    cancelAnimationFrame(signalFrame);
    if (inView || motion.matches) drawSignal(performance.now());
  }
  new IntersectionObserver(([entry]) => {
    inView = entry.isIntersecting;
    refreshSignal();
  }).observe(field);
  new MutationObserver(() => {
    if (motion.matches) refreshSignal();
  }).observe(demo, { attributes: true, attributeFilter: ['data-phase'] });
  motion.addEventListener('change', refreshSignal);
}



const film = document.querySelector('.film');
const filmCanvas = film.querySelector('.film-signal');
const filmInk = filmCanvas.getContext('2d');
if (filmInk) {
  let filmFrame;
  let filmVisible = false;
  function paintFilm() {
    filmFrame = undefined;
    if (!filmVisible || motion.matches) return;
    const travel = Math.max(1, film.offsetHeight - hero.offsetHeight);
    const p = Math.max(0, Math.min(1, -film.getBoundingClientRect().top / travel));
    const morph = p * p * (3 - 2 * p);
    const { width, height } = filmCanvas;
    filmInk.clearRect(0, 0, width, height);
    const glow = filmInk.createLinearGradient(0, 0, width, 0);
    glow.addColorStop(0, '#f5cd8e00');
    glow.addColorStop(.3, '#f5cd8e');
    glow.addColorStop(.65, '#fff2cf');
    glow.addColorStop(1, '#f5cd8e00');
    filmInk.strokeStyle = glow;
    for (let row = 9; row >= 0; row--) {
      const z = row * 22;
      const perspective = 540 / (540 + z);
      filmInk.lineWidth = row === 0 ? 2 : 1;
      filmInk.globalAlpha = (.83 - row * .065) * (1 - morph);
      filmInk.beginPath();
      for (let col = 0; col <= 100; col++) {
        const u = col / 100;
        const envelope = Math.sin(Math.PI * u) ** 1.6;
        const wave = Math.sin(u * 22 - p * 9 + row * .42) + .3 * Math.sin(u * 57 + p * 14);
        const x = width / 2 + (u - .5) * width * perspective;
        const y = height / 2 + (wave * 52 * envelope * (1 - morph) - z * .13) * perspective;
        if (col === 0) filmInk.moveTo(x, y);
        else filmInk.lineTo(x, y);
      }
      filmInk.stroke();
    }
    filmInk.globalAlpha = morph;
    filmInk.fillStyle = '#fff1c9';
    filmInk.fillRect(width / 2, height / 2 - 25, 3, 50);
  }
  function scheduleFilm() {
    if (filmVisible && !motion.matches) filmFrame ??= requestAnimationFrame(paintFilm);
  }
  new IntersectionObserver(([entry]) => {
    filmVisible = entry.isIntersecting;
    scheduleFilm();
  }).observe(film);
  film.classList.add('is-film');
  window.addEventListener('scroll', scheduleFilm, { passive: true });
  window.addEventListener('resize', scheduleFilm);
  motion.addEventListener('change', scheduleFilm);
}

const gallery = document.querySelector('.profile-gallery');
const slides = [...gallery.querySelectorAll('article')];
const galleryNav = gallery.querySelector('.gallery-nav');
const galleryStatus = galleryNav.querySelector('[role="status"]');
let activeSlide = 0;
function showSlide(index, animate = true) {
  activeSlide = (index + slides.length) % slides.length;
  slides.forEach((slide, position) => { slide.hidden = position !== activeSlide; });
  const slide = slides[activeSlide];
  galleryStatus.textContent = slide.querySelector('h3').textContent + ' · ' + (activeSlide + 1) + ' / ' + slides.length;
  if (animate && !motion.matches) slide.animate(
    [{ opacity: .4, translate: '12px 0' }, { opacity: 1, translate: '0 0' }],
    { duration: 280, easing: 'cubic-bezier(.2,.72,.23,1)' },
  );
}
galleryNav.addEventListener('click', event => {
  const control = event.target.closest('[data-gallery]');
  if (control) showSlide(activeSlide + Number(control.dataset.gallery));
});
gallery.classList.add('is-gallery');
galleryNav.hidden = false;
showSlide(0, false);

const intro = document.querySelector('.edition-intro');
if (!motion.matches && performance.getEntriesByType('navigation')[0]?.type === 'navigate' && !location.hash && !sessionStorage.getItem('sayit-intro')) {
  sessionStorage.setItem('sayit-intro', '1');
  intro.classList.add('is-loading');
  setTimeout(() => intro.classList.remove('is-loading'), 820);
}

const exampleDialog = document.querySelector('.edition-dialog');
const detailControl = document.querySelector('.gallery-detail');
detailControl.hidden = false;
detailControl.addEventListener('click', () => {
  const profileName = slides[activeSlide].querySelector('[data-example]').dataset.example;
  const [, spoken, inserted] = examples[profileName];
  exampleDialog.querySelector('h2').textContent = slides[activeSlide].querySelector('h3').textContent;
  exampleDialog.querySelector('[data-spoken]').textContent = spoken;
  exampleDialog.querySelector('[data-inserted]').textContent = inserted.join('');
  exampleDialog.showModal();
});
exampleDialog.querySelector('[data-dialog-example]').addEventListener('click', event => {
  event.preventDefault();
  exampleDialog.close();
  slides[activeSlide].querySelector('[data-example]').click();
});

const scenePresets = {
  prologue: { rows: 3, columns: 106, height: .5, hue: '201,169,117', opacity: .55 },
  privacy: { rows: 4, columns: 76, height: .33, hue: '225,188,124', opacity: .25 },
  closing: { rows: 6, columns: 92, height: .7, hue: '231,193,127', opacity: .43 },
};

const chapterScenes = [...document.querySelectorAll('[data-signal-scene]')].map(section => {
  const canvas = document.createElement('canvas');
  canvas.className = 'chapter-signal';
  canvas.setAttribute('aria-hidden', 'true');
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  section.prepend(canvas);
  return { section, canvas, ctx, preset: scenePresets[section.dataset.signalScene] };
}).filter(Boolean);
const visibleChapters = new Set();
let chapterFrame;
function drawChapters() {
  chapterFrame = undefined;
  for (const scene of visibleChapters) {
    const { section, canvas, ctx, preset } = scene;
    const bounds = section.getBoundingClientRect();
    const p = motion.matches ? .66 : Math.max(0, Math.min(1, (innerHeight - bounds.top) / (innerHeight + bounds.height)));
    section.style.setProperty('--chapter-p', motion.matches ? 1 : Math.min(1, p * 2.3));
    const w = Math.min(1440, Math.ceil(bounds.width));
    const h = Math.min(920, Math.ceil(bounds.height));
    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;
    ctx.clearRect(0, 0, w, h);
    for (let row = preset.rows - 1; row >= 0; row--) {
      const depth = 1 / (1 + row * .18);
      for (let col = 0; col < preset.columns; col++) {
        const u = col / (preset.columns - 1);
        const wave = Math.sin(u * 16 + row * .8 - p * 5) * Math.cos(u * 8 + row * .5);
        const edge = Math.abs(u - .5) * 2;
        const mask = section.dataset.signalScene === 'prologue' ? .17 + edge ** 2 : .31 + edge * .6;
        const length = (8 + Math.abs(wave) * h * preset.height) * depth * mask;
        const x = w / 2 + (u - .5) * w * depth * 1.1;
        const y = h * (.44 + wave * .28 * depth) - (p - .5) * 140 * depth;
        ctx.fillStyle = 'rgba(' + preset.hue + ',' + (preset.opacity * depth * mask) + ')';
        ctx.fillRect(x, y - length / 2, Math.max(1, w / 680), length);
      }
    }
  }
}
function queueChapters() {
  if (visibleChapters.size) chapterFrame ??= requestAnimationFrame(drawChapters);
}
const chapterVisibility = new IntersectionObserver(entries => {
  for (const entry of entries) {
    const scene = chapterScenes.find(item => item.section === entry.target);
    if (entry.isIntersecting) visibleChapters.add(scene);
    else visibleChapters.delete(scene);
  }
  queueChapters();
});
chapterScenes.forEach(scene => chapterVisibility.observe(scene.section));
window.addEventListener('scroll', () => { if (!motion.matches) queueChapters(); }, { passive: true });
window.addEventListener('resize', queueChapters);
motion.addEventListener('change', queueChapters);
