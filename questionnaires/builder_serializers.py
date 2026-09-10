"""問卷編輯器（後台 staff 用）的 serializers。

與 serializers.py（家長端唯讀 schema）分開：這裡是可寫的，且只作用於
草稿版本。
"""

from rest_framework import serializers

from .models import (
    BranchRule, Category, EligibilityRule, Option, Question,
    Questionnaire, QuestionnaireVersion, Section, Tier,
)


class OptionEditSerializer(serializers.ModelSerializer):
    # value 可留空，建立時自動以 opt1/opt2… 產生（醫護通常只想填「選項文字」）
    value = serializers.CharField(max_length=100, required=False, allow_blank=True)

    class Meta:
        model = Option
        fields = ("id", "label", "value", "order", "is_active")
        read_only_fields = ("id",)


class BranchRuleEditSerializer(serializers.ModelSerializer):
    # 給前端顯示用的人類可讀描述
    description = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = BranchRule
        fields = (
            "id", "trigger_question", "trigger_operator", "trigger_value", "action",
            "target_section", "target_question", "target_questionnaire", "description",
        )
        read_only_fields = ("id", "description")

    def validate(self, attrs):
        targets = [
            attrs.get("target_section", getattr(self.instance, "target_section", None)),
            attrs.get("target_question", getattr(self.instance, "target_question", None)),
            attrs.get("target_questionnaire", getattr(self.instance, "target_questionnaire", None)),
        ]
        if sum(1 for t in targets if t is not None) != 1:
            raise serializers.ValidationError("跳題目標必須且只能指定一個（題組／題目／問卷）。")
        return attrs


class QuestionEditSerializer(serializers.ModelSerializer):
    options = OptionEditSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = (
            "id", "section", "prompt", "help_text", "question_type",
            "required", "order", "is_active", "config", "options",
        )
        read_only_fields = ("id", "section", "options")


class SectionEditSerializer(serializers.ModelSerializer):
    questions = QuestionEditSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = ("id", "version", "title", "description", "order", "is_active", "questions")
        read_only_fields = ("id", "version", "questions")


class EligibilityRuleEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = EligibilityRule
        fields = ("id", "version", "min_age_months", "max_age_months",
                  "tracking_status", "condition_json")
        read_only_fields = ("id", "version")


class VersionBuilderSerializer(serializers.ModelSerializer):
    """編輯器載入用的完整結構（含草稿可編輯資訊）。"""

    questionnaire_name = serializers.CharField(source="questionnaire.name", read_only=True)
    questionnaire_id = serializers.IntegerField(source="questionnaire.id", read_only=True)
    is_editable = serializers.BooleanField(read_only=True)
    sections = serializers.SerializerMethodField()
    branch_rules = serializers.SerializerMethodField()
    eligibility_rules = EligibilityRuleEditSerializer(many=True, read_only=True)

    class Meta:
        model = QuestionnaireVersion
        fields = (
            "id", "questionnaire_id", "questionnaire_name", "version_number",
            "status", "is_editable", "change_note", "sections", "branch_rules",
            "eligibility_rules",
        )
        read_only_fields = fields

    def get_sections(self, obj):
        sections = obj.sections.order_by("order").prefetch_related("questions__options")
        return SectionEditSerializer(sections, many=True).data

    def get_branch_rules(self, obj):
        rules = (
            BranchRule.objects
            .filter(trigger_question__section__version=obj)
            .select_related("target_section", "target_question", "target_questionnaire")
        )
        return BranchRuleEditSerializer(rules, many=True).data


class QuestionnaireListSerializer(serializers.ModelSerializer):
    versions = serializers.SerializerMethodField()
    tier_name = serializers.CharField(source="tier.name", read_only=True, default=None)
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)

    class Meta:
        model = Questionnaire
        fields = ("id", "name", "description", "category", "category_name",
                  "tier", "tier_name", "is_active", "created_at", "versions")

    def get_versions(self, obj):
        return [
            {
                "id": v.id,
                "version_number": v.version_number,
                "status": v.status,
                "status_label": v.get_status_display(),
                "published_at": v.published_at,
            }
            for v in obj.versions.order_by("version_number")
        ]


class QuestionnaireCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Questionnaire
        fields = ("id", "name", "description", "category", "tier")

    def create(self, validated_data):
        questionnaire = super().create(validated_data)
        QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
        return questionnaire
