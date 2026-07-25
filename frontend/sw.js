// Ivy's Inspiration Library - Service Worker v10 (stable)
const CACHE = 'ivy-library-v10';

// 安装时立即激活
self.addEventListener('install', e => {
    self.skipWaiting();
    e.waitUntil(caches.open(CACHE));
});

// 激活时清除旧缓存
self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys => 
            Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', e => {
    const url = new URL(e.request.url);
    
    // API 请求和 HTML 导航：始终走网络，不缓存
    if (url.pathname.includes('/api/') || e.request.mode === 'navigate' || url.pathname === '/') {
        e.respondWith(fetch(e.request, {cache: 'no-store'}));
        return;
    }
    
    // 其他静态资源：网络优先，失败时回退缓存
    e.respondWith(
        fetch(e.request).then(res => {
            const clone = res.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
            return res;
        }).catch(() => caches.match(e.request))
    );
});
