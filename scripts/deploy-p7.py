#!/usr/bin/env python3
"""
NemoClaw P-7 Deployment: Security Headers Middleware

Patches: main.py (add SecurityHeadersMiddleware class + register)

Run from repo root:
    cd ~/nemoclaw-local-foundation
    python3 scripts/deploy-p7.py
"""

from pathlib import Path
import sys

BACKEND = Path.home() / "nemoclaw-local-foundation" / "command-center" / "backend"


def deploy():
    errors = []
    main_path = BACKEND / "app" / "main.py"

    print("1/1 Patching main.py...")
    content = main_path.read_text()

    # Patch 1: Add imports
    old_import = "from fastapi.middleware.cors import CORSMiddleware"
    new_import = """from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse"""

    if "BaseHTTPMiddleware" not in content:
        if old_import in content:
            content = content.replace(old_import, new_import)
        else:
            errors.append("Import patch target not found")
            print("  ❌ Import target missing")
    else:
        print("  ⚠️ Imports already present")

    # Patch 2: Add middleware class + registration after CORS
    old_cors = '''# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)'''

    new_cors = '''# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── P-7: Security Headers Middleware ──
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every HTTP response."""

    HEADERS = {
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self' ws: wss:"
        ),
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }

    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)
        for header, value in self.HEADERS.items():
            response.headers[header] = value
        return response


app.add_middleware(SecurityHeadersMiddleware)'''

    if "SecurityHeadersMiddleware" not in content:
        if old_cors in content:
            content = content.replace(old_cors, new_cors)
        else:
            errors.append("CORS block patch target not found")
            print("  ❌ CORS target missing")
    else:
        print("  ⚠️ Middleware already present")

    main_path.write_text(content)
    try:
        compile(main_path.read_text(), str(main_path), "exec")
        print("  ✅ main.py compiles")
    except SyntaxError as e:
        errors.append(f"main.py: {e}")
        print(f"  ❌ {e}")

    print()
    if errors:
        print(f"⛔ {len(errors)} ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ P-7 deployed successfully")
        print()
        print("Restart backend, then validate:")
        print()
        print('  TOKEN=$(cat ~/.nemoclaw/cc-token)')
        print()
        print('  # Check security headers')
        print('  curl -sI -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8100/api/health | grep -iE "strict-transport|x-content-type|x-frame|referrer-policy|content-security|permissions-policy|x-xss"')
        print()
        print('  # CORS still works')
        print('  curl -sI -H "Origin: http://localhost:3000" http://127.0.0.1:8100/api/health | grep -i "access-control"')
        print()
        print('  cd ~/nemoclaw-local-foundation && bash scripts/full_regression.sh')
        print()
        print('  git add -A && git status')
        print('  git commit -m "feat(engine): P-7 security headers middleware — HSTS, CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy"')
        print('  git push origin main')


if __name__ == "__main__":
    deploy()
