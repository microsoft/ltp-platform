# js-yaml Upgrade from v3 to v4

## Summary

Upgraded `js-yaml` from `~3.13.1` to `^4.1.0` to fix compatibility issues with modern Node.js and the upgraded `openpai-js-sdk`.

## Changes Made

### 1. Package Version Update

**File:** `package.json`

```diff
- "js-yaml": "~3.13.1",
+ "js-yaml": "^4.1.0",
```

### 2. API Updates

js-yaml v4 changed the API names for safety reasons:

| v3 API (Old)      | v4 API (New)  | Notes                          |
|-------------------|---------------|--------------------------------|
| `yaml.safeLoad()` | `yaml.load()` | Now safe by default           |
| `yaml.safeDump()` | `yaml.dump()` | Now safe by default           |

### 3. Files Updated

The following files were updated to use the new API:

1. `src/app/job-submission/utils/conn.js`
2. `src/app/job-submission/models/job-protocol.js`
3. `src/app/job-submission/yaml-edit-page.jsx`
4. `src/app/job-submission/components/yamledit-topbar/yamledit-export-config.jsx`
5. `src/app/job-submission-demo/utils/conn.js`
6. `src/app/job-submission-demo/models/job-protocol.js`
7. `src/app/job/job-view/fabric/job-transfer.jsx`
8. `src/app/job/job-view/fabric/job-detail.jsx`
9. `src/app/job/job-view/fabric/job-detail/components/summary.jsx`
10. `src/app/job/job-view/fabric/job-detail/components/task-role-container-list.jsx`
11. `src/app/job/job-view/fabric/task-attempt/task-attempt-list.jsx`

All occurrences of `yaml.safeLoad()` were replaced with `yaml.load()`.
All occurrences of `yaml.safeDump()` were replaced with `yaml.dump()`.

## Why This Change?

### Original Issue

The old `js-yaml` v3.13.1 had compatibility issues that caused bugs in the webportal when processing YAML configurations. This was identified during the webportal upgrade process.

### Benefits of v4

1. **Better Node.js Compatibility**: Works correctly with Node.js 20+
2. **Improved Security**: The default `load()` and `dump()` methods are now safe by default (equivalent to the old `safeLoad()` and `safeDump()`)
3. **Bug Fixes**: Resolves various parsing issues found in v3
4. **Consistency**: Matches the version used in the upgraded `openpai-js-sdk`

## Testing

After this upgrade, verify:

1. Job submission works correctly with YAML configs
2. Job config export/import functions properly
3. Job detail page displays YAML correctly
4. YAML editor can parse and save configurations

## Migration Notes

- ⚠️ **Breaking Change**: If you have code using `yaml.load()` or `yaml.dump()` (without "safe"), note that in v3 these were unsafe operations, but in v4 they are safe by default.
- ✅ **Backward Compatible**: All `safeLoad()` and `safeDump()` calls have been migrated to the v4 equivalents.
- ✅ **No Functional Changes**: The upgrade maintains the same security level - all operations are still safe.

## Related Changes

This upgrade was done in coordination with the `openpai-js-sdk` upgrade, which also updated its `js-yaml` dependency from `^3.13.1` to `^4.1.0`.

See: `src/openpai-js-sdk/CHANGELOG.md`
