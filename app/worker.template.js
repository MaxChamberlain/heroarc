
const FILES = __FILES__;
const TYPES = {html:'text/html; charset=utf-8',json:'application/json',svg:'image/svg+xml',js:'text/javascript'};
export default {
  async fetch(req, env) {
    // Second lock: Cloudflare Access must have authenticated this request.
    if (!req.headers.get('Cf-Access-Jwt-Assertion')) return new Response('Forbidden', {status: 403});
    const url = new URL(req.url);
    if (url.pathname === '/api/data') {
      const d = await env.HEALTH.get('data');
      return new Response(d || '{}', {headers: {'content-type':'application/json','cache-control':'no-store'}});
    }
    const key = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
    const f = FILES[key];
    if (!f) return new Response('Not found', {status: 404});
    return new Response(f, {headers: {'content-type': TYPES[key.split('.').pop()] || 'text/plain', 'cache-control':'no-cache'}});
  }
};
