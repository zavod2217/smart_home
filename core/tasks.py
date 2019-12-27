from __future__ import absolute_import, unicode_literals
from celery import task
from .models import Setting, Controller
from django.core.mail import send_mail
import requests
import json


@task(default_retry_delay=10)
def get_data_controller():
    """обновленире данных с контроллера каждую секунду"""
    headers = {"Authorization": "Bearer ed9efa2161b1a262095a516277aeed3e27cee48fc08abe9ac2dc186eb2eefb2a"}
    try:
        result = requests.get("https://smarthome.webpython.graders.eldf.ru/api/user.controller", headers=headers)
    except Exception as e:
        print(f"API error: {e}")
        return
    try:
        result = dict(json.loads(result.text))
        if result["status"] == "ok":
            for item in result["data"]:
                data = {"controller_name": item["name"], "value": item["value"]}
                Controller.objects.update_or_create(controller_name=item["name"], defaults=data)
    except Exception as e:
        print(f"Ошибка обработки данных: {e}")


@task()
def switch(params: dict, user=False):
    """Функция выставляет данные в контроллерах по API. user - пользователь или автоматическая система изменяет
    param = {
      "name": "air_conditioner",
      "value": True
    }
    """

    if user:
        if Controller.objects.get(controller_name="smoke_detector").value == "True":
            return

    headers = {'Content-type': 'application/json',
               "Authorization": "Bearer ed9efa2161b1a262095a516277aeed3e27cee48fc08abe9ac2dc186eb2eefb2a"}

    data = {"controllers": []}
    try:
        for key, val in params.items():
            data["controllers"].append({"name": f"{key}", "value": val})
        requests.post("https://smarthome.webpython.graders.eldf.ru/api/user.controller", headers=headers, json=data)
    except Exception as e:
        print(f"API error: {e}")


@task()
def send_email():
    send_mail("Пожар ! Беги !!!", "leak_detector@temp.ru", ["user@temp.ru"])


@task()
def smart_home_manager():
    # Здесь проверка условий
    controllers = Controller.objects.all().values("controller_name", "value")
    settings = Setting.objects.all().values("controller_name", "value")
    settings = dict([(i["controller_name"], int(i["value"])) for i in settings])

    all_controllers = dict([(i["controller_name"], i["value"].replace("None", "0")) for i in controllers])
    all_controllers.update(settings)

    for key, val in all_controllers.items():
        if str(val).isdigit():
            all_controllers[key] = int(val)

    """Если есть протечка воды (leak_detector=true), закрыть холодную (cold_water=false) и горячую (hot_water=false)
    воду и отослать письмо в момент обнаружения."""
    if all_controllers["leak_detector"] == "True":
        switch({"cold_water": "false", "hot_water": "false"})
        send_email()

    """Если холодная вода (cold_water) закрыта, немедленно выключить бойлер (boiler) и стиральную машину 
    (washing_machine) и ни при каких условиях не включать их, пока холодная вода не будет снова открыта."""
    if all_controllers["cold_water"] == "False":
        switch({"boiler": "false", "washing_machine": "off"})

    """Если горячая вода имеет температуру (boiler_temperature) меньше чем hot_water_target_temperature - 10%, нужно 
    включить бойлер (boiler), и ждать пока она не достигнет температуры hot_water_target_temperature + 10%, после чего 
    в целях экономии энергии бойлер нужно отключить"""
    target = int(all_controllers["hot_water_target_temperature"]) - (int(all_controllers["hot_water_target_temperature"]) * 0.1)
    if all_controllers["cold_water"] == "True" and int(all_controllers["boiler_temperature"]) < target and all_controllers["smoke_detector"] == "False":
        switch({"boiler": "true"})
    target = int(all_controllers["hot_water_target_temperature"]) + (int(all_controllers["hot_water_target_temperature"]) * 0.1)
    if all_controllers["boiler_temperature"] > target:
        switch({"boiler": "false"})

    """Если шторы частично открыты (curtains == “slightly_open”), то они находятся на ручном управлении - это значит 
    их состояние нельзя изменять автоматически ни при каких условиях."""

    """Если на улице (outdoor_light) темнее 50, открыть шторы (curtains), но только если не горит лампа в спальне 
    (bedroom_light). Если на улице (outdoor_light) светлее 50, или горит свет в спальне (bedroom_light), закрыть шторы.
     Кроме случаев когда они на ручном управлении"""
    if all_controllers["outdoor_light"] < 50 and all_controllers['bedroom_light'] == "False":
        switch({"curtains": "open"})
    if all_controllers["outdoor_light"] > 50 or all_controllers["bedroom_light"] == "True" and all_controllers["curtains"] == "slightly_open":
        switch({"curtains": "close"})

    """Если обнаружен дым (smoke_detector), немедленно выключить следующие приборы [air_conditioner, bedroom_light, 
    bathroom_light, boiler, washing_machine], и ни при каких условиях не включать их, пока дым не исчезнет."""
    if all_controllers["smoke_detector"] == "True":
        switch({"air_conditioner": "false", "bedroom_light": "false", "bathroom_light": "false", "boiler": "false",
                "washing_machine": "off"})

    """Если температура в спальне (bedroom_temperature) поднялась выше bedroom_target_temperature + 10% - включить 
    кондиционер (air_conditioner), и ждать пока температура не опустится ниже bedroom_target_temperature - 10%, 
    после чего кондиционер отключить"""
    target = all_controllers["bedroom_target_temperature"] - (all_controllers["bedroom_target_temperature"] * 0.1)
    if all_controllers["bedroom_temperature"] < target:
        switch({"air_conditioner": "false"})
    target = all_controllers["bedroom_target_temperature"] + (all_controllers["bedroom_target_temperature"] * 0.1)
    if all_controllers["bedroom_temperature"] > target and all_controllers["smoke_detector"] == "False":
        switch({"air_conditioner": "true"})
