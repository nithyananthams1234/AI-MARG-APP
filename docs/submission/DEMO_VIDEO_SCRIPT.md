# MARG – 3-minute demo video script

**Target length:** 2:50 (hard limit 3:00). Record at 1080p. Show the web app in a
phone-sized browser window (DevTools device mode, Pixel 7), or on an Android
phone with screen recording.

| Time | Screen | Voice-over (about 130 words per minute) |
|---|---|---|
| 0:00–0:20 | Title slide, then the login screen | "In India, school mentors support dozens of teachers across many schools. Their observations, follow-ups and plans live on paper and WhatsApp, so classroom problems are noticed but rarely followed through. MARG is a mentor-focused app that turns every classroom visit into an improvement cycle." |
| 0:20–0:40 | Sign in → Dashboard → bell → Notifications | "Kavya, a mentor with four schools, signs in. Her dashboard is live data: visits this week, an overdue report, follow-ups waiting for verification. Reminders are generated from her real records." |
| 0:40–1:25 | Observations → Science observation → **Analyse with Classroom Coach** → results with sources → select → **Add selected as suggestions** | "After a Grade 8 science lesson she records what she saw. The Classroom Coach, a local language model with retrieval over 167 educational documents such as NCF, CCE and mentoring manuals, analyses the notes. It suggests findings with the evidence quoted from her notes, learning gaps and recommendations, with the exact source pages. Nothing becomes official automatically: she chooses what to keep, and each item stays *AI suggested* until she approves it." |
| 1:25–1:50 | Approve recommendation → Action plans → New plan → Approve → add step | "She approves a hands-on recommendation and turns it into an action plan with steps the teacher agrees to. Plans can only come from approved recommendations." |
| 1:50–2:05 | Follow-ups → upload photo → Verify | "Later, the teacher shares a photo of the student work. Kavya attaches it as evidence and verifies the follow-up." |
| 2:05–2:25 | Coach tab → ask question → answer with [S1] sources; off-topic question → "no relevant knowledge" | "Any time, she can ask the Coach a teaching question. Answers cite their sources, and when the knowledge base has nothing relevant, the Coach says so instead of inventing an answer." |
| 2:25–2:45 | Mentor AI → Daily plan → Visit planning → proposal → Approve → Visits shows the new visit | "The Mentor AI Assistant, powered by Claude, plans her day, ranks her tasks and proposes visits. It never acts alone: when she approves, the visit is created in MARG through the same rules as every other change." |
| 2:45–2:55 | Turn the network off → create a task → "Saved offline" → reconnect → synced | "And because schools often have no signal, MARG works offline and syncs safely, without overwriting newer data." |
| 2:55–3:00 | End slide | "MARG: mentoring that leads to action." |

## Recording checklist

- [ ] Reset the demo data shortly before recording: `python -m app.database.seed_demo --reset` against the demo DB.
- [ ] All services healthy: backend `/health/ready`, Coach `/health/ready` (warm it up with one question first, since the first answer is slower), Mentor AI `/mentor-ai/status`.
- [ ] Claude enabled for Mentor Intelligence, with a valid `ANTHROPIC_MODEL`, so the AI narrative shows. Otherwise say "computed analysis" in the voice-over.
- [ ] Browser zoom at 100%, notifications muted, bookmarks bar hidden, no password visible on screen (type it off-camera or blur it).
- [ ] A small JPEG/PNG of "student work" ready for the evidence upload.
- [ ] Rehearse the Coach analysis wait (20–60 s): cut or speed up the wait in editing, and say so on screen ("sped up").
- [ ] Final cut no longer than 3:00; captions optional; export MP4 (H.264).
