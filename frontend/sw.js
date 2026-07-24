// English Workbench Service Worker - 离线缓存支持
const CACHE = 'workbench-v1';
const URLS = ['/', '/manifest.json', '/icon-192.png', '/icon-512.png'];

self.addEventListener('install', e => {
    e.waitUntil(caches.open(CACHE).then(c => c.addAll(URLS)));
});

self.addEventListener('fetch', e => {
    // API 请求走网络优先
    if (e.request.url.includes('/api/')) {
        e.respondWith(
            fetch(e.request).catch(() => caches.match(e.request))
        );
        return;
    }
    // 静态资源缓存优先
    e.respondWith(
        caches.match(e.request).then(r => r || fetch(e.request))
    );
});
