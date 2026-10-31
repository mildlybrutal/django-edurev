from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("clusters", views.SkillClusterViewSet, basename="skill-cluster")
router.register("roles", views.TargetRoleViewSet, basename="target-role")
router.register("", views.SkillViewSet, basename="skill")

urlpatterns = router.urls
