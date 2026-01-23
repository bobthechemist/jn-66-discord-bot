# Project Requirements Document: jn-66 — Intelligent Task Management Bot (Discord)

## Overview
jn-66 is an intelligent task and workflow management bot for Discord that enables teams to create, assign, track, and automate tasks via natural language, integrations, and smart suggestions. The bot should be efficient in server contexts, respect role-based permissions, and provide clear UX in text and slash-command flows.

## Scope
In scope:
- Task creation, editing, assignment, and lifecycle management inside Discord servers.
- Natural language parsing for quick task entry.
- Reminders, due dates, recurring tasks, prioritization, and status updates.
- Integrations with calendar services, GitHub (issues/PR links), and external task trackers (optional).
- Notification controls, permissions, and audit logging.
Out of scope:
- Full standalone web app (minimal web UI for oauth/integration settings only).
- Heavy-weight project management features (Gantt charts, time tracking).

## Stakeholders
- Product Owner: Team lead
- End Users: Developers, PMs, Ops in Discord servers
- Admins: Server owners and role-based managers
- Integrations: Calendar, GitHub, external webhooks

## Goals
- Reduce friction to create and track tasks directly in chat.
- Provide reliable reminders and status tracking.
- Surface intelligent suggestions to prioritize and batch tasks.
- Respect server privacy and permission models.

## Functional Requirements

| Req ID | Description | User Story | Expected Behavior / Acceptance Criteria |
|--------|-------------|------------|------------------------------------------|
| FR001 | Create Task | As a user, I want to create a task via slash command or natural language so I can capture work items quickly. | /task create or natural language ("todo: fix bug #123 by Friday @alice #high") creates a task with title, optional assignee, due date, priority, tags. Bot confirms with a message and task ID. |
| FR002 | Edit Task | As a user, I want to edit task fields so I can correct or update details. | /task edit <id> updates title, description, assignee, due date, priority, recurring schedule; confirmation shown. Permissions restrict edits to creator, assignee, or roles. |
| FR003 | Assign Task | As a user, I want to assign a task to a team member so responsibilities are clear. | Assign via command or mention; assignee receives DM/mention and task appears in their task list. |
| FR004 | Task Status & Lifecycle | As a user, I want to change status (todo/in-progress/done) so progress is tracked. | /task status <id> <status> updates task; channel message and audit log entry created. |
| FR005 | Reminders & Notifications | As a user, I want reminders for upcoming/overdue tasks so I don't miss deadlines. | Reminders sent via DM or channel at configurable intervals; overdue alerts posted. Users can snooze or dismiss. |
| FR006 | Recurring Tasks | As a user, I want recurring tasks so repeated work is automated. | Support cron-like or human schedules (daily, weekly, monthly); bot auto-creates occurrences and notifies assignees. |
| FR007 | Natural Language Parsing | As a user, I want to type tasks in plain language so entry is fast. | NLP extracts title, due date, assignee, tags, and priority with >80% accuracy in typical formats; provides a preview and confirm step. |
| FR008 | Bulk Import & Export | As an admin, I want to import/export tasks so teams can migrate or backup data. | CSV/JSON import and export available via command or web settings with validation feedback. |
| FR009 | Search & List Views | As a user, I want to list and filter tasks so I can find relevant items. | /task list supports filters (assignee, status, due range, tags, priority) and pagination. |
| FR010 | Integration: GitHub & Calendar | As a user, I want to link issues and calendar events so tasks align with external systems. | Link GitHub issues to tasks, sync due dates with calendar invites; OAuth-based integrations with per-server settings. |
| FR011 | Permissions & Roles | As an admin, I want role-based controls so task actions are secure. | Server admins configure who can create, assign, edit, delete, and export tasks. Defaults sensible for public servers. |
| FR012 | Audit Logging | As an admin, I want an audit trail so changes are traceable. | Immutable logs for create/edit/assign/status/delete with timestamp, user, and diff available to admins. |
| FR013 | Undo & Recovery | As a user, I want to undo recent destructive actions so mistakes can be recovered. | Soft-delete with 30-day retention and /task restore <id> for authorized users. |
| FR014 | Reporting & Metrics | As a manager, I want usage and throughput reports so team health is visible. | /task report generates summaries (open tasks, avg time-to-complete, overdue counts) per period. |

## Non-Functional Requirements
- Availability: 99.9% uptime during working hours; graceful degradation for integrations.
- Performance: Commands should respond within 2s for 95% of requests.
- Scalability: Support servers with up to 50k members using sharding and per-guild storage.
- Security & Privacy: Follow OAuth best practices; store minimal PII; encryption at rest; role-based access.
- Data Retention: Soft-deletes retained 30 days; exports available; clear deletion workflow.
- Localization: English v1; design for easy i18n.

## UX & Interaction Patterns
- Support both slash commands and natural-language messages.
- Provide ephemeral confirmations for command initiators and public summaries where appropriate.
- Use embeds for task cards with concise fields (title, assignee, due, priority, tags, link).

## Success Metrics
- 30-day active install growth rate.
- Time-to-create-task < 10s (average).
- Reduction in missed deadlines for pilot teams by 30%.
- Daily active users / server conversion rates.

## Release Milestones
- M1 (Alpha, 4 weeks): Basic task create/edit/list, slash commands, simple reminders, permissions.
- M2 (Beta, +4 weeks): NLP entry, assignees, recurring tasks, search, export.
- M3 (Integrations, +4 weeks): GitHub and Calendar integrations, web settings UI.
- M4 (Stability, +4 weeks): Audit logs, reporting, performance tuning, public launch.

## Risks & Mitigations
- NLP mis-parsing: add explicit confirm preview and fallback structured commands.
- Notification spam: configurable channels and per-user preferences.
- Data privacy concerns: minimal data storage, clear privacy docs, opt-out export/delete.

## Open Questions
- Required GDPR/data residency constraints per target audience?
- Which third-party integrations are highest priority beyond GitHub and Calendar?
- Default permission model for community vs private servers?

## Appendix
- Example command syntaxes:
  - /task create title:"Fix login bug" assignee:@alice due:tomorrow priority:high tags:auth
  - "todo: write release notes by Friday @bob #docs"
- Minimal web settings: OAuth, integration configuration, data export.