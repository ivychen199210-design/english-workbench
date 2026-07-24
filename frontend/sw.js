// English Workbench Service Worker - 网络优先策略
const CACHE = 'workbench-v3';
const URLS = ['/', '/manifest.json', '/icon-192.png', '/icon-512.png'];

// 安装时立即激活新版本
self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE).then(c => c.addAll(URLS)).then(() => self.skipWaiting())
    );
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
    // API 请求始终走网络
    if (e.request.url.includes('/api/')) {
        e.respondWith(fetch(e.request));
        return;
    }
    // 页面和静态资源：网络优先，失败时用缓存
    e.respondWith(
        fetch(e.request).then(res => {
            // 成功则更新缓存
            const clone = res.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
            return res;
        }).catch(() => caches.match(e.request))
    );
});
