const sections = document.querySelectorAll('.detail-content section');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const observer = new IntersectionObserver(entries => {
  for (const { target, isIntersecting } of entries) {
    if (!isIntersecting) continue;
    observer.unobserve(target);
    target.classList.add('has-entered');
    if (!reduced.matches) target.animate(
      [{ opacity: .65, transform: 'translateY(14px)' }, { opacity: 1, transform: 'none' }],
      { duration: 460, easing: 'cubic-bezier(.2,.72,.23,1)' },
    );
  }
}, { threshold: .12 });
sections.forEach(section => observer.observe(section));

const status = document.querySelector('#release-status');
if (status) loadRelease(status);

async function loadRelease(status) {
  status.textContent = 'Checking the latest release…';
  try {
    const manifest = await loadManifest();
    const response = manifest ?? await fetch('https://api.github.com/repos/VptrCipher/SayIt/releases/latest', { signal: AbortSignal.timeout(8000) });
    if (!manifest && !response.ok) throw new Error('Release unavailable');
    const release = manifest ?? await response.json();
    let count = 0;
    const assetPrefix = 'https://github.com/VptrCipher/SayIt/releases/download/';
    for (const asset of release.assets) {
      const windows = /^SayIt-Setup-x64(?:-Offline)?\.exe$/i.test(asset.name);
      const linux = /^SayIt-[\w.-]+\.AppImage$/i.test(asset.name);
      if ((!windows && !linux) || !asset.browser_download_url?.startsWith(assetPrefix)) continue;
      const row = document.createElement('li');
      const link = document.createElement('a');
      link.href = asset.browser_download_url;
      link.textContent = asset.name + ' ↗';
      row.append(link);
      if (/^sha256:[a-f0-9]{64}$/i.test(asset.digest)) {
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        const digest = document.createElement('code');
        summary.textContent = 'SHA-256 checksum';
        digest.textContent = asset.digest.slice(7);
        details.append(summary, digest);
        row.append(details);
      }
      document.querySelector(windows ? '[data-platform="windows"] ul' : '[data-platform="linux"] ul').append(row);
      count++;
    }
    status.textContent = count ? 'Latest release ' + release.tag_name : 'See GitHub for available release files.';
  } catch {
    status.textContent = 'Couldn’t load release files here. Open the latest release on GitHub below.';
  }
}


const hero = document.querySelector('.detail-hero');
const finePointer = matchMedia('(hover: hover) and (pointer: fine)');
let frame;
function updateScene() {
  frame = undefined;
  const top = hero.getBoundingClientRect().top;
  if (top < -hero.offsetHeight) return;
  hero.style.setProperty('--scene-y', reduced.matches ? '0px' : Math.min(28, Math.max(0, -top * .12)) + 'px');
}
function scheduleScene() {
  frame ??= requestAnimationFrame(updateScene);
}
window.addEventListener('scroll', scheduleScene, { passive: true });
hero.addEventListener('pointermove', event => {
  if (reduced.matches || !finePointer.matches || event.pointerType !== 'mouse') return;
  const bounds = hero.getBoundingClientRect();
  hero.style.setProperty('--orbit-x', 54 - (event.clientY - bounds.top) / bounds.height * 18 + 'deg');
  hero.style.setProperty('--orbit-y', -24 + (event.clientX - bounds.left) / bounds.width * 22 + 'deg');
}, { passive: true });
function resetOrbit() {
  hero.style.removeProperty('--orbit-x');
  hero.style.removeProperty('--orbit-y');
}
hero.addEventListener('pointerleave', resetOrbit);
reduced.addEventListener('change', () => {
  if (reduced.matches) {
    resetOrbit();
    hero.style.removeProperty('--scene-y');
    sections.forEach(section => section.getAnimations().forEach(animation => animation.cancel()));
  }
  scheduleScene();
});
scheduleScene();


async function loadManifest() {
  try {
    const response = await fetch('../release-manifest.json', { signal: AbortSignal.timeout(2500) });
    if (!response.ok) return null;
    const manifest = await response.json();
    if (typeof manifest.version !== 'string' || !manifest.platforms) return null;
    const prefix = 'https://github.com/VptrCipher/SayIt/releases/download/';
    const assets = Object.entries(manifest.platforms)
      .filter(([key, asset]) => ['windows', 'windows_ondemand', 'linux'].includes(key) && asset?.url?.startsWith(prefix))
      .map(([, asset]) => ({
        name: decodeURIComponent(new URL(asset.url).pathname.split('/').at(-1)),
        browser_download_url: asset.url,
        digest: 'sha256:' + asset.sha256,
      }));
    return assets.length ? { tag_name: 'v' + manifest.version, assets } : null;
  } catch {
    return null;
  }
}
