# React Hooks Linting Setup ✅

This document confirms that Biome is properly configured to enforce React's Rules of Hooks in your project.

## Configuration Summary

### Biome Configuration (`biome.json`)

The following React hooks rules are enforced:

```json
{
  "linter": {
    "rules": {
      "correctness": {
        "useHookAtTopLevel": "error",
        "useExhaustiveDependencies": "warn"
      }
    }
  }
}
```

### Rules Enforced

✅ **`useHookAtTopLevel`**: Prevents calling hooks conditionally or inside loops
- Catches hooks in `if` statements
- Catches hooks in `for/while` loops  
- Catches hooks called outside React components
- Set to **error** level (fails build)

✅ **`useExhaustiveDependencies`**: Ensures all dependencies are included in hook dependency arrays
- Warns about missing dependencies in `useEffect`, `useCallback`, etc.
- Set to **warn** level (shows warning but doesn't fail build)

## Available Scripts

### Check All Linting
```bash
npm run lint:biome       # Run all Biome rules
npm run check           # Run Biome check (lint + format)
npm run check:fix       # Run Biome check and auto-fix issues
```

### Check Only Hooks Rules
```bash
npm run lint:hooks      # Check only React hooks rules
```

### Format Code
```bash
npm run format          # Format code with Biome
npm run format:check    # Check formatting without changing files
```

## Pre-commit Integration

The setup includes automatic enforcement via:

1. **Husky pre-commit hook** (`.husky/pre-commit`)
2. **lint-staged** configuration in `package.json`
3. **Biome check** runs on all staged files before commit

## Verification Test Results

✅ **Conditional hooks detected**: `useState` inside `if` statement
✅ **Hooks in loops detected**: `useEffect` inside `for` loop  
✅ **Hooks outside components detected**: `useState` at module level
✅ **Clean codebase**: No Rules of Hooks violations found in actual code

## Example Violations Caught

```tsx
// ❌ Conditional hook - CAUGHT
if (condition) {
  const [state] = useState(0) // Error: useHookAtTopLevel
}

// ❌ Hook in loop - CAUGHT  
for (let i = 0; i < 3; i++) {
  useEffect(() => {}, []) // Error: useHookAtTopLevel
}

// ❌ Hook outside component - CAUGHT
const globalState = useState(0) // Error: useHookAtTopLevel

// ❌ Missing dependency - CAUGHT
useEffect(() => {
  console.log(someVariable) // Warning: useExhaustiveDependencies
}, []) // Missing someVariable in deps
```

## Current Status

- ✅ Biome configuration is correct
- ✅ React hooks rules are active and working
- ✅ Pre-commit hooks are configured
- ✅ No Rules of Hooks violations in codebase
- ⚠️  2 minor dependency warnings in `CardsPage.tsx` (can be fixed if desired)

## Next Steps

1. **Optionally fix dependency warnings**:
   ```bash
   npm run lint:hooks -- --write
   ```

2. **Team education**: Ensure all developers understand the Rules of Hooks

3. **CI Integration**: Consider adding `npm run lint:hooks` to your CI pipeline

## Resources

- [React Rules of Hooks](https://reactjs.org/docs/hooks-rules.html)
- [Biome Linter Rules](https://biomejs.dev/linter/rules/)
- [Biome useHookAtTopLevel rule](https://biomejs.dev/linter/rules/use-hook-at-top-level/)

---

**Status**: ✅ Complete - React hooks rules are properly enforced