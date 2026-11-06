from routes import admin, auth, dashboard, enrollments, import_routes, measures, participants, reports

BLUEPRINTS = [
    auth.bp,
    participants.bp,
    measures.bp,
    enrollments.bp,
    dashboard.bp,
    reports.bp,
    import_routes.bp,
    admin.bp,
]


def register_blueprints(app):
    for bp in BLUEPRINTS:
        app.register_blueprint(bp)
