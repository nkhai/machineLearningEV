# ──────────────────────────────────────────────────────────────────
# How to run
# ──────────────────────────────────────────────────────────────────
#
# Option 1 — Docker (recommended)
#   docker build -t aiapi-backend .
#   docker compose up -d
#
# Option 2 — Local (requires Python 3.10+ and GPU driver)
#   cp .env.example .env               # edit proxy / DB / HDFS creds
#   pip install -r requirements.txt
#   PYTHONPATH=../ev_client_app:$PYTHONPATH
#     uvicorn main:app --host 0.0.0.0 --port 8000 --reload
#
#   env AUTH_ENABLED=false              # skip Azure AD, use template user
# ──────────────────────────────────────────────────────────────────
from fastapi import FastAPI, Security
from fastapi.middleware.cors import CORSMiddleware
from api.train import router as predict_router
from api.train_pipeline import router as train_router
from api.xgb_train import router as xgb_train_router
from api.xgb_predict import router as xgb_predict_router
from api.jobs import router as jobs_router
from api.vehicles import router as vehicles_router
from core.auth import azure_scheme, APP_CLIENT_ID, AUTH_ENABLED, TEMPLATE_USER_ID
from core.database import engine, Base, SessionLocal
from core.models import User
import core.models  # noqa: F401 — register ORM models with Base

# ── Auth is DISABLED — all /api/v1/* routes use the template user fallback ──
# auth_deps = [Security(azure_scheme)] if AUTH_ENABLED else []
auth_deps = []  # Azure AD commented out; set AUTH_ENABLED=true to re-enable

app = FastAPI(
    title="EV Battery Health Prediction API",
    description="Backend API for predicting EV battery health using pre-trained models",
    version="1.0.0",
    # swagger_ui_init_oauth={            # Azure AD commented out
    #     "usePkceWithAuthorizationCodeGrant": True,
    #     "clientId": APP_CLIENT_ID,
    # } if AUTH_ENABLED else None,
    swagger_ui_init_oauth=None,            # set to the dict above when re-enabling auth
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API routes require Azure AD authentication (when enabled)
app.include_router(predict_router, prefix="/api/v1", dependencies=auth_deps)
app.include_router(train_router, prefix="/api/v1", dependencies=auth_deps)
app.include_router(xgb_train_router, prefix="/api/v1", dependencies=auth_deps)
app.include_router(xgb_predict_router, prefix="/api/v1", dependencies=auth_deps)
app.include_router(jobs_router, prefix="/api/v1", dependencies=auth_deps)
app.include_router(vehicles_router, prefix="/api/v1", dependencies=auth_deps)


@app.on_event("startup")
async def startup():
    # Create tables if they don't exist (like JPA ddl-auto=update)
    Base.metadata.create_all(bind=engine)

    # ── Migration: add use_to_predict column if missing ──
    with engine.connect() as conn:
        import sqlalchemy as sa
        inspector = sa.inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("vehicles")}
        if "use_to_predict" not in cols:
            conn.execute(sa.text("ALTER TABLE vehicles ADD COLUMN use_to_predict BOOLEAN NOT NULL DEFAULT TRUE"))
            conn.commit()

    # Seed admin user if not present
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.user_id == "vkn1hc").first():
            db.add(User(
                user_id="vkn1hc",
                user_name="Vo Nguyen Khai",
                pw="",
                phone_number=None,
                role="Admin",
            ))
            db.commit()

        # Seed template user when auth is disabled
        if not AUTH_ENABLED:
            if not db.query(User).filter(User.user_id == TEMPLATE_USER_ID).first():
                db.add(User(
                    user_id=TEMPLATE_USER_ID,
                    user_name="Template User",
                    pw="",
                    phone_number=None,
                    role="Admin",
                ))
                db.commit()
    finally:
        db.close()

    # ── Azure AD OpenID config loading DISABLED ──
    # if AUTH_ENABLED:
    #     await azure_scheme.openid_config.load_config()


@app.get("/health")
def health_check():
    return {"status": "ok"}
