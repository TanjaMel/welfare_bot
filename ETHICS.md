## Third-Party Data Processors

The following third-party services process data on behalf of Welfare Bot:

### OpenAI
- **Purpose:** Conversation generation (GPT-4o-mini), speech-to-text (Whisper), text-to-speech (TTS-1)
- **Data sent:** Conversation messages, audio recordings
- **Retention:** Per OpenAI API policy — not used for training by default
- **Privacy policy:** https://openai.com/policies/privacy-policy

### SendGrid (Twilio)
- **Purpose:** Transactional email notifications — risk alerts to care contacts, password reset emails
- **Data sent:** Recipient email address, user first name, risk level, suggested action
- **What is NOT sent:** Conversation content, full risk analysis, personal health details
- **Retention:** Per SendGrid policy — email logs retained 30 days
- **Privacy policy:** https://www.twilio.com/en-us/legal/privacy

### Railway
- **Purpose:** Cloud hosting and PostgreSQL database
- **Data stored:** All application data including user profiles, conversations, risk analyses
- **Region:** US West (configurable)
- **Privacy policy:** https://railway.app/legal/privacy

## Notification Pipeline Ethics

When a HIGH or CRITICAL risk is detected:
1. A notification is queued in the database
2. Every 5 minutes the system checks for pending notifications
3. An email is sent to the user's designated care contact
4. If no care contact is set, the email goes to the admin

**What the notification contains:**
- User's first name
- Risk level (HIGH or CRITICAL)
- Suggested action for the care worker
- No conversation content is included

**Human oversight requirement:**
All notifications are informational only. No automated action is taken.
The care contact must decide independently what action to take.