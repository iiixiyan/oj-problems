// 华为OD题库 Service Worker - 缓存优化
const CACHE_NAME = 'hvod-cache-v2';
const ASSETS_TO_CACHE = [
    '/',
    '/index.html',
    '/problems-100.json',
    '/sw.js'
];

// 安装时预缓存核心资源
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('Service Worker: 预缓存核心资源');
            return cache.addAll(ASSETS_TO_CACHE).catch(e => {
                console.log('Service Worker: 部分缓存失败（首次安装正常）');
            });
        })
    );
    self.skipWaiting();
});

// 激活时清理旧缓存
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.filter(name => name !== CACHE_NAME).map(name => {
                    console.log('Service Worker: 清理旧缓存', name);
                    return caches.delete(name);
                })
            );
        })
    );
    self.clients.claim();
});

// 请求拦截：缓存优先，网络回退
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    
    // 只缓存本站资源
    if (url.origin !== self.location.origin) return;
    
    // 对大 JSON 文件使用网络优先（确保数据最新）
    if (url.pathname.includes('problems-') && url.pathname.endsWith('.json')) {
        event.respondWith(
            fetch(event.request).then(response => {
                return caches.open(CACHE_NAME).then(cache => {
                    cache.put(event.request, response.clone());
                    return response;
                });
            }).catch(() => {
                return caches.match(event.request);
            })
        );
        return;
    }

    // 对静态资源使用缓存优先
    if (url.pathname.endsWith('.html') || url.pathname.endsWith('.js') || 
        url.pathname.endsWith('.css') || url.pathname.endsWith('.png') || 
        url.pathname.endsWith('.svg') || url.pathname === '/' || url.pathname.endsWith('/')) {
        event.respondWith(
            caches.match(event.request).then(cached => {
                return cached || fetch(event.request).then(response => {
                    return caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, response.clone());
                        return response;
                    });
                });
            })
        );
        return;
    }

    // 题目 HTML 文件：网络优先，缓存回退
    if (url.pathname.includes('/OJ_title/')) {
        event.respondWith(
            fetch(event.request).then(response => {
                return caches.open(CACHE_NAME).then(cache => {
                    cache.put(event.request, response.clone());
                    return response;
                });
            }).catch(() => {
                return caches.match(event.request);
            })
        );
        return;
    }
});
