---
name: dogfood
description: "Use when performing systematic exploratory QA testing of web applications — finding bugs, capturing evidence, and generating structured test reports. NOT for: unit testing, performance testing, security penetration testing, or automated regression testing."
category: qa
---

## When to Use This Skill

Load this skill when the user asks you to:
- Test a web application for bugs
- Perform exploratory QA on a website
- Find UI/UX issues in a web app
- Generate structured bug reports with evidence
- Do "dogfood" testing of a product

## Core Principles

1. **Explore systematically** — Don't click randomly. Cover: login flows, forms, navigation, edge cases, error states
2. **Capture evidence** — Screenshot or record the URL + steps to reproduce + actual vs expected behavior
3. **Structured reporting** — Always report: Severity | Component | Description | Steps to Reproduce | Expected | Actual

## Workflow

1. Understand the app's core user flows
2. Enumerate edge cases and error states
3. Execute tests and document each finding with evidence
4. Compile a structured report at the end

## Environment

- Browser-based testing (Playwright or similar)
- Evidence format: screenshot + steps + expected vs actual + severity

## Common Triggers

- "test the login page"
- "dogfood this app"
- "find bugs in [website]"
- "exploratory QA"
- "check if [app] is working"
- "test [feature] edge cases"

## Anti-Patterns

Do NOT use this skill for:
- Unit testing (use code-simplification or write unit tests)
- API testing (use http/request tools directly)
- Load/performance testing (use dedicated load testing tools)
- Security penetration testing (use oss-forensics)
- Mobile app testing (this is browser-only)
- Don't make permanent changes to the application under test
