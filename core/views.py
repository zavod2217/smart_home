from django.urls import reverse_lazy
from django.views.generic import FormView
from .models import Setting, Controller
from .form import ControllerForm
from .tasks import switch


class ControllerView(FormView):
    form_class = ControllerForm
    template_name = 'core/control.html'
    success_url = reverse_lazy('form')

    def get_context_data(self, **kwargs):
        """Выводим значнеие всех конролов"""
        context = super(ControllerView, self).get_context_data()
        data = Controller.objects.all()
        context['data'] = dict([(item.controller_name, item.value) for item in data])
        return context

    def get_initial(self):
        """при загрузке формы подставляем данные и из Setting и с Controller"""
        data_setting = Setting.objects.values("controller_name", "value")
        data_setting_dict = dict([item.values() for item in data_setting])

        data_controller = Controller.objects.filter(controller_name__in=["bedroom_light", "bathroom_light"]).values(
                                                                                            "controller_name", "value")
        data_controller_dict = dict([(item.get("controller_name"), eval(item.get("value"))) for item in data_controller])

        result = data_setting_dict.copy()
        result.update(data_controller_dict)

        return result

    def form_valid(self, form):
        """данные валидны, отправка bedroom_target_temperature, hot_water_target_temperature в Setting
        a bedroom_light, bathroom_light на сервер"""
        swith_data = {}
        for key, value in form.cleaned_data.items():
            if bool(value) and (key in ["bedroom_target_temperature", "hot_water_target_temperature"]):
                row = Setting.objects.get(controller_name=key)
                row.value = value
                row.save()
            if key in ["bedroom_light", "bathroom_light"]:
                swith_data.update({key: value})

        if bool(swith_data):
            # задача в celery, пусть отправляет изменения на сервер
            switch(swith_data, user=True)

        return super(ControllerView, self).form_valid(form)
