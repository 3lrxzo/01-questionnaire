/* 家長端問卷填答頁 —— Vue 3（CDN、Options API、無建構工具）
 *
 * 職責：一次呈現一題、依作答即時套用分支可見性、debounce autosave。
 * 分支可見性在前端算一份是刻意的（《開發規劃書》第二節：避免每答一題
 * 就打一次 server），送出時後端 complete API 會再驗一次必填。
 * 這裡的判斷邏輯必須與 questionnaires/logic.py 的 compute_visibility 對齊。
 */
(function () {
  "use strict";

  const el = document.getElementById("app");
  const cfg = {
    versionId: el.dataset.versionId,
    preview: el.dataset.preview === "1",
    childId: el.dataset.childId || "",
    schemaUrl: el.dataset.schemaUrl,
    responsesUrl: el.dataset.responsesUrl,
    csrf: el.dataset.csrf,
  };

  // --- 與 logic.py evaluate_condition 對齊 ---------------------------------
  function toNumber(v) {
    const n = parseFloat(v);
    return Number.isNaN(n) ? null : n;
  }

  function evaluateCondition(operator, triggerValue, answerValue) {
    if (operator === "answered") {
      if (answerValue === null || answerValue === undefined) return false;
      if (Array.isArray(answerValue) || typeof answerValue === "string") return answerValue.length > 0;
      return true;
    }
    if (answerValue === null || answerValue === undefined) return false;

    if (Array.isArray(answerValue)) {
      return answerValue.some((item) => evaluateCondition(operator, triggerValue, item));
    }

    switch (operator) {
      case "eq": return String(answerValue) === String(triggerValue);
      case "neq": return String(answerValue) !== String(triggerValue);
      case "in": return String(triggerValue).split(",").map((s) => s.trim()).includes(String(answerValue));
    }

    const left = toNumber(answerValue);
    const right = toNumber(triggerValue);
    if (left === null || right === null) return false;
    switch (operator) {
      case "gt": return left > right;
      case "gte": return left >= right;
      case "lt": return left < right;
      case "lte": return left <= right;
      default: return false;
    }
  }

  // --- 與 logic.py compute_visibility 對齊 -------------------------------
  function computeVisibleQuestionIds(schema, answers) {
    const rules = schema.branch_rules || [];
    const allSectionIds = schema.sections.map((s) => s.id);
    const questionToSection = {};
    let allQuestionIds = [];
    schema.sections.forEach((s) => {
      s.questions.forEach((q) => {
        questionToSection[q.id] = s.id;
        allQuestionIds.push(q.id);
      });
    });

    const showTargetSections = new Set(
      rules.filter((r) => r.action === "show" && r.target_section_id).map((r) => r.target_section_id)
    );
    const showTargetQuestions = new Set(
      rules.filter((r) => r.action === "show" && r.target_question_id).map((r) => r.target_question_id)
    );

    const visibleSections = new Set(allSectionIds.filter((id) => !showTargetSections.has(id)));
    const visibleQuestions = new Set(allQuestionIds.filter((id) => !showTargetQuestions.has(id)));

    rules.forEach((rule) => {
      const hit = evaluateCondition(rule.trigger_operator, rule.trigger_value, answers[rule.trigger_question_id]);
      if (!hit) return;
      if (rule.action === "show") {
        if (rule.target_section_id) visibleSections.add(rule.target_section_id);
        if (rule.target_question_id) visibleQuestions.add(rule.target_question_id);
      } else {
        visibleSections.delete(rule.target_section_id);
        visibleQuestions.delete(rule.target_question_id);
      }
    });

    // 題組隱藏時其下題目一併隱藏
    allQuestionIds.forEach((qid) => {
      if (!visibleSections.has(questionToSection[qid])) visibleQuestions.delete(qid);
    });

    return visibleQuestions;
  }

  function isBlank(v) {
    return v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0);
  }

  const { createApp } = Vue;

  createApp({
    compilerOptions: { delimiters: ["{[", "]}"] },

    data() {
      return {
        loading: true,
        loadError: "",
        schema: null,
        answers: {},
        responseId: null,
        currentIndex: 0,
        saveHint: "",
        submitting: false,
        submitError: "",
        completed: false,
        _saveTimer: null,
      };
    },

    computed: {
      isPreview() { return cfg.preview; },

      orderedQuestions() {
        if (!this.schema) return [];
        const out = [];
        this.schema.sections.forEach((s) => s.questions.forEach((q) => out.push(q)));
        return out;
      },

      visibleQuestions() {
        if (!this.schema) return [];
        const visibleIds = computeVisibleQuestionIds(this.schema, this.answers);
        return this.orderedQuestions.filter((q) => visibleIds.has(q.id));
      },

      currentQuestion() {
        return this.visibleQuestions[this.currentIndex] || null;
      },

      isLast() {
        return this.currentIndex >= this.visibleQuestions.length - 1;
      },

      progressPct() {
        if (!this.visibleQuestions.length) return 0;
        return Math.round(((this.currentIndex + 1) / this.visibleQuestions.length) * 100);
      },

      canAdvance() {
        const q = this.currentQuestion;
        if (!q) return false;
        if (!q.required) return true;
        return !isBlank(this.answers[q.id]);
      },
    },

    watch: {
      // 分支收合後，currentIndex 可能落在清單外
      "visibleQuestions.length"(len) {
        if (this.currentIndex > len - 1) this.currentIndex = Math.max(0, len - 1);
      },
    },

    async mounted() {
      try {
        const res = await fetch(cfg.schemaUrl + (cfg.preview ? "?preview=1" : ""), {
          headers: { "Accept": "application/json" },
        });
        if (!res.ok) throw new Error("無法載入問卷內容（" + res.status + "）");
        this.schema = await res.json();

        // 預設把複選題答案初始化為陣列，讓 v-model 綁定正常
        this.orderedQuestions.forEach((q) => {
          if (q.question_type === "multi" && !(q.id in this.answers)) this.answers[q.id] = [];
        });

        if (!cfg.preview && cfg.childId) {
          await this.startResponse();
        }
      } catch (e) {
        this.loadError = e.message || String(e);
      } finally {
        this.loading = false;
      }
    },

    methods: {
      scaleRange(q) {
        const min = q.config.min ?? 0;
        const max = q.config.max ?? 10;
        const out = [];
        for (let i = min; i <= max; i++) out.push(i);
        return out;
      },

      async startResponse() {
        const res = await fetch(cfg.responsesUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": cfg.csrf },
          body: JSON.stringify({ child: cfg.childId, version: cfg.versionId }),
        });
        if (!res.ok) throw new Error("無法建立填答紀錄（" + res.status + "）");
        const data = await res.json();
        this.responseId = data.id;
        // 續填：把已存的答案帶回
        Object.entries(data.answers || {}).forEach(([qid, value]) => {
          this.answers[qid] = value;
        });
      },

      onAnswerChanged() {
        this.submitError = "";
        if (cfg.preview || !this.responseId) {
          this.saveHint = cfg.preview ? "預覽模式不會儲存" : "";
          return;
        }
        this.saveHint = "儲存中…";
        clearTimeout(this._saveTimer);
        this._saveTimer = setTimeout(this.autosave, 600);
      },

      async autosave() {
        if (!this.responseId || !this.currentQuestion) return;
        const qid = this.currentQuestion.id;
        try {
          const res = await fetch(`/api/responses/${this.responseId}/autosave/`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json", "X-CSRFToken": cfg.csrf },
            body: JSON.stringify({ answers: { [qid]: this.answers[qid] } }),
          });
          if (!res.ok) throw new Error();
          const t = new Date();
          this.saveHint = `已於 ${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")} 暫存`;
        } catch {
          this.saveHint = "暫存失敗，稍後會自動重試";
        }
      },

      next() {
        if (this.currentIndex < this.visibleQuestions.length - 1) this.currentIndex++;
      },

      prev() {
        if (this.currentIndex > 0) this.currentIndex--;
      },

      async submit() {
        this.submitError = "";
        if (cfg.preview) {
          this.completed = true;
          return;
        }
        if (!this.responseId) {
          this.submitError = "尚未指定填答對象，無法送出。";
          return;
        }
        this.submitting = true;
        try {
          clearTimeout(this._saveTimer);
          await this.autosave();
          const res = await fetch(`/api/responses/${this.responseId}/complete/`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": cfg.csrf },
          });
          const data = await res.json();
          if (!res.ok) {
            if (data.missing_question_ids && data.missing_question_ids.length) {
              const idx = this.visibleQuestions.findIndex((q) => data.missing_question_ids.includes(q.id));
              if (idx >= 0) this.currentIndex = idx;
            }
            throw new Error(data.detail || "送出失敗");
          }
          this.completed = true;
        } catch (e) {
          this.submitError = e.message || String(e);
        } finally {
          this.submitting = false;
        }
      },
    },
  }).mount("#app");
})();
