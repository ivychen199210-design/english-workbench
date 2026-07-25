// Ivy's Inspiration Library - Service Worker v8 (vocab audio)
const CACHE = 'ivy-library-v8';
const URLS = ['/', '/manifest.json', '/icon-new-192.png', '/icon-new-512.png'];

// 安装时立即激活新版本
self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE).then(c => c.addAll(URLS)).then(() => self.skipWaiting())
    );
});

// 激活时清除所有旧缓存（包括 workbench-v* 等旧版本）
self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys => 
            Promise.all(keys.map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', e => {
    // API 请求始终走网络
    if (e.request.url.includes('/api/')) {
        e.respondWith(fetch(e.request));
        return;
    }
    // 页面和静态资源：网络优先
    e.respondWith(
        fetch(e.request).then(res => {
            const clone = res.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
            return res;
        }).catch(() => caches.match(e.request))
    );
});
