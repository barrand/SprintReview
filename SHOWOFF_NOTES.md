# Sprint Review Automation -- Showoff Notes

## The Challenge

How do we eliminate the sprint review meeting entirely -- and still achieve the same outcomes?

Sprint reviews exist to produce specific outcomes. If a page can deliver every one of them asynchronously, the meeting is dead weight.

## Desired Outcomes of a Sprint Review

1. **Stakeholder awareness of what shipped** -- people know what was delivered
2. **Validation of working software** -- stakeholders see the actual product
3. **Feedback and questions** -- stakeholders react, ask, push back
4. **Priority input on upcoming work** -- alignment on what matters next
5. **Risk and blocker visibility** -- what didn't get done and why
6. **Team recognition** -- celebrating contributions
7. **Proof of engagement** -- knowing who actually consumed the review

## The Approach

Every outcome above maps to a feature on an auto-generated interactive page that replaces the meeting entirely:

| Outcome | Page Feature |
|---|---|
| Awareness of what shipped | Auto-generated metrics, story breakdowns, release notes |
| Validation | Story detail with subtasks, descriptions, Jira links |
| Feedback and questions | **Freeform input box** at the bottom of the page |
| Priority input | **Coming Attractions Ballot** -- vote on next sprint's backlog |
| Risk / blocker visibility | **Cutting Room Floor** section with carry-over items |
| Team recognition | **Academy Awards** -- auto-calculated from real data |
| Proof of engagement | **Ticket Stub** -- rip to check in |

If a question or piece of feedback warrants a deeper conversation, the product team schedules a dedicated meeting for that specific topic. No more recurring ceremony.

## How We Measure Success

Three interactive features give us direct signal on whether the page is replacing the meeting:

1. **Ticket Stub (Rip to Check In)** -- tells us *who opened and read the review*
2. **Coming Attractions Ballot (Feature Voting)** -- tells us *who engaged deeply enough to weigh in on priorities*
3. **Feedback Box (Questions & Input)** -- tells us *what stakeholders are thinking* and whether anything needs a follow-up conversation

If people are ripping tickets, casting votes, and leaving feedback -- the meeting is dead. And honestly? This is better. A meeting loses feedback the moment it ends. This page captures it. A meeting lets people zone out. This page requires engagement to check in. Good riddance.

## Time & Cost Savings

**Per pod, per sprint (2-week cycle), ~24 attendees out of 34 invitees:**

| | Hours | Notes |
|---|---|---|
| Meeting eliminated (1 hr x 24 attendees) | -24 hrs | Saved |
| Prep eliminated (slides + demos) | -5 hrs | Saved |
| Time viewing the page (15 min x 24 people) | +6 hrs | Added |
| **Net savings per sprint** | **~23 hrs** | |
| **Net savings per year (26 sprints)** | **~598 hrs** | |

**Across 12 pods in Field Service division:**

| | Hours | Cost |
|---|---|---|
| Per pod per year | ~598 hrs | ~$45k |
| **12 pods per year** | **~7,176 hrs** | **~$538k** |

Based on a blended rate of $75/hr.
