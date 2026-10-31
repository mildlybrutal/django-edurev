from rest_framework.routers import SimpleRouter

from .views import EvidenceViewSet

router = SimpleRouter()
router.register("", EvidenceViewSet, basename="evidence")
urlpatterns = router.urls
