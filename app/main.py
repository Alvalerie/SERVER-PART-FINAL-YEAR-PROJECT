from fastapi import FastAPI

from .config.settings import settings
from .routers.user import router as user_router
from .routers.student import router as student_router
from .routers.course import router as course_router
from .routers.student_course import router as student_course_router
from .routers.image import router as image_router



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
app.include_router(image_router)

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}