// Representative mock data + smart catch-all for the momentstudio admin API.
// All paths are matched against the pathname AFTER stripping /api/v1.

const now = new Date();
const iso = (d) => new Date(d).toISOString();
const daysAgo = (n) => iso(now.getTime() - n * 864e5);

export const OWNER_USER = {
  id: 'u-owner-1', email: 'owner@momentstudio.ro', username: 'owner', name: 'Adriana Owner',
  name_tag: 1, first_name: 'Adriana', last_name: 'Owner', role: 'owner', email_verified: true,
  two_factor_enabled: true, preferred_language: 'en', created_at: daysAgo(400), updated_at: daysAgo(1),
  admin_training_mode: false, avatar_url: null,
};

const meta = (n = 3, limit = 20, page = 1) => ({ total_items: n, total_pages: Math.max(1, Math.ceil(n / limit)), page, limit });

const PRODUCTS = Array.from({ length: 8 }).map((_, i) => ({
  id: `p-${i + 1}`, slug: `hand-painted-vase-${i + 1}`, name: `Hand-Painted Ceramic Vase ${i + 1}`,
  price: 120 + i * 35, currency: 'RON', status: i % 4 === 0 ? 'draft' : 'published',
  category: ['Vases', 'Wall Art', 'Sculpture'][i % 3], sku: `MS-VAS-00${i + 1}`,
  stock_quantity: i % 5 === 0 ? 2 : 14 + i, publish_at: i % 4 === 0 ? null : daysAgo(30 - i),
  tags: ['handmade', 'ceramic'], thumbnail_url: null, is_visible: true,
}));

const ORDERS = Array.from({ length: 8 }).map((_, i) => ({
  id: `ORD-10${i + 1}`, order_number: `MS-2026-10${i + 1}`,
  status: ['paid', 'fulfilled', 'pending', 'refunded', 'cancelled'][i % 5],
  payment_status: ['captured', 'authorized', 'pending'][i % 3],
  fulfillment_status: ['unfulfilled', 'fulfilled', 'partial'][i % 3],
  total_amount: 150 + i * 60, currency: 'RON', created_at: daysAgo(i + 1),
  customer: `Customer ${i + 1}`, customer_email: `cust${i + 1}@example.com`, items_count: 1 + (i % 3),
}));

const USERS = Array.from({ length: 8 }).map((_, i) => ({
  id: `u-${i + 1}`, email: `user${i + 1}@example.com`, username: `user${i + 1}`,
  name: `User ${i + 1}`, name_tag: i + 1, role: ['customer', 'support', 'content', 'fulfillment', 'admin'][i % 5],
  created_at: daysAgo(i * 10 + 5), email_verified: i % 2 === 0, two_factor_enabled: i % 3 === 0,
  orders_count: i, total_spent: i * 240, is_banned: false,
}));

const COUPONS = Array.from({ length: 6 }).map((_, i) => ({
  id: `c-${i + 1}`, code: `SAVE${(i + 1) * 10}`, percentage_off: i % 2 === 0 ? (i + 1) * 5 : null,
  amount_off: i % 2 === 1 ? (i + 1) * 10 : null, currency: 'RON',
  expires_at: daysAgo(-30 + i), active: i % 3 !== 0, times_used: i * 4, max_uses: 100,
}));

const RETURNS = Array.from({ length: 5 }).map((_, i) => ({
  id: `r-${i + 1}`, rma_number: `RMA-20${i + 1}`, order_id: `ORD-10${i + 1}`, order_number: `MS-2026-10${i + 1}`,
  status: ['requested', 'approved', 'received', 'refunded', 'rejected'][i % 5],
  reason: 'Damaged on arrival', created_at: daysAgo(i + 2), customer: `Customer ${i + 1}`,
  refund_amount: 60 + i * 20, currency: 'RON', items_count: 1 + (i % 2),
}));

const CONTENT_PAGES = ['about', 'terms', 'privacy', 'shipping', 'returns-policy', 'faq'].map((k, i) => ({
  id: `cp-${i}`, key: `page.${k}`, title: k.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
  updated_at: daysAgo(i + 1), version: i + 2, status: 'published', lang: 'en', sort_order: i,
  published_at: daysAgo(i + 1), needs_translation_ro: i % 2 === 0,
}));

const BLOG_POSTS = Array.from({ length: 5 }).map((_, i) => ({
  id: `b-${i + 1}`, slug: `studio-journal-${i + 1}`, title: `Studio Journal Entry ${i + 1}`,
  status: i % 3 === 0 ? 'draft' : 'published', published_at: daysAgo(i * 7), updated_at: daysAgo(i),
  author: { id: 'u-owner-1', username: 'owner', name: 'Adriana Owner' }, excerpt: 'A look inside the studio process.',
  tags: ['process', 'behind-the-scenes'], series: null, cover_image_url: null, comment_count: i * 2,
}));

const INVENTORY = PRODUCTS.map((p, i) => ({
  id: p.id, product_id: p.id, slug: p.slug, name: p.name, sku: p.sku,
  stock_quantity: p.stock_quantity, low_stock_threshold: 5, reserved: i % 3,
  status: p.stock_quantity <= 5 ? 'low' : 'ok', updated_at: daysAgo(i), variant: null,
}));

const SUMMARY = {
  products: 42, orders: 318, users: 1204, low_stock: 3, sales_30d: 48230, gross_sales_30d: 52100,
  net_sales_30d: 45980, orders_30d: 96, sales_range: 48230, gross_sales_range: 52100, net_sales_range: 45980,
  orders_range: 96, range_days: 30, range_from: daysAgo(30), range_to: iso(now),
  today_orders: 6, yesterday_orders: 4, orders_delta_pct: 50, today_sales: 1820, yesterday_sales: 1410,
  sales_delta_pct: 29.1, gross_today_sales: 1980, gross_yesterday_sales: 1520, gross_sales_delta_pct: 30.2,
  net_today_sales: 1720, net_yesterday_sales: 1330, net_sales_delta_pct: 29.3,
  today_refunds: 1, yesterday_refunds: 0, refunds_delta_pct: null,
  anomalies: { has_anomaly: false, items: [] },
  alert_thresholds: { payment_failure_rate_pct: 5, webhook_error_rate_pct: 5, refund_rate_pct: 10, low_stock_count: 5 },
  system: { status: 'ok', db: 'ok', cache: 'ok', queue: 'ok' },
};

// Exact-suffix handlers (highest priority). Key = pathname after /api/v1.
export const EXACT = {
  'GET /auth/me': OWNER_USER,
  'GET /auth/admin/access': { allowed: true },
  'POST /auth/refresh': { access_token: 'mock.mock.mock', refresh_token: 'mock.mock.mock', token_type: 'bearer' },
  'GET /auth/me/2fa': { enabled: true, confirmed_at: daysAgo(100), recovery_codes_remaining: 8 },
  'GET /auth/me/passkeys': [],
  'GET /auth/me/sessions': [],
  'GET /auth/me/security-events': [],
  'GET /auth/me/export/jobs/latest': null,
  'GET /admin/dashboard/summary': SUMMARY,
  'GET /admin/dashboard/funnel': { range_days: 30, range_from: daysAgo(30), range_to: iso(now), opt_in_only: false,
    counts: { sessions: 5400, carts: 1200, checkouts: 420, orders: 96 },
    conversions: { to_cart: 22.2, to_checkout: 35, to_order: 22.9 } },
  'GET /admin/dashboard/scheduled-tasks': { publish_schedules: [], promo_schedules: [] },
  'GET /admin/dashboard/alert-thresholds': SUMMARY.alert_thresholds,
  'GET /admin/dashboard/maintenance': { enabled: false, message: '', allow_admins: true },
  'GET /admin/dashboard/audit/retention': { retention_days: 90 },
  'GET /coupons/admin/analytics': { total_discount_ron: '4820.00', total_shipping_discount_ron: '320.00',
    redemptions: 184, avg_order_total_with_coupon: '210.00', avg_order_total_without_coupon: '180.00', rows: [] },
  'GET /fx/admin/status': { base: 'RON', updated_at: daysAgo(0), override_active: false, rates: { EUR: 0.2, USD: 0.22 } },
  'GET /fx/rates': { base: 'RON', rates: { EUR: 0.2, USD: 0.22, RON: 1 }, updated_at: daysAgo(0) },
  'GET /content/site.navigation': { key: 'site.navigation', value: { primary: [], footer: [] }, meta: {} },
  'GET /content/site.company': { key: 'site.company', value: { name: 'momentstudio', email: 'hello@momentstudio.ro' } },
  'GET /content/site.social': { key: 'site.social', value: { instagram: [], facebook: [] } },
  'GET /content/site.checkout': { key: 'site.checkout', value: {} },
  'GET /notifications/unread-count': { count: 0, unread: 0 },
  'GET /notifications': { items: [], meta: meta(0) },
  'GET /ops/banner': null,
  'GET /ops/admin/diagnostics': { status: 'ok', checks: [] },
  'GET /ops/admin/webhooks/stats': { total: 0, failed: 0, pending: 0 },
  'GET /ops/admin/webhooks/backlog': { items: [], meta: meta(0) },
  'GET /ops/admin/email-failures/stats': { total: 0, last_24h: 0 },
  'GET /health': { status: 'ok' },
  'GET /health/ready': { status: 'ok' },
  'GET /catalog/categories': [
    { id: 'cat-1', name: 'Vases', slug: 'vases', is_visible: true, sort_order: 0, parent_id: null },
    { id: 'cat-2', name: 'Wall Art', slug: 'wall-art', is_visible: true, sort_order: 1, parent_id: null },
    { id: 'cat-3', name: 'Sculpture', slug: 'sculpture', is_visible: true, sort_order: 2, parent_id: null },
  ],
  'GET /admin/ui/favorites': { items: [] },
};

// Pattern handlers (regex on pathname). Ordered; first match wins.
export const PATTERNS = [
  [/\/content\/site\.(header-banners|announcement|footer-promo|banners)$/, () => ({ key: 'site.x', value: [] })],
  [/\/catalog\/products\/price-bounds$/, () => ({ min: 0, max: 2000, currency: 'RON' })],
  [/\/catalog\/products$/, () => ({ items: PRODUCTS, meta: meta(PRODUCTS.length) })],
  [/\/admin\/dashboard\/products\/search$/, () => ({ items: PRODUCTS.map((p, i) => ({
      id: p.id, slug: p.slug, sku: p.sku, name: p.name, base_price: p.price, currency: 'RON',
      status: p.status, is_active: p.status === 'published', is_featured: i % 3 === 0, stock_quantity: p.stock_quantity,
      category_slug: p.category.toLowerCase().replace(/\s/g, '-'), category_name: p.category, updated_at: daysAgo(i),
      sale_type: i % 2 === 0 ? 'percent' : null, sale_value: i % 2 === 0 ? 10 : null, missing_translations: i % 2 === 0 ? ['ro'] : [],
    })), meta: meta(PRODUCTS.length) })],
  [/\/admin\/dashboard\/products$/, () => ({ items: PRODUCTS, meta: meta(PRODUCTS.length) })],
  [/\/admin\/dashboard\/orders$/, () => ({ items: ORDERS, meta: meta(ORDERS.length) })],
  [/\/admin\/dashboard\/users\/search$/, () => ({ items: USERS.map((u) => ({
      id: u.id, email: u.email, username: u.username, name: u.name, name_tag: u.name_tag, role: u.role,
      email_verified: u.email_verified, created_at: u.created_at,
    })), meta: meta(USERS.length) })],
  [/\/admin\/dashboard\/users$/, () => ({ items: USERS, meta: meta(USERS.length) })],
  [/\/admin\/dashboard\/coupons$/, () => ({ items: COUPONS, meta: meta(COUPONS.length) })],
  [/\/admin\/dashboard\/inventory\/restock-list$/, () => ({ items: INVENTORY.map((x, i) => ({
      kind: 'product', product_id: x.product_id, sku: x.sku, product_slug: x.slug, product_name: x.name,
      stock_quantity: x.stock_quantity, reserved_in_carts: x.reserved, reserved_in_orders: 0,
      available_quantity: x.stock_quantity - x.reserved, threshold: 5, is_critical: x.status === 'low',
      restock_at: null, supplier: 'Studio Supply Co', desired_quantity: 20, note: null,
    })), meta: { page: 1, limit: 20, total_items: INVENTORY.length, total_pages: 1 } })],
  [/\/admin\/dashboard\/low-stock$/, () => ([])],
  [/\/support\/admin\/assignees$/, () => ([{ id: 'u-owner-1', username: 'owner', name: 'Adriana Owner' }])],
  [/\/support\/admin\/submissions$/, () => ({ items: Array.from({ length: 5 }).map((_, i) => ({
      id: `s-${i + 1}`, topic: ['order', 'product', 'general', 'shipping', 'other'][i % 5],
      status: ['new', 'open', 'pending', 'resolved', 'closed'][i % 5], name: `Customer ${i + 1}`,
      email: `cust${i + 1}@example.com`, order_reference: i % 2 === 0 ? `MS-2026-10${i + 1}` : null,
      assignee: i % 2 === 0 ? { id: 'u-owner-1', username: 'owner', name: 'Adriana Owner' } : null, created_at: daysAgo(i),
    })), meta: meta(5) })],
  [/\/admin\/dashboard\/content$/, () => ({ items: CONTENT_PAGES, meta: meta(CONTENT_PAGES.length) })],
  [/\/admin\/dashboard\/search$/, () => ({ products: [], orders: [], users: [] })],
  [/\/admin\/dashboard\/stock-adjustments$/, () => ({ items: [], meta: meta(0) })],
  [/\/admin\/dashboard\/audit(\/entries)?$/, () => ({ items: [], meta: meta(0) })],
  [/\/products\/by-ids$/, () => ({ items: PRODUCTS.slice(0, 3) })],
  [/\/orders\/admin\/[^/]+\/(notes|refunds|email-events|tags|shipments|documents)$/, () => ([])],
  [/\/orders\/admin\/[^/]+$/, () => ({ ...ORDERS[0],
    items: [{ id: 'oi-1', product_name: PRODUCTS[0].name, name: PRODUCTS[0].name, quantity: 2, unit_price: 120, currency: 'RON', sku: 'MS-VAS-001' }],
    shipping_address: { name: 'Customer 1', line1: '1 Art St', city: 'Bucharest', country: 'RO', postal_code: '010101' },
    billing_address: { name: 'Customer 1', line1: '1 Art St', city: 'Bucharest', country: 'RO', postal_code: '010101' },
    timeline: [], events: [], notes: [], admin_notes: [], refunds: [], fraud_signals: [], shipments: [],
    tags: ['vip'], email_events: [], documents: [], payments: [], adjustments: [], history: [], returns: [] })],
  [/\/orders\/admin\/exports?$/, () => ({ items: [], meta: meta(0) })],
  [/\/orders\/admin\/search$/, () => ({ items: ORDERS.map((o) => ({
      id: o.id, reference_code: o.order_number, status: o.status, total_amount: o.total_amount, currency: 'RON',
      payment_method: ['card', 'paypal'][o.items_count % 2], created_at: o.created_at, customer_email: o.customer_email,
      customer_username: o.customer, tags: ['vip'], fraud_flagged: false, sla_overdue: false,
    })), meta: meta(ORDERS.length) })],
  [/\/orders\/admin/, () => ({ items: ORDERS, meta: meta(ORDERS.length) })],
  [/\/returns\/admin\/by-order\//, () => ([])],
  [/\/returns\/admin/, () => ({ items: RETURNS.map((r) => ({
      id: r.id, order_id: r.order_id, order_reference: r.order_number, customer_email: `${r.customer.replace(/\s/g, '').toLowerCase()}@example.com`,
      customer_name: r.customer, status: r.status, created_at: r.created_at,
    })), meta: meta(RETURNS.length) })],
  [/\/coupons\/admin\/promotions$/, () => ([])],
  [/\/coupons\/admin\/coupons\/bulk-jobs$/, () => ({ items: [], meta: meta(0) })],
  [/\/coupons\/admin\/coupons/, () => ({ items: COUPONS, meta: meta(COUPONS.length) })],
  [/\/content\/admin\/pages\/list$/, () => CONTENT_PAGES.map((p, i) => ({ key: p.key, slug: p.key.replace('page.', ''), title: p.title, status: 'published', hidden: false, updated_at: p.updated_at, published_at: p.published_at, needs_translation_ro: i % 2 === 0 }))],
  [/\/content\/admin\/media\/(assets|collections|jobs)$/, () => ({ items: [], meta: meta(0) })],
  [/\/content\/admin\/media\/telemetry$/, () => ({ total_assets: 0, total_bytes: 0, jobs_pending: 0 })],
  [/\/content\/admin\/media\/retry-policies$/, () => ({ items: [] })],
  [/\/content\/admin\/redirects$/, () => ({ items: [], meta: meta(0) })],
  [/\/content\/admin\/scheduling$/, () => ({ items: [], meta: meta(0) })],
  [/\/content\/admin\/[^/]+\/versions$/, () => ({ items: [], meta: meta(0) })],
  [/\/content\/admin\/home/, () => ({ id: 'c-home', key: 'home', title: 'Home', body_markdown: '# Welcome\n\nHand-made art.', version: 3, updated_at: daysAgo(1), status: 'published', meta: { hero: { title: 'momentstudio' }, sections: [] } })],
  [/\/content\/admin\//, () => ({ id: 'c-x', key: 'page.about', title: 'About', body_markdown: '# About\n\nOur story.', version: 2, updated_at: daysAgo(2), status: 'published', meta: {} })],
  [/\/blog\/admin\/comments\/flagged$/, () => ({ items: [], meta: meta(0) })],
  [/\/blog\/posts$/, () => ({ items: BLOG_POSTS, meta: meta(BLOG_POSTS.length) })],
  [/\/blog\/me\/comments$/, () => ({ items: [], meta: meta(0) })],
  [/\/admin\/users\/segments/, () => ({ items: USERS.slice(0, 4).map((u) => ({ ...u, total_spent: u.total_spent })), meta: meta(4) })],
  [/\/admin\/users/, () => ({ items: USERS, meta: meta(USERS.length) })],
  [/\/admin\/observability\/client-errors$/, () => ({ items: [], meta: meta(0) })],
  [/\/admin\/shipping\/sameday-sync\/status$/, () => ({ last_run: null, lockers: 0, status: 'idle' })],
  [/\/ops\/admin\/banners$/, () => ({ items: [], meta: meta(0) })],
  [/\/ops\/admin\/email-events$/, () => ([])],
  [/\/ops\/admin\/email-failures$/, () => ({ items: [], meta: meta(0) })],
  [/\/ops\/admin\/webhooks$/, () => ({ items: [], meta: meta(0) })],
  [/\/me\/addresses$/, () => ([])],
  [/\/gdpr\/(deletions|exports)/, () => ({ items: [], meta: meta(0) })],
  [/\/export\/jobs/, () => ({ items: [], meta: meta(0) })],
];

export function resolveMock(method, pathname) {
  const key = `${method} ${pathname}`;
  if (key in EXACT) return EXACT[key];
  for (const [re, fn] of PATTERNS) if (re.test(pathname)) return fn();
  // Smart default: admin/list-ish → envelope; else empty object.
  if (/admin|coupons|orders|returns|users|products|blog|content|notifications|ops/.test(pathname)) {
    return { items: [], meta: meta(0) };
  }
  return {};
}
