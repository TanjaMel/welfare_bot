# Ethics Documentation — Welfare Bot

## Project overview

Welfare Bot is an AI-powered daily check-in assistant for elderly people living alone.
It monitors wellbeing through conversation, detects risk signals, and alerts care workers
and family members when concerning patterns emerge.

This document identifies the ethical risks of the system, the design decisions made to
mitigate them, and the responsibilities of everyone involved in its operation.

---

## 1. Who is affected

| Stakeholder | Role | Potential impact |
|---|---|---|
| Elderly users | Primary users — converse with the bot daily | Privacy, dignity, autonomy, safety |
| Family members / care contacts | Receive alerts | Emotional burden, false alarms |
| Care workers / admins | View dashboard, act on flags | Workload, decision responsibility |
| Developers | Build and maintain the system | Accountability for failures |
| Healthcare providers | May receive escalated cases | Clinical responsibility |

---

## 2. Identified ethical risks

### 2.1 False positives — unnecessary alarm

**Risk:** The risk engine or anomaly detector flags a user as HIGH or CRITICAL when they
are actually fine. This causes unnecessary worry for family members, wastes care worker
time, and may erode the user's trust in the system.

**Likelihood:** Medium. The LLM risk engine is probabilistic and can misread indirect
language. The anomaly detector uses statistical thresholds that will fire on natural
variation in small datasets.

**Mitigation:**
- The rule-based engine acts as a safety floor — it only fires on explicit signals
- The LLM result is never allowed to *downgrade* a risk level, only upgrade it
- Anomaly flags require severity ≥ 2.0 AND at least 5 days of history
- All alerts are labeled "possible concern" — never "emergency" — until a human reviews
- Care workers see the specific signals that triggered the flag, not just the label

---

### 2.2 False negatives — missed real crises

**Risk:** The system fails to detect a genuine emergency. A user falls, feels severe
chest pain, or experiences a mental health crisis, but the message is phrased in a way
the system does not recognize.

**Likelihood:** Low for explicit physical signals (rule engine catches these directly).
Medium for indirect emotional distress, especially in Finnish or Swedish where cultural
norms discourage direct expression of suffering.

**Mitigation:**
- Critical keywords (chest pain, rintakipu, bröstsmärta, fell down) trigger immediate
  CRITICAL flag regardless of LLM assessment
- The system explicitly prompts follow-up questions when medium signals are detected
- Users are reminded at conversation start that the bot is not a substitute for emergency services
- The system is designed as a *supplement* to human care, not a replacement

**Residual risk:** This system cannot replace 112 / emergency services. Users must be
informed clearly that if they feel they are in immediate danger, they should call 112.

---

### 2.3 Over-reliance by care workers

**Risk:** Care workers begin treating the bot's risk assessment as a clinical diagnosis.
They reduce direct human contact because "the bot is monitoring." This creates a false
sense of safety and reduces genuine human connection — which is itself a wellbeing factor.

**Mitigation:**
- The admin dashboard explicitly labels all outputs as "indicators" not "diagnoses"
- Risk levels use soft language (needs attention, concerning) — never clinical terms
- Dashboard documentation states: *"This system supports, but does not replace, human judgment"*
- Alerts recommend human contact as the response — the bot does not act autonomously

---

### 2.4 Privacy and data sensitivity

**Risk:** The system stores sensitive health-related conversation data, risk assessments,
and wellbeing scores for vulnerable individuals. A data breach would expose intimate
details of elderly people's physical and mental health.

**Data collected:**
- Conversation messages (free text, may include health complaints)
- Risk scores and categories
- Wellbeing metrics (sleep, food, mood, hydration)
- Memory summaries (AI-generated summaries of health patterns)
- Care contact information

**Mitigation:**
- All data is stored in a private PostgreSQL database, not shared with third parties
- OpenAI API calls do not include personally identifying information (name, address, ID)
  in the message content — only the message text and language
- Memory summaries are stored per-user and only accessible to that user's care worker
- No data is used to train external models
- Users should be informed of what data is collected and for how long it is retained
  (recommended retention: 12 months rolling)

**Remaining gap:** A formal GDPR-compliant privacy policy and data retention schedule
should be implemented before production deployment with real users.

---

### 2.5 Language and cultural bias

**Risk:** The system was primarily designed and tested with English language patterns.
Finnish and Swedish users — who are the primary target population — may experience
lower accuracy in risk detection because the signal patterns are less comprehensive
in those languages.

**Evidence:** During testing, Finnish phrases like "en oikein jaksanut nukkua" (I
haven't really been able to sleep) required manual addition to the rule engine because
they were not initially covered. Swedish "mår inte bra" (not feeling well) was also
missed in the first version.

**Mitigation:**
- Finnish and Swedish signal patterns have been expanded and tested
- The LLM risk engine uses language-agnostic semantic understanding and performs better
  on indirect expressions than the rule engine alone
- The fallback rule engine is tested with explicit Finnish and Swedish test cases
  (see `test_risk_service.py`)

**Remaining gap:** The system has not been tested with real elderly Finnish or Swedish
speakers. Pilot testing with the actual user population is essential before deployment.

---

### 2.6 Autonomy and dignity of elderly users

**Risk:** The system may feel infantilizing or surveillance-like to elderly users.
Being monitored by an AI could feel undignified, especially if alerts are sent to
family members without the user's knowledge or consent.

**Mitigation:**
- Conversations are designed to feel warm and peer-like, not clinical or interrogating
- The bot asks one question at a time — never lists or interrogates
- Users should be informed that care contacts receive alerts and should consent to this
- Users should have the right to opt out of family notifications while retaining bot access
- The memory system is designed to make the bot feel more personal, not more surveilling

**Recommended addition:** An explicit consent flow at onboarding where users choose
their alert preferences and are shown exactly what information their care contacts receive.

---

### 2.7 Algorithmic bias in anomaly detection

**Risk:** The anomaly detector uses each user's own baseline to detect anomalies
(Z-score against personal history). This is intentionally personalized. However:

- Users with very short history (< 5 days) are excluded from anomaly detection entirely,
  meaning new users have no safety net during their first week
- Users who are *consistently* unwell will have a low baseline — a further drop
  that is clinically significant may not trigger an anomaly because their std is high

**Mitigation:**
- The 5-day minimum threshold is explicit and documented
- The rule-based risk engine covers new users during the history-building period
- Absolute score thresholds (status = "critical") trigger alerts regardless of personal baseline

**Remaining gap:** The anomaly detector should be supplemented with population-level
thresholds (e.g. flag anyone whose overall score drops below 30 regardless of baseline).

---

## 3. Human oversight requirements

The system is designed with the principle that **no automated action affects a person's
care without human review**. Specifically:

| Automated action | Human review required |
|---|---|
| Risk flag stored in database | ✅ Care worker reviews dashboard |
| Notification sent to care contact | ✅ Care contact decides how to respond |
| Anomaly flag raised | ✅ Admin reviews flagged users list |
| Memory summary generated | ℹ️ No action taken — informational only |

The system does **not** and should **not**:
- Automatically dispatch emergency services
- Share data with healthcare providers without consent
- Make clinical diagnoses
- Replace scheduled care visits

---

## 4. Accuracy monitoring obligations

The development team is responsible for:

- Reviewing false positive rates monthly once the system is in production
- Tracking how often CRITICAL flags correspond to genuine crises (precision)
- Tracking how often genuine crises were not flagged (recall) — requires care worker feedback
- Retraining or recalibrating the anomaly detector if false positive rate exceeds 20%
- Logging all LLM risk assessments with `assessed_by` field for audit trail

---

## 5. Recommendations before production deployment

1. **Informed consent** — all users must be told what the system does, what data it collects,
   who receives alerts, and how to opt out
2. **GDPR compliance** — formal data retention policy, right to deletion, privacy notice
3. **Pilot testing** — test with 5–10 real elderly Finnish/Swedish users before wider rollout
4. **Care worker training** — document explicitly that this is a support tool, not a diagnostic tool
5. **Emergency services clarity** — every conversation should include a reminder that
   112 is the number for genuine emergencies
6. **Feedback loop** — care workers should be able to mark alerts as "false positive" or
   "genuine concern" so accuracy can be tracked over time

---

## 6. Summary

Welfare Bot has meaningful potential to improve safety and wellbeing outcomes for
elderly people living alone. The risks are real but manageable with the mitigations
described above. The most important principle is that **the system supports human care
workers and family members — it does not replace them**.

Every alert the system generates is a prompt for a human to make a phone call.
Every risk flag is a starting point for conversation, not a conclusion.

---

