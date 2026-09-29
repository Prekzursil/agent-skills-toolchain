# Two parts: PART A writes one skeleton file (exact content given), PART B gathers read-only evidence. HARD RULES: no git 

- runtime: claude
- session date: 2026-09-22 18:09
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil-Documents-GitHub-WebCoder\86b9d1a8-40b5-4757-b206-7ef1dc45292b.jsonl`
- distilled: 2026-09-28T05:42:37
- backend: claude

## create_summary

**Purpose:** A queued, strictly read-only security audit of WebCoder's Django backend and React frontend auth (branch `wave/nextjs-migration`, commit `40fda968`), writing one 13-finding skeleton report plus gathering verification evidence.

## Key points

1. Two-part task: PART A writes `docs/SECURITY-AUDIT-auth.md` verbatim; PART B gathers read-only evidence.
2. Hard rules: no git writes, no edits beyond that one file, no installs/builds/servers, searches depth ≤ 4.
3. Scope: `settings.py` (302 lines), `requirements.txt`, `AuthContext.tsx` (85 lines), URL wiring.
4. CRITICAL: `DEBUG=True` hardcoded (settings.py:37); HIGH: `ALLOWED_HOSTS` empty (settings.py:39).
5. HIGH: access and refresh JWTs persisted in `localStorage`, XSS-stealable (AuthContext.tsx:17-18).
6. HIGH: GitHub OAuth `repo` scope, no refresh rotation/blacklist, logout leaves refresh token valid 24h.
7. Positives: fail-loud SECRET_KEY/DB_PASSWORD env reads, `.env` gitignored, narrow explicit CORS origins.
8. `manage.py check` failed earlier on missing SECRET_KEY; retry uses process-local dummy env.
9. PART B: verbatim check/`--deploy` output (60-line cap), full urls.py, users app files, frontend Bearer grep.
10. Skeleton sections start UNKNOWN and are non-citable until measured; hardening list finalizes in v2.

## Takeaways

1. Splitting a durable findings skeleton from live evidence collection keeps unmeasured claims explicitly marked.
2. Process-local dummy env vars unblock Django checks without persisting any credentials.
3. JWT lifecycle — storage, rotation, server-side logout — forms the dominant frontend+backend risk cluster.
4. Guardrails (skip-if-exists, all-UNKNOWN non-citable warning) prevent overwriting or misquoting stale verdicts.
5. Enforced read-only constraints (no git writes, scoped searches, line caps, factual route mapping) keep audits non-invasive.

## extract_wisdom

Report per the task contract. Note on staleness: this chunk was queued 2026-09-22 15:02 and is being executed 2026-09-28; repo HEAD is now `fb82580c` (≠ audited commit `40fda968`), so all PART B evidence reflects **fb82580c**, not the audited commit. I executed anyway because PART A carried its own existence guard and PART B is read-only. No git writes, no installs, no edits outside the (skipped) PART A file.

## PART A

**File created: NO.** `docs\SECURITY-AUDIT-auth.md` **already exists** — 20,127 bytes, LastWrite 2026-09-22 18:18:45 (written *after* this chunk was queued at 15:02, i.e. a later unit already produced it). Per the task's own guard: not modified, PART A skipped entirely.

## B1 — manage.py check (dummy process-local env)

Exit codes: `check` = **1**, `check --deploy` = **1**. Verbatim outputs:

```
=== manage.py check (exit 1) ===
SystemCheckError: System check identified some issues:

CRITICALS:
?: 'password' is not a valid field for ACCOUNT_SIGNUP_FIELDS, use 'password1'

WARNINGS:
?: (account.W001) ACCOUNT_LOGIN_METHODS conflicts with ACCOUNT_SIGNUP_FIELDS
?: settings.ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE is deprecated, use: settings.ACCOUNT_SIGNUP_FIELDS = ['username', 'email', 'password']

System check identified 3 issues (0 silenced).

=== manage.py check --deploy (exit 1) ===
SystemCheckError: System check identified some issues:

CRITICALS:
?: 'password' is not a valid field for ACCOUNT_SIGNUP_FIELDS, use 'password1'

WARNINGS:
?: (account.W001) ACCOUNT_LOGIN_METHODS conflicts with ACCOUNT_SIGNUP_FIELDS
?: (security.W004) You have not set a value for the SECURE_HSTS_SECONDS setting. [...]
?: (security.W008) Your SECURE_SSL_REDIRECT setting is not set to True. [...]
?: (security.W009) Your SECRET_KEY has less than 50 characters, less than 5 unique characters, or it's prefixed with 'django-insecure-' [...]
?: (security.W012) SESSION_COOKIE_SECURE is not set to True. [...]
?: (security.W016) You have 'django.middleware.csrf.CsrfViewMiddleware' in your MIDDLEWARE, but you have not set CSRF_COOKIE_SECURE to True. [...]
?: (security.W018) You should not have DEBUG set to True in deployment.
?: (security.W020) ALLOWED_HOSTS must not be empty in deployment.
?: settings.ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE is deprecated, use: settings.ACCOUNT_SIGNUP_FIELDS = ['username', 'email', 'password']

System check identified 10 issues (0 silenced).
```
(`--deploy` output was 24 lines — under the 60-line cap; `[...]` above are my elisions of boilerplate only, full text is in the tool result.) **Caveats:** W009 is an artifact of the dummy `SECRET_KEY` I injected, not a repo finding. W018/W020 corroborate skeleton findings A-01/A-02. The allauth CRITICAL + W001 + deprecation are **new measured findings** not in the skeleton's table.

## B2 — webcoder_api/urls.py (43 lines, full)

Printed verbatim with line numbers in the Read result above. Key wiring: lines 34-36 simplejwt token/refresh/verify; 38-39 dj_rest_auth + registration includes; 40-41 google/github OAuth includes; 42 allauth.

## B3 — users app

`backend/users/` (depth 1, dirs+files): `migrations/`, `management/commands/`, `api/oauth/{google,github}/`, `__pycache__/`, plus `__init__.py, adapters.py, admin.py, apps.py, models.py, serializers.py, tests.py, test_wave.py, urls.py, utils.py, views.py, permissions.py`.

All four requested files exist and were printed **in full** via Read above, none truncated (all under the 250-line cap): `urls.py` 19 lines, `views.py` 112, `serializers.py` 107, `adapters.py` 36.

## B4 — frontend auth-token usage

Matches (case-insensitive, full list, see Grep result for ±3-line context):

1. `src/context/AuthContext.tsx` — :8 `refreshToken` in context type; :17-18 tokens initialized from `localStorage`; :39-44 purge on failed user fetch; :52-58 `login()` persists access/refresh/user to `localStorage`; :59 `console.log` of userData; :62-70 `logout()` is localStorage/state-only, :69 `console.log`; :73 provider value.
2. `src/pages/auth/CompleteRegistrationPage.tsx` — :32-33 passes `response.refresh` into `auth.login`.
3. `src/types/api.ts` — :9-13 `LoginResponse { access, refresh, user }`.
4. `src/services/ApiService.ts` — :4 reads `localStorage.getItem('accessToken')`; :7 `headers.set('Authorization', \`Bearer ${token}\`)`.
5. `src/pages/auth/LoginPage.tsx` — :25-26 passes access/refresh into `auth.login`.

`src/services/` contains only `ApiService.ts`; **`src/api` does not exist**. Notable absence: zero matches for `axios` or `interceptors` anywhere in `src`, and no code path calls `/api/v1/token/refresh/` — the refresh token is stored but never used by the frontend.

## B5 — route → view mapping (from printed urls.py content only)

| Route | View/source |
|---|---|
| `/api/v1/token/` | `TokenObtainPairView` (simplejwt, urls.py:34) |
| `/api/v1/token/refresh/` | `TokenRefreshView` (simplejwt, :35) |
| `/api/v1/token/verify/` | `TokenVerifyView` (simplejwt, :36) |
| `/api/v1/auth/` | `include('dj_rest_auth.urls')` (:38) — internal routes not printed here |
| `/api/v1/auth/registration/` | `include('dj_rest_auth.registration.urls')` (:39) |
| `/api/v1/auth/google/` | `include('users.api.oauth.google.urls')` (:40) |
| `/api/v1/auth/github/` | `include('users.api.oauth.github.urls')` (:41) |
| `/accounts/` | `include('allauth.urls')` (:42) |
| `/api/v1/users/register/` | `UserRegistrationView` (AllowAny) |
| `/api/v1/users/me/` | `UserMeView` (IsAuthenticated) |
| `/api/v1/users/password/change/` | `PasswordChangeView` (IsAuthenticated) |
| `/api/v1/users/admin/stats/` | `AdminStatsView` (IsAdminUser) |
| `/api/v1/users/` (router) | `UserViewSet` (ReadOnly; IsOwnerOrAdminForUser override on write actions per views.py:68-71) |
| `/api/v1/users/admin/manage/` (router) | `AdminUserViewSet` (IsAdminUser) |

- **`rest_framework.authtoken` / `obtain_auth_token`: NOT wired** anywhere in printed content.
- **No logout/blacklist endpoint of any kind appears in the printed urls.py content** — no `TokenBlacklistView` route is wired, so (consistent with skeleton A-06) there is no reachable server-side logout/blacklist path visible in routing. `GoogleLogin`/`GithubLogin` are defined in `users/views.py:85-93` and imported in `users/urls.py:3` but are **not routed there** — they ride the separate `api/oauth/*/urls.py` includes.
