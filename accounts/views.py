from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import ParentRegistrationForm


def register(request):
    """家長註冊，成功後直接登入並導向新增第一個孩子。"""
    if request.user.is_authenticated:
        return redirect("questionnaires:parent-home")

    if request.method == "POST":
        form = ParentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("questionnaires:child-add")
    else:
        form = ParentRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})
