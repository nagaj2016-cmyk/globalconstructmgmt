/**
 * NagaForge — Service Worker (Phase 14 PWA)
 * Strategy:
 *   - App shell (HTML/JS): Cache-first with background revalidation
 *   - API calls: Network-first, fallback to cache for GET requests
 *   - Static assets: Cache-first
 */

const CACHE_NAME    = "nagaforge-v1";
const API_CACHE     = "nagaforge-api-v1";
const OFFLINE_URL   = "/offline.html";

// App shell resources to pre-cache on install
const PRECACHE_URLS = [
  "/",
  "/index.html",
  "/manifest.json",
];

// ── Install ──────────────────────────────────────────────────────────────────

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS).catch((err) => {
        console.warn("[SW] Pre-cache partial failure (offline):", err);
      });
    }).then(() => self.skipWaiting())
  );
});

// ── Activate ─────────────────────────────────────────────────────────────────

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME && k !== API_CACHE)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch ─────────────────────────────────────────────────────────────────────

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== "GET") return;
  // Allow same-origin only (works for localhost AND ngrok — same origin serves both API and frontend)
  if (url.origin !== self.location.origin) return;

  // API calls — Network-first, cache fallback
  if (url.pathname.startsWith("/api/") || isApiEndpoint(url.pathname)) {
    event.respondWith(networkFirstAPI(request));
    return;
  }

  // App shell / static assets — Cache-first, network fallback
  event.respondWith(cacheFirstApp(request));
});

function isApiEndpoint(pathname) {
  const apiPrefixes = [
    "/projects", "/workers", "/clients", "/finance",
    "/safety", "/quality", "/site-ops", "/structural",
    "/steel", "/bim", "/saas", "/reports",
    "/scheduling", "/commercial", "/inventory",
    "/documents", "/controls", "/company", "/dashboard",
  ];
  return apiPrefixes.some((p) => pathname.startsWith(p));
}

async function networkFirstAPI(request) {
  const cache = await caches.open(API_CACHE);
  try {
    const response = await fetch(request.clone());
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await cache.match(request);
    if (cached) {
      // Add offline header so UI can show stale-data indicator
      const headers = new Headers(cached.headers);
      headers.set("X-Cache-Status", "offline");
      return new Response(cached.body, { status: cached.status, headers });
    }
    // Return structured offline response for API
    return new Response(
      JSON.stringify({ error: "offline", message: "No network. Showing cached data." }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }
}

async function cacheFirstApp(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) {
    // Revalidate in background
    fetch(request).then((r) => { if (r.ok) cache.put(request, r); }).catch(() => {});
    return cached;
  }
  try {
    const response = await fetch(request);
    if (response.ok && response.status < 400) {
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Fallback to root for SPA navigation
    const root = await cache.match("/");
    return root || new Response("App offline", { status: 503 });
  }
}

// ── Push Notifications ────────────────────────────────────────────────────────

self.addEventListener("push", (event) => {
  let data = { title: "NagaForge", body: "You have a new update.", icon: "/manifest.json" };
  try { data = { ...data, ...event.data.json() }; } catch {}

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body:    data.body,
      icon:    data.icon || "/manifest.json",
      badge:   data.badge || "/manifest.json",
      tag:     data.tag || "nagaforge",
      data:    data,
      actions: data.actions || [
        { action: "open",    title: "Open App" },
        { action: "dismiss", title: "Dismiss"  },
      ],
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  if (event.action === "dismiss") return;

  const url = event.notification.data?.url || "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url === url && "focus" in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});

// ── Background Sync ───────────────────────────────────────────────────────────
// Used for offline form submissions (attendance, site diary, safety incidents)

const SYNC_QUEUE_KEY = "nagaforge-sync-queue";

self.addEventListener("sync", (event) => {
  if (event.tag === "nagaforge-sync") {
    event.waitUntil(processSyncQueue());
  }
});

async function processSyncQueue() {
  // Open an IDB-backed queue if available; falls back gracefully
  try {
    const cache = await caches.open("nagaforge-sync");
    const keys  = await cache.keys();
    for (const req of keys) {
      try {
        const res = await fetch(req.clone());
        if (res.ok) await cache.delete(req);
      } catch {}
    }
  } catch (e) {
    console.warn("[SW] Sync queue processing failed:", e);
  }
}

// ── Message Handler ───────────────────────────────────────────────────────────

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
  if (event.data?.type === "CLEAR_CACHE") {
    caches.keys().then((keys) => keys.forEach((k) => caches.delete(k)));
  }
  if (event.data?.type === "CACHE_VERSION") {
    event.source?.postMessage({ type: "CACHE_VERSION", version: CACHE_NAME });
  }
});

console.log("[SW] NagaForge Service Worker loaded —", CACHE_NAME);
