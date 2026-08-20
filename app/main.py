from fastapi import FastAPI

from .config.settings import settings
from .routers.user import router as user_router
from .routers.student import router as student_router
from .routers.course import router as course_router
from .routers.student_course import router as student_course_router
from .routers.handwriting_sample import router as handwriting_sample_router
from .routers.auth import router as auth_router
from .routers.marking_session import router as marking_session_router
from .routers.script_capture import router as script_capture_router



app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)


# Routers
app.include_router(user_router)
app.include_router(student_router)
app.include_router(course_router)
app.include_router(student_course_router)
app.include_router(handwriting_sample_router)
app.include_router(auth_router)
app.include_router(marking_session_router)
app.include_router(script_capture_router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}