# Evidence folder

This folder is for *agent-verifiable* ticket completion notes.

Workflow we’ll use per ticket:
1. Move Jira issue to **In Progress** when we start.
2. Implement code + tests.
3. Create an evidence file `evidence/<ISSUE_KEY>.md` based on `TICKET_COMMENT_TEMPLATE.md`.
4. Post that file to Jira as a comment.
5. Move Jira issue to **Test** and wait for human verification.
6. After verification, move Jira issue to **Done**.

Helper script:
- `tools/jira/workflow.py` can transition issues and post comment text.
