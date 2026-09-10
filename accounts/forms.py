from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from children.models import Child


class ParentRegistrationForm(UserCreationForm):
    """家長註冊。沿用 Django 內建 User，僅多收 email。

    院方 APP 介接後家長身分會改由 APP 帶入，這個表單只供展示與測試。
    """

    email = forms.EmailField(label="電子郵件", required=True)
    full_name = forms.CharField(label="姓名", max_length=60, required=True)

    class Meta:
        model = User
        fields = ("username", "full_name", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["full_name"]
        if commit:
            user.save()
        return user


class ChildForm(forms.ModelForm):
    class Meta:
        model = Child
        fields = ("name", "birth_date", "medical_no", "tracking_status")
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "medical_no": "病歷號（選填）",
            "tracking_status": "追蹤狀態（選填）",
        }
        help_texts = {
            "tracking_status": "例如：一般、氣喘追蹤、早療追蹤",
        }
