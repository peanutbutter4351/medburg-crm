"""
core/apps.py
━━━━━━━━━━━━
Django AppConfig for the core infrastructure app.

'core' is the shared foundation for all business apps — it owns:
  - BaseModel          (abstract timestamped base)
  - ImportLog          (import audit model)
  - BaseExcelImporter  (reusable Excel import engine)
  - constants          (shared choice constants)
  - decorators         (RBAC/role decorators)
  - services           (shared utility services)

This AppConfig registers 'core' with Django's app registry so that:
  - ImportLog migrations are discovered and applied
  - Django admin picks up core/admin.py
  - The app label is explicit and stable
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    # Use BigAutoField consistently with the project default
    default_auto_field = "django.db.models.BigAutoField"

    # Module path — must match the package directory name
    name = "core"

    # Human-readable label shown in Django admin and error messages
    verbose_name = "Core Infrastructure"

    def ready(self):
        from django.contrib import admin
        
        def get_custom_app_list(self, request, app_label=None):
            app_dict = self._build_app_dict(request)

            models_by_name = {}
            for app in app_dict.values():
                for model in app['models']:
                    models_by_name[model['object_name']] = model

            def get_model(name):
                return models_by_name.get(name)

            custom_app_list = [
                {
                    "name": "Users & Authorization",
                    "app_label": "auth",
                    "app_url": "",
                    "has_module_perms": True,
                    "models": [get_model("User"), get_model("Group")],
                },
                {
                    "name": "Master Data",
                    "app_label": "master_data",
                    "app_url": "",
                    "has_module_perms": True,
                    "models": [get_model("Medicine"), get_model("PrepaidDoctor"), get_model("PostpaidDoctor"), get_model("ImportLog")],
                },
                {
                    "name": "Prepaid Engine",
                    "app_label": "prepaid_engine",
                    "app_url": "",
                    "has_module_perms": True,
                    "models": [get_model("Investment"), get_model("SalesEntry")],
                },
                {
                    "name": "Postpaid Engine",
                    "app_label": "postpaid_engine",
                    "app_url": "",
                    "has_module_perms": True,
                    "models": [get_model("PostpaidCampaign"), get_model("PostpaidSaleEntry"), get_model("CampaignPayment"), get_model("PostpaidCampaignCorrection")],
                },
            ]

            final_app_list = []
            for app in custom_app_list:
                valid_models = [m for m in app['models'] if m is not None]
                if valid_models:
                    app['models'] = valid_models
                    final_app_list.append(app)
            
            return final_app_list

        admin.site.__class__.get_app_list = get_custom_app_list
