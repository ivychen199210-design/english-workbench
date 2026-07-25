// Ivy's Inspiration Library - Service Worker v9 (force no-cache for HTML)
const CACHE = 'ivy-library-v9';
const URLS = ['/manifest.json', '/icon-new-192.png', '/icon-new-512.png'];

// 监听 skipWaiting 消息
self.addEventListener('message', e => {
    if (e.data === 'skipWaiting') self.skipWaiting();
});

// 安装时立即激活新版本（不预缓存 HTML）
self.addEventListener('install', e => {
    self.skipWaiting();
    e.waitUntil(
        caches.open(CACHE).then(c => c.addAll(URLS)).catch(() => {})
    );
});

// 激活时清除所有旧缓存
self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys => 
            Promise.all(keys.map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', e => {
    const url = new URL(e.request.url);
    
    // API 请求始终走网络
    if (url.pathname.includes('/api/')) {
        e.respondWith(fetch(e.request));
        return;
    }
    
    // HTML 导航请求：始终走网络，不读缓存
    if (e.request.mode === 'navigate' || url.pathname === '/' || url.pathname.endsWith('.html')) {
        e.respondWith(
            fetch(e.request, {cache: 'no-store'}).then(res => {
                return res;
            }).catch(() => caches.match(e.request))
        );
        return;
    }
    
    // 其他静态资源：网络优先
    e.respondWith(
        fetch(e.request).then(res => {
            const clone = res.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
            return res;
        }).catch(() => caches.match(e.request))
    );
});
