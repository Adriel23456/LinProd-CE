# Code Control

## Branching Strategy

```
master
  └── develop/**
        └── task/**
```

---

## Branches

### `master`
- **Purpose:** Production-ready releases only. Nothing is pushed here directly.
- **Receives PRs from:** `develop/**` branches exclusively.
- **PR Approval:** **1 approval required** before merge.

---

### `develop/**`
- **Purpose:** Represents a major stage of development (e.g., `develop/auth`, `develop/navigation`).
- **Receives PRs from:** `task/**` branches exclusively.
- **PR Approval:** **No approval required** — merge freely once your task is done.

---

### `task/**`
- **Purpose:** Day-to-day implementation work. One task, one branch (e.g., `task/login-ui`, `task/fix-sensor-timeout`).
- **PRs:** **Not required.** Work directly on this branch and open a PR to the relevant `develop/**` branch when ready.

---

## Flow Summary

```
task/your-feature
    │
    │  PR (no approval needed)
    ▼
develop/your-stage
    │
    │  PR (1 approval required)
    ▼
master  ← releases only
```

---

## Rules at a Glance

| Branch       | Push directly? | PR target      | Approval needed? |
|--------------|---------------|----------------|------------------|
| `master`     | ❌ No          | —              | —                |
| `develop/**` | ❌ No          | `master`       | ✅ 1 approval    |
| `task/**`    | ✅ Yes         | `develop/**`   | ❌ No            |

---

## Naming Convention

```
develop/feature-name
task/short-description
```

Keep names lowercase, hyphen-separated, and descriptive.