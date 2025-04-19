# Git Workflow Guide for TradingV1: Check-In, Merge, and Branch Reset

**Tags**: #Git #VersionControl #TradingV1 #SSH #CheckIn #Merge #BranchReset

## Overview
This guide documents the Git workflow for the `TradingV1` repository, including checking in changes, merging to the `master` branch, and resetting the `dev` branch for a fresh start. It includes troubleshooting steps for SSH authentication issues, ensuring smooth operations without investigative work.

## Repository Details
- **Repository Root**: `/home/egirg/shared/`
- **Remote URL**: `git@github.com:SimoneAG21/TradingV1.git`
- **Primary Branch**: `master`
- **Development Branch**: `dev`
- **Git Remote**:
  ```
  origin  git@github.com:SimoneAG21/TradingV1.git (fetch)
  origin  git@github.com:SimoneAG21/TradingV1.git (push)
  ```

## Workflow Steps

### 1. Navigate to the Repository Root
```bash
cd /home/egirg/shared/
```

### 2. Verify Your Branch
Ensure you’re on the `dev` branch:
```bash
git branch
```
- If not on `dev`, switch to it:
  ```bash
  git checkout dev
  ```

### 3. Check the Status
View modified, deleted, and untracked files:
```bash
git status
```

### 4. Stage Changes
Stage the files to commit:
- Modified files:
  ```bash
  git add trading_dev/config/combined_config.yaml
  git add trading_dev/devSetEnv.bash
  git add trading_dev/dev_specific/testing.md
  git add trading_dev/helper/Logger.py
  git add trading_dev/helper/lockfile.py
  git add trading_dev/scripts/channelTracker.py
  git add trading_dev/scripts/telegram_fetch.py
  git add trading_dev/tests/test_channel_tracker.py
  git add trading_dev/tests/test_config_manager.py
  git add trading_dev/tests/test_lockfile.py
  ```
- New files:
  ```bash
  git add trading_dev/channel-tracker-service-guide.md
  git add trading_dev/tests/test_telegram_fetch.py
  ```
- Deleted files:
  ```bash
  git rm "trading_dev - Shortcut.lnk"
  ```
- Updated `.gitignore`:
  ```bash
  git add .gitignore
  ```

### 5. Commit Changes
Commit with a descriptive message:
```bash
git commit -m "Your commit message here"
```
- Example:
  ```bash
  git commit -m "Fix initial channel sync in channelTracker.py, update tests, helpers, config, and add channel-tracker-service-guide.md"
  ```

### 6. Push to the Dev Branch
Push changes to the remote `dev` branch:
```bash
git push origin dev
```

#### Troubleshooting SSH Authentication Issues
If you encounter `Permission denied (publickey)`:
- **Start SSH Agent**:
  ```bash
  eval "$(ssh-agent -s)"
  ```
- **Add SSH Key**:
  ```bash
  ssh-add ~/.ssh/id_ed25519_tradingv1
  ```
- **Verify Key**:
  ```bash
  ssh-add -l
  ```
  - Expected: `256 SHA256:0mkf1vjWS877+Eki/U4qPZJ64PJq5DQd+yAsQlhwowc SimoneAG21_TradingV1 (ED25519)`
- **Test SSH Connection**:
  ```bash
  ssh -T git@github.com
  ```
  - Expected: `Hi SimoneAG21! You've successfully authenticated, but GitHub does not provide shell access.`
- **Debug SSH Push**:
  ```bash
  GIT_SSH_COMMAND="ssh -v" git push origin dev
  ```
- **Switch to HTTPS (Fallback)**:
  ```bash
  git remote set-url origin https://github.com/SimoneAG21/TradingV1.git
  git push origin dev
  ```
  - Use username `SimoneAG21` and a Personal Access Token (PAT).

### 7. Merge to Master
- Switch to `master`:
  ```bash
  git checkout master
  ```
- Merge `dev`:
  ```bash
  git merge dev
  ```
- Push to `master`:
  ```bash
  git push origin master
  ```

### 8. Reset the Dev Branch
- Switch to `dev`:
  ```bash
  git checkout dev
  ```
- Reset to `master`:
  ```bash
  git reset --hard origin/master
  git push origin dev --force
  ```

## Verification
- **Check Remote Branches**:
  ```bash
  git fetch origin
  git log origin/master --oneline
  git log origin/dev --oneline
  ```
- **Check Status**:
  ```bash
  git status
  ```

## SSH Key Details
- **Key File**: `/home/egirg/.ssh/id_ed25519_tradingv1`
- **Public Key**:
  ```
  ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ5ML10SE7+6tBxkJegLavxcDWq2LMS0Kv5n0nKKedaO SimoneAG21_TradingV1
  ```
- **Key Fingerprint**:
  ```
  256 SHA256:0mkf1vjWS877+Eki/U4qPZJ64PJq5DQd+yAsQlhwowc SimoneAG21_TradingV1 (ED25519)
  ```

## Additional Notes
- **Excluded Files**: `.gitignore` excludes `sessions/*.session`, `.coverage`, `output.txt`, `*.lnk`, and `troubleshoot_telegram_client.py`.
- **Automate SSH Agent**: Add to `~/.bashrc`:
  ```bash
  echo 'eval "$(ssh-agent -s)"' >> ~/.bashrc
  echo 'ssh-add ~/.ssh/id_ed25519_tradingv1' >> ~/.bashrc
  ```