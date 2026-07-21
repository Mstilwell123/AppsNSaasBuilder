# Auth-Gated App Testing Playbook (Emergent Google Auth + Local Password)

Backend routes:
- POST /api/auth/session   (body: `{ session_id }`)  → sets `session_token` cookie
- GET  /api/auth/me
- POST /api/auth/logout
- POST /api/auth/change-password  (body: `{ current_password?, new_password }`)

Mongo collections:
- `users` — user_id (custom UUID), email, name, picture, password_hash, created_at, updated_at
- `user_sessions` — user_id, session_token, expires_at, created_at

## Step 1: Seed a test user + session directly in Mongo

```bash
mongosh --eval "
use('test_database');
var uid = 'test-user-' + Date.now();
var token = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: uid,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/150',
  password_hash: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString()
});
db.user_sessions.insertOne({
  user_id: uid,
  session_token: token,
  expires_at: new Date(Date.now() + 7*24*60*60*1000).toISOString(),
  created_at: new Date().toISOString()
});
print('Session token: ' + token);
print('User ID: ' + uid);
"
```

## Step 2: API test via curl (use Bearer since we can't set httpOnly cookies here)

```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
TOKEN="<paste session token from step 1>"

# me
curl -s "$API/api/auth/me" -H "Authorization: Bearer $TOKEN"

# set initial password (no current_password required)
curl -s -X POST "$API/api/auth/change-password" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"new_password":"correct-horse-battery-staple"}'

# change password (current required)
curl -s -X POST "$API/api/auth/change-password" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"current_password":"correct-horse-battery-staple","new_password":"newpass-9chars"}'

# wrong current password → 400
curl -s -X POST "$API/api/auth/change-password" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"current_password":"WRONG","new_password":"anotherpass9"}'

# short new password → 400
curl -s -X POST "$API/api/auth/change-password" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"current_password":"newpass-9chars","new_password":"short"}'
```

## Step 3: Browser (Playwright) with cookie

```python
await page.context.add_cookies([{
    "name": "session_token",
    "value": TOKEN,
    "domain": "<host from REACT_APP_BACKEND_URL without protocol>",
    "path": "/",
    "httpOnly": True,
    "secure": True,
    "sameSite": "None"
}])
await page.goto(FRONTEND_URL + "/settings")
```

## Test IDs on the Settings page
- `settings-profile-card`, `settings-profile-name`, `settings-profile-email`, `settings-profile-provider`
- `settings-password-card`
- `change-password-current-input` (only rendered once user has a password)
- `change-password-new-input`
- `change-password-confirm-input`
- `change-password-submit-button`
- `change-password-current-error`, `change-password-new-error`, `change-password-confirm-error`

## Cleanup

```bash
mongosh --eval "
use('test_database');
db.users.deleteMany({email: /test\\.user\\./});
db.user_sessions.deleteMany({session_token: /test_session/});
"
```

## Success indicators
- ✅ `/api/auth/me` returns user JSON (200)
- ✅ First change-password with no `current_password` succeeds; `has_password` becomes `true`
- ✅ Correct current password → 200; wrong current password → 400 "Current password is incorrect"
- ✅ `new_password` shorter than 8 → 400
- ✅ Password stored as bcrypt hash (starts with `$2b$`)
