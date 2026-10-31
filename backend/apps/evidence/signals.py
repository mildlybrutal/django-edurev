import django.dispatch

# Sent after a student's evidence set or verification state changes. The profile module
# listens and schedules a (debounced) skill-profile and readiness recompute.
evidence_changed = django.dispatch.Signal()
