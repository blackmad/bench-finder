# Pre-commit API Generation Setup

This project automatically regenerates the TypeScript API client from the FastAPI OpenAPI schema before each commit to ensure your frontend stays in sync with the backend API.

## How it works

Two pre-commit hooks have been set up:

### 1. Git Pre-commit Hook (`.git/hooks/pre-commit`)
- Simple shell script that runs before each commit
- Works for all contributors without requiring additional packages
- Automatically regenerates API client and stages changes

### 2. Husky + lint-staged (`.husky/pre-commit`)
- More advanced setup with additional linting and formatting
- Requires `husky` and `lint-staged` packages (already installed)
- Runs API generation + code formatting + linting

## What happens on commit

1. **API Generation**: Attempts to regenerate the API client using:
   - Live server (`npm run generate-api`) if FastAPI server is running on port 8866
   - Local schema (`npm run generate-schema`) if server is not running

2. **Auto-staging**: If API client files change, they are automatically staged for commit

3. **Code Quality** (husky only): Runs linting and formatting on staged files

## Commands

- `npm run generate-api` - Generate from live server
- `npm run generate-schema` - Generate local schema and then API client  
- `npm run precommit:api` - Pre-commit friendly generation (won't fail if server is down)
- `npm run dev:with-api` - Start development with auto API generation

## Best Practices

### For Development
1. Keep FastAPI server running during development: `npm run dev:with-api`
2. API client will auto-update on each commit
3. Review generated changes before pushing

### For Team Collaboration
1. Always commit the generated `src/api/` directory
2. Don't modify generated files manually (they'll be overwritten)
3. Update backend OpenAPI documentation when changing endpoints

### Troubleshooting

**"Could not regenerate API client"**
- Start the FastAPI server: `cd .. && source venv/bin/activate && uvicorn fastapi_server:app --reload --port 8866`
- Or use local schema generation: `npm run generate-schema`

**Pre-commit hook not running**
- Check if hooks are executable: `chmod +x .git/hooks/pre-commit .husky/pre-commit`
- For husky: ensure packages are installed: `npm install`

**API client out of sync**
- Manually regenerate: `npm run generate-schema`
- Commit the updated files

## Disabling (if needed)

### Temporarily skip pre-commit hooks
```bash
git commit -m "your message" --no-verify
```

### Disable git hook permanently
```bash
rm .git/hooks/pre-commit
```

### Disable husky permanently
```bash
rm -rf .husky
npm uninstall husky lint-staged
# Remove "prepare" script from package.json
```

## Benefits

✅ **Always in sync**: API client matches your backend  
✅ **Type safety**: No runtime errors from API changes  
✅ **Team consistency**: Everyone gets the same generated code  
✅ **Zero maintenance**: Happens automatically on commits  
✅ **Fail-safe**: Won't block commits if generation fails