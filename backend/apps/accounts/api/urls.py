from django.urls import path

from . import signup, views

app_name = "auth"

urlpatterns = [
    path("csrf/", views.CsrfView.as_view(), name="csrf"),
    path("signup-options/", signup.SignupOptionsView.as_view(), name="signup-options"),
    path("signup/", signup.SignupView.as_view(), name="signup"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("refresh/", views.RefreshView.as_view(), name="refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("mfa/verify/", views.MFAVerifyView.as_view(), name="mfa-verify"),
    path("mfa/setup/", views.MFASetupView.as_view(), name="mfa-setup"),
    path("mfa/confirm/", views.MFAConfirmView.as_view(), name="mfa-confirm"),
    path("mfa/disable/", views.MFADisableView.as_view(), name="mfa-disable"),
]
