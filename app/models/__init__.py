from .user_model import User
from .audit_model import Audit
from .student_model import Student
from .course_model import Course
from .student_course_model import StudentCourse
from .image_model import Image

#note that we added these to prevent the circular import error. We can import the models here and then import this file in the repositories and services without any issues.