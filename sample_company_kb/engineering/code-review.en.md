---
title: Code Review Guidelines
document_group_id: code-review-guidelines
language: en
space: engineering
allowed_users: []
allowed_groups:
  - engineering
version: 1
updated_at: "2026-05-15T09:00:00Z"
---
# Code Review Guidelines

All production code changes require at least one approval from another engineer. High-risk changes require review from the responsible tech lead.

## Review Expectations

Reviewers should check correctness, maintainability, tests, observability, and security impact. Style comments should reference existing project conventions.

## Merge Rules

Pull requests may be merged when:

- CI passes
- required approvals are present
- migrations are reviewed
- deployment risks are documented

## Response Time

Engineers should respond to review requests within one working day unless they are on leave or assigned to urgent production support.

