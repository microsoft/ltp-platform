# Immediate Breaking Changes to Fix

## Priority 1: Build-Blocking Issues

### 1. ESLint 10 Configuration
**Issue**: ESLint 8 → 10 has breaking config changes
**Files to update**:
- `.eslintrc.js` or `.eslintrc.json` → Need to use new flat config format
- May need to create `eslint.config.js`

**Actions**:
```bash
# Check current config
cat .eslintrc* 2>/dev/null

# ESLint 10 requires flat config or compatibility mode
# Options:
# A) Add ESLINT_USE_FLAT_CONFIG=false to use legacy config
# B) Migrate to flat config format (eslint.config.js)
```

### 2. Webpack Loaders - Remove Deprecated
**Issue**: file-loader, json-loader, raw-loader removed but may still be referenced in webpack config
**Files to update**:
- `config/webpack.common.js`
- `config/webpack.dev.js`
- `config/webpack.prod.js`

**Actions**:
- Remove `file-loader` - use `type: 'asset/resource'`
- Remove `json-loader` - webpack 5 handles JSON natively
- Remove `raw-loader` - use `type: 'asset/source'`

### 3. Monaco Editor Wrapper
**Issue**: Changed from `react-monaco-editor` to `@monaco-editor/react`
**Files to update**:
- `src/app/components/monaco-editor.jsx`

**Changes needed**:
```javascript
// OLD:
import MonacoEditor from 'react-monaco-editor';

// NEW:
import Editor from '@monaco-editor/react';

// API changes:
// - Component name: MonacoEditor → Editor
// - Props slightly different (check docs)
```

## Priority 2: Runtime Breaking Changes

### 4. Express 5 API Changes
**Issue**: Express 4 → 5 has middleware and routing changes
**Files to check**:
- `server.js` or `server/index.js`
- Any custom middleware files

**Key changes**:
- `app.del()` removed, use `app.delete()`
- Path routing syntax changes
- Middleware signature changes
- Body parser now built-in

### 5. React 19 Changes
**Issue**: React 18 → 19 deprecations and new features
**Files to check**:
- All files using `ReactDOM.render`
- Files using deprecated lifecycle methods

**Changes**:
- `ReactDOM.render` → `ReactDOM.createRoot().render()`
- Check for deprecated lifecycle methods
- PropTypes warnings

### 6. react-router-dom 7 API Changes
**Issue**: v6 → v7 has route definition changes
**Files to check**:
- Route definition files
- Components using `useNavigate`, `useParams`, etc.

**Changes**:
- Route component structure may have changed
- Loader/action API updates
- Check migration guide

## Priority 3: Styling & UI Changes

### 7. Bootstrap 3 → 5 Class Changes
**Issue**: Major CSS class name changes
**Scope**: Affects ALL template and component files

**Common changes**:
```
.col-md-* → .col-md-* (same but need BS5 grid)
.panel → .card
.panel-heading → .card-header
.panel-body → .card-body
.btn-default → .btn-secondary
.hidden-* → .d-none .d-*-block
.pull-right → .float-end
.pull-left → .float-start
```

**Strategy**:
- This is MASSIVE - may need to defer
- Or use Bootstrap 3 compatibility shim
- Or gradually migrate page by page

### 8. Font Awesome 4 → 6 Icon Changes
**Issue**: Icon class names changed
**Files**: All files using Font Awesome icons

**Changes**:
```
.fa .fa-icon → .fa-solid .fa-icon
               .fa-regular .fa-icon
               .fa-brands .fa-icon
```

### 9. jQuery 3 → 4 Changes
**Issue**: jQuery 4 has some API deprecations
**Files**: Any files using jQuery directly

**Check for**:
- Deprecated jQuery methods
- Plugin compatibility (DataTables, Bootstrap)

### 10. Admin-LTE 2 → 3 Changes
**Issue**: AdminLTE template structure changes
**Files**: Components using AdminLTE classes

**Changes**:
- Box classes updated
- Sidebar structure may differ
- Color scheme classes updated

## Quick Fix Strategy

### Option A: Minimal Fixes (Get Build Working)
1. Fix ESLint config (use legacy mode)
2. Update webpack config (remove old loaders)
3. Update Monaco wrapper
4. Add Bootstrap/jQuery compatibility shims if needed
5. Test build

### Option B: Defer Major UI Changes
Keep Bootstrap 3, jQuery 3 by:
1. Downgrade bootstrap: `"bootstrap": "~3.4.1"`
2. Downgrade jquery: `"jquery": "~3.7.1"`
3. Keep admin-lte: `"admin-lte": "~2.4.2"`
4. Fix only build-blocking issues
5. Plan UI migration as separate project

### Option C: Full Migration (Time-Intensive)
1. Migrate all Bootstrap classes
2. Update all Font Awesome icons
3. Update AdminLTE templates
4. Test every page
5. Fix jQuery compatibility

## Recommendation

**For Now**: Option A or B
- Focus on getting the build working
- Fix ESLint, webpack, Monaco issues
- Consider reverting Bootstrap/jQuery/AdminLTE to old versions
- Do comprehensive UI migration later as dedicated project

**Next Sprint**: Plan full UI migration
- Budget 2-4 weeks for Bootstrap 3 → 5
- Create UI component library
- Migrate page by page with QA

---

## Commands to Run After npm install

```bash
# 1. Check what's installed
npm list --depth=0 | grep -E "(bootstrap|jquery|admin-lte|eslint|monaco)"

# 2. Test build
npm run build

# 3. Check for ESLint errors
npm run lint

# 4. Run audit
npm audit

# 5. If build fails, check specific errors and fix one by one
```

---

*Created: March 25, 2026*
*Part of Node.js 24 + Package Upgrade Project*
