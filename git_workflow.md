# Start on main and make sure it's up-to-date
git checkout main
git pull origin main

# Create your feature branch and do your work
git checkout -b <branch>
# ... write code, test, then commit ...
git add .
git commit -m "A good commit message"

# Prepare to merge by updating main again
git checkout main
git pull origin main

# Merge your feature and push it to the remote
git merge <branch>
git push origin main

# Clean up your local branch
git branch -d <branch>


# --- for making changes unrelated to feature branch

git stash push -m "WIP on feature branch"

# Switch to main and make sure it's up-to-date
git checkout main
git pull origin main

# Make the minor fix (e.g., typo, comment)
# ... edit files ...
git add .
git commit -m "Fix typo / add comment"

# Push the fix to remote
git push origin main

# Return to your feature branch
# You're currently on your feature branch
# Save your work (if not committed yet)
git stash push -m "WIP on feature branch"

# Switch to main and make sure it's up-to-date
git checkout main
git pull origin main

# Make the minor fix (e.g., typo, comment)
# ... edit files ...
git add .
git commit -m "Fix typo / add comment"

# Push the fix to remote
git push origin main

# Return to your feature branch
git checkout <branch>

# Reapply your stashed work
git stash pop