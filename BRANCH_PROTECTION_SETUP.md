# Branch Protection Setup — Tile Station

## How to enable "block broken code" on GitHub:

### Step 1: Go to your repo settings
`https://github.com/YOUR_USERNAME/YOUR_REPO/settings/branches`

### Step 2: Add a branch protection rule
- Click **"Add branch protection rule"**
- **Branch name pattern**: `main`

### Step 3: Enable these settings
- [x] **Require a pull request before merging**
  - [x] Require approvals: `0` (so you can merge your own PRs)
  - [x] Dismiss stale pull request approvals when new commits are pushed
- [x] **Require status checks to pass before merging**
  - Search and add: `Code Integrity Checks`
  - Search and add: `Backend API Regression`
- [x] **Do not allow bypassing the above settings**

### Step 4: Click "Create" / "Save changes"

---

## How the workflow changes:

### Before (direct push):
`Code change → Push to main → Deploys immediately → Tests run after (too late)`

### After (protected):
`Code change → Push to branch → Open PR → Tests run → Pass? → Merge to main → Deploys`

If any test fails, the PR shows ❌ and **cannot be merged**.
