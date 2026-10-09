import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html, format_html_join
from django.views.decorators.http import require_http_methods

from .forms import TaskForm
from .models import Task

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
def index(request):
    form = TaskForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        task = form.save()
        logger.info("Task created id=%s", task.pk)
        return redirect("list")

    return render(request, "tasks/list.html", {
        "tasks": Task.objects.all(),
        "form": form,
        "welcome_message": "Bienvenue sur votre TO DO LIST !",
    })


@require_http_methods(["GET", "POST"])
def updateTask(request, pk):
    task = get_object_or_404(Task, pk=pk)
    form = TaskForm(
        request.POST if request.method == "POST" else None,
        instance=task,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        logger.info("Task updated id=%s", task.pk)
        return redirect("list")

    return render(request, "tasks/update_task.html", {"form": form})


@require_http_methods(["GET", "POST"])
def deleteTask(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        task_id = task.pk
        task.delete()
        logger.info("Task deleted id=%s", task_id)
        return redirect("list")

    return render(request, "tasks/delete.html", {"item": task})


@require_http_methods(["GET"])
def search_tasks(request):
    query = request.GET.get("q", "")[:200]
    tasks = Task.objects.filter(title__icontains=query)[:100]
    results = format_html_join(
        "", "<li>{}</li>", ((task.title,) for task in tasks)
    )
    return HttpResponse(format_html("<ul>{}</ul>", results))


def validate_import(raw_data):
    if len(raw_data) > 100000:
        raise ValueError("Import trop volumineux.")

    titles = json.loads(raw_data)
    if not isinstance(titles, list) or len(titles) > 100:
        raise ValueError("Fournir une liste JSON de 100 titres maximum.")

    forms = []
    for title in titles:
        if not isinstance(title, str):
            raise ValueError("Chaque titre doit etre une chaine.")
        form = TaskForm(data={"title": title, "complete": False})
        if not form.is_valid():
            raise ValueError("Un titre est vide ou invalide.")
        forms.append(form)
    return forms


@require_http_methods(["GET", "POST"])
def import_tasks(request):
    if request.method == "GET":
        return render(request, "tasks/import.html")

    try:
        forms = validate_import(request.POST.get("tasks_data", ""))
    except ValueError:
        return HttpResponseBadRequest(
            "Import invalide : fournir une liste JSON de titres valides "
            "(100 maximum, 100000 caracteres maximum)."
        )

    with transaction.atomic():
        for form in forms:
            form.save()
    logger.info("Tasks imported count=%s", len(forms))
    return redirect("list")


@staff_member_required
@require_http_methods(["GET"])
def admin_panel(request):
    return HttpResponse("Bienvenue dans le panneau administrateur.")