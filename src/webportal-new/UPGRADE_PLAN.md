# Webportal-New Upgrade Plan

## Goal
Upgrade all packages to latest versions compatible with Node.js 24

## Phase 1: Package Replacements (Breaking Changes)

### 1. Replace react-monaco-editor → @monaco-editor/react
- **Files to update**: `src/app/components/monaco-editor.jsx`
- **Reason**: react-monaco-editor is outdated, @monaco-editor/react is actively maintained
- **Impact**: 1 wrapper file + 6-10 components using the wrapper

### 2. Replace joi-browser → zod
- **Files to update**: ~9 files with validation schemas
  - `src/app/job-submission/components/tab-form.jsx`
  - `src/app/job-submission/models/protocol-schema.js`
  - `src/app/job-submission/models/job-protocol.js`
  - `src/app/job/job-view/fabric/job-transfer.jsx`
  - `src/app/user/fabric/utils.js`
  - `src/app/user/fabric/user-profile/bounded-cluster-dialog.jsx`
  - `src/app/job-submission-demo/models/protocol-schema.js`
  - `src/app/job-submission-demo/models/job-protocol.js`
- **Reason**: joi-browser is unmaintained, zod is modern and TypeScript-friendly
- **Impact**: Need to rewrite validation schemas

### 3. Remove node-rsa → Use native crypto
- **Files to update**: 2 files
  - `src/app/job-submission/utils/ssh-keygen.js`
  - `src/app/job-submission-demo/utils/ssh-keygen.js`
- **Reason**: node-rsa has security issues
- **Impact**: Small - rewrite key generation logic

### 4. Remove sshpk → Alternative or native
- **Files to update**: 3-4 files
  - `src/app/job-submission/utils/ssh-keygen.js`
  - `src/app/job-submission-demo/utils/ssh-keygen.js`
  - `src/app/user/fabric/user-profile/ssh-list-dialog.jsx`
- **Reason**: sshpk has security advisories
- **Impact**: Small - SSH key parsing logic

### 5. Remove deprecated webpack loaders
- json-loader (webpack 5 native)
- file-loader (use asset/resource)
- raw-loader (use asset/source)
- url-loader (use asset/inline)

## Phase 2: Major Version Upgrades

### Packages to upgrade (may have breaking changes):
- React 18 → 19
- Bootstrap 3 → 5 (MAJOR IMPACT - keep for now?)
- ESLint 8 → 9
- Express 4 → 5
- marked 11 → 17
- react-router-dom 6 → 7
- datatables packages (if keeping jQuery/DataTables)

## Phase 3: Keep Current (Large Refactor Required)

These require major code refactoring and should be deferred:
- ❌ jQuery (70+ usages, DataTables dependency)
- ❌ Bootstrap 3 → 5 (all templates need updating)
- ❌ AdminLTE (6 components, complete UI overhaul)
- ❌ DataTables (3 components, or replace with React table)

## Strategy

1. First: Install ncu (npm-check-updates) and upgrade all non-breaking packages
2. Replace deprecated packages one by one
3. Test build after each major change
4. Run npm audit and fix security issues
5. Build Docker image and test

## Breaking Change Exceptions

For packages that would require massive refactoring:
- Keep Bootstrap 3 for now (or plan separate UI migration project)
- Keep jQuery (required by DataTables, Bootstrap 3, AdminLTE)
- Keep DataTables (or plan separate React table migration)
- Keep AdminLTE 2 (or plan separate UI framework migration)
