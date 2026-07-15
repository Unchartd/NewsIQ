---
trigger: always_on
---

# planning.md — Planning & Execution Rules for NewsIQ

All project modifications must follow the Planning → Design → Document → Task → Implement workflow.

## 1. Planning Phase (No Code Modifications)
- Before making any code changes, perform comprehensive research using search, view_file, and directory analysis tools.
- Identify:
  - Downstream and upstream impact of the change.
  - Affected services, endpoints, and databases.
  - Potential architectural risks and rollback strategies.

## 2. Design & Implementation Plan
- Document findings and proposed solutions in an `implementation_plan.md` artifact.
- The plan must break the work into clear milestones, outlining:
  - Affected files and components.
  - Estimate complexity, risks, and dependencies.
  - Acceptance criteria and automated/manual testing strategy.
- Obtain explicit user review and approval before starting coding tasks.

## 3. Task Breakdown & Tracking
- Create a `task.md` file listing all required items.
- Track progress by marking items as:
  - `[ ]` for uncompleted tasks.
  - `[/]` for in-progress tasks.
  - `[x]` for completed tasks.
- Keep tasks atomic and focused on a single change.

## 4. Incremental Execution & Self-Review
- Implement only one task at a time.
- Perform a thorough self-review of changes: check type annotations, SOLID principles, lint conformity, and potential resource leaks.
- Write or update tests and run them to verify correctness.
- Update relevant architecture, API, or system documentation before proceeding to the next task.
