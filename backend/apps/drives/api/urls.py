from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("companies", views.CompanyViewSet, basename="company")
router.register("", views.DriveViewSet, basename="drive")
urlpatterns = router.urls
