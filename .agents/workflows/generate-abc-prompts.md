---
description: Generates exactly 100 canonical prompts for Agent Behavioral Checksum evaluation based on the requirements defined in docs/canonical-prompts.md.
---

# Generate ABC Canonical Prompts — Workflow Description

This workflow defines an AI agent process for automatically generating a standardized evaluation dataset called **ABC Canonical Prompts**.

## Overview

The workflow performs three sequential stages:

1. Read the prompt generation requirements.
2. Generate a compliant prompt dataset.
3. Save the generated dataset to a file.

---

## Step 1: Read Guidelines

The agent begins by loading and reading the specification document:

`docs/canonical-prompts.md`

This document defines the requirements for valid canonical prompts, including:

- The required prompt categories
- The expected JSON schema
- Quality and formatting constraints

---

## Step 2: Generate JSON Prompts

After reading the specification, the agent invokes a language model to generate the dataset.

The model is instructed to:

- Generate **exactly 100 canonical prompts**
- Strictly follow the specification defined in the guidelines document
- Produce prompts across **8 categories**
- Keep category distribution approximately balanced (**±3 prompts per category**)
- Ensure **at least 30% of prompts are security-relevant**
- Follow the required **JSON schema**
- Return **only the raw JSON array** with no additional explanation or formatting

---

## Step 3: Save to File

Once generation completes, the workflow writes the resulting JSON output to:

`docs/abc_canonical_prompts_dataset.json`

The saved content is taken directly from the output of the prompt generation step.

---

## Summary

The workflow can be summarized as:

**Read requirements → Generate compliant prompt dataset → Save dataset**

Its purpose is to create a reproducible benchmark dataset for **Agent Behavioral Checksum (ABC) evaluation**, enabling consistent assessment and comparison of agent behavior.
