# Webportal-New Package Upgrades Summary

## Completed: March 25, 2026

### Environment
- Node.js: 18 → **24.14.1**
- npm: 9 → **11.11.0**
- Docker base image: node:20-alpine → **node:24-alpine**

### Major Framework Upgrades

#### React Ecosystem
- react: 18.2.0 → **19.2.4** (Major)
- react-dom: 18.2.0 → **19.2.4** (Major)
- @types/react: 18.2.48 → **19.2.14** (Major)
- @types/react-dom: 18.2.18 → **19.2.3** (Major)
- react-redux: 9.0.4 → **9.2.0**
- react-router-dom: 6.21.1 → **7.13.2** (Major)
- react-responsive: 9.0.2 → **10.0.1** (Major)

#### UI Frameworks & Libraries
- bootstrap: 3.4.1 → **5.3.8** (Major - Breaking Changes Expected)
- admin-lte: 2.4.2 → **3.2.0** (Major - Breaking Changes Expected)
- jquery: 3.7.1 → **4.0.0** (Major)
- font-awesome: 4.7.0 → REMOVED
- @fortawesome/fontawesome-free: **6.7.2** (NEW)
- @fluentui/react: 8.118.0 → **8.125.5**

#### Build Tools
- webpack: 5.89.0 → **5.105.4**
- webpack-cli: 5.1.4 → **7.0.2** (Major)
- webpack-dev-server: 4.15.1 → **5.2.3** (Major)
- webpack-bundle-analyzer: 4.10.1 → **5.3.0** (Major)
- copy-webpack-plugin: 11.0.0 → **14.0.0** (Major)

#### Babel
- @babel/core: 7.23.7 → **7.29.0**
- @babel/preset-env: 7.23.7 → **7.29.2**
- @babel/preset-react: 7.23.3 → **7.28.5**
- babel-loader: 9.1.3 → **10.1.1** (Major)

#### CSS/Styling
- css-loader: 6.8.1 → **7.1.4** (Major)
- sass-loader: 13.3.3 → **16.0.7** (Major)
- sass: 1.69.7 → **1.98.0**
- style-loader: 3.3.3 → **4.0.0** (Major)
- styled-components: 6.1.8 → **6.3.12**
- cssnano: 6.0.2 → **7.1.3** (Major)
- postcss: 8.4.32 → **8.5.8**
- postcss-loader: 7.3.4 → **8.2.1** (Major)
- postcss-import: 15.1.0 → **16.1.1** (Major)
- autoprefixer: 10.4.16 → **10.4.27**
- mini-css-extract-plugin: 2.7.6 → **2.10.1**

#### Linting & Code Quality
- eslint: 8.57.1 → **10.1.0** (Major)
- eslint-config-prettier: 9.1.0 → **10.1.8** (Major)
- eslint-plugin-import: 2.29.1 → **2.32.0**
- eslint-plugin-n: 16.6.2 → **17.24.0** (Major)
- eslint-plugin-prettier: 5.1.2 → **5.5.5**
- eslint-plugin-promise: 6.1.1 → **7.2.1** (Major)
- eslint-plugin-react: 7.33.2 → **7.37.5**
- eslint-plugin-react-hooks: 4.6.0 → **7.0.1** (Major)
- prettier: 3.2.4 → **3.8.1**

#### Server & Backend
- express: 4.18.2 → **5.2.1** (Major - Breaking Changes)
- compression: 1.7.4 → **1.8.1**
- cookie-parser: 1.4.6 → **1.4.7**
- morgan: 1.10.0 → **1.10.1**
- winston: 3.11.0 → **3.19.0**
- dotenv: 16.3.1 → **17.3.1** (Major)

#### Data & Utilities
- joi: 17.11.0 → **18.1.1** (Major)
- marked: 11.1.1 → **17.0.5** (Major)
- luxon: 3.4.4 → **3.7.2**
- papaparse: 5.4.1 → **5.5.3**
- query-string: 8.1.0 → **9.3.1** (Major)
- fs-extra: 11.2.0 → **11.3.4**
- jsonwebtoken: 9.0.2 → **9.0.3**
- handlebars: 4.7.8 → (same, no upgrade available)

#### Editor & Monaco
- monaco-editor: 0.45.0 → **0.55.1**
- monaco-editor-webpack-plugin: 7.1.0 → **7.1.1**
- react-monaco-editor: 0.54.0 → REMOVED
- @monaco-editor/react: **4.7.3** (NEW)

#### DataTables
- datatables.net-buttons-bs: 2.4.2 → **3.2.6** (Major)
- datatables.net-plugins: 1.13.6 → **2.3.6** (Major)
- datatables.net-responsive-bs: 2.5.0 → **3.0.8** (Major)
- datatables.net-select-bs: 1.7.0 → **3.1.3** (Major)

#### Visualization
- d3: 7.8.5 → **7.9.0**
- billboard.js: 3.12.3 → **3.18.0**

#### Other Libraries
- @loadable/component: 5.16.4 → **5.16.7**
- classnames: 2.3.2 → **2.5.1**
- core-js: 3.35.0 → **3.49.0**
- app-root-path: 2.2.1 → **3.1.0** (Major)
- redux: 5.0.1 → (same)
- redux-saga: 1.3.0 → **1.4.2**
- js-yaml: 4.1.0 → **4.1.1**
- strip-json-comments: 5.0.1 → **5.0.3**
- readable-stream: 4.5.2 → **4.7.0**
- rimraf: 5.0.5 → **6.1.3** (Major)
- mkdirp: 3.0.1 → (same)
- html-loader: 4.2.0 → **5.1.0** (Major)
- html-webpack-plugin: 5.6.0 → **5.6.6**
- terser-webpack-plugin: 5.3.10 → **5.4.0**
- serve-favicon: 2.5.0 → **2.5.1**

### Package Replacements & Removals

#### Replaced
- ✅ `font-awesome@4.7.0` → `@fortawesome/fontawesome-free@6.7.2`
- ✅ `react-monaco-editor@0.54.0` → `@monaco-editor/react@4.7.3`
- ✅ `joi-browser@13.4.0` → `zod@3.24.4` (needs code migration)

#### Removed (Deprecated/Unsafe)
- ❌ `node-rsa@1.1.1` - Security issues, use native crypto
- ❌ `sshpk@1.18.0` - Security advisories, use alternative
- ❌ `file-loader@6.2.0` - Use webpack 5 asset modules
- ❌ `json-loader@0.5.7` - Webpack 5 handles JSON natively
- ❌ `raw-loader@4.0.2` - Use webpack 5 asset/source

### Breaking Changes to Address

#### High Priority (Required for Build)
1. **Bootstrap 3 → 5**: Major CSS class changes, grid system updates
   - Replace `.col-md-*` with Bootstrap 5 grid
   - Update modal, button, form classes
   - Remove jQuery dependencies from Bootstrap components

2. **jQuery 3 → 4**: API changes and compatibility
   - Review all `$` usages
   - Update DataTables integration
   - Test Bootstrap 5 compatibility

3. **React 18 → 19**: New APIs and deprecations
   - Review `ReactDOM.render` → `createRoot`
   - Check concurrent features
   - Update type definitions

4. **Express 4 → 5**: Breaking API changes
   - Update middleware patterns
   - Check route handling changes
   - Review error handling

5. **ESLint 8 → 10**: Configuration and plugin updates
   - Update `.eslintrc` config format
   - Fix new rule violations
   - Ensure all plugins are compatible

6. **react-router-dom 6 → 7**: Routing API changes
   - Update route definitions
   - Check `useNavigate`, `useParams` usage
   - Review loader/action patterns

#### Medium Priority (Code Migration Needed)
1. **Webpack Loaders**: Migrate to asset modules
   - Replace `file-loader` with `type: 'asset/resource'`
   - Replace `json-loader` (remove, native support)
   - Replace `raw-loader` with `type: 'asset/source'`

2. **Monaco Editor**: Update wrapper component
   - Change imports from `react-monaco-editor` to `@monaco-editor/react`
   - Update API calls (slight differences)
   - Test all editor instances

3. **Joi → Zod**: Validation schema migration
   - Rewrite ~9 schema files
   - Update validation calls
   - Test all form validations

4. **Font Awesome**: Update icon references
   - Change CSS class names (`.fa-*` → `.fa-solid`, `.fa-regular`)
   - Update imports if using JS
   - Test all icon appearances

5. **node-rsa / sshpk**: Implement with native crypto
   - Rewrite SSH key generation (2 files)
   - Rewrite SSH key parsing (3-4 files)
   - Test key format compatibility

#### Low Priority (May Work As-Is)
1. **Admin-LTE 2 → 3**: May have visual changes
2. **DataTables bs → bs5**: Bootstrap 5 adapters
3. **marked 11 → 17**: Check for XSS fixes
4. **webpack-dev-server 4 → 5**: Config changes

### Next Steps

1. ✅ Run `npm install --legacy-peer-deps` (in progress)
2. ⏳ Fix ESLint configuration for v10
3. ⏳ Update webpack config (remove old loaders, add asset modules)
4. ⏳ Update Monaco Editor wrapper component
5. ⏳ Test build with `npm run build`
6. ⏳ Run `npm audit` and fix security issues
7. ⏳ Update Bootstrap/jQuery code (if time permits)
8. ⏳ Build Docker image
9. ⏳ Deploy and test

### Files Requiring Updates

#### Immediate (Build-Blocking)
- `.eslintrc` or `eslint.config.js` - ESLint 10 config
- `config/webpack.common.js` - Remove old loaders
- `src/app/components/monaco-editor.jsx` - Monaco wrapper

#### High Priority (Functionality)
- All files using Font Awesome icons
- Express server files (breaking changes in v5)
- React 19 migration points

#### Deferred (Large Refactor)
- Bootstrap 3 → 5 migration (all template files)
- jQuery removal (70+ usages)
- AdminLTE components (6 files)
- DataTables components (3 files)
- Joi → Zod migration (9 schema files)
- SSH key utilities (5 files)

### Security Status
- Before: 25 vulnerabilities (9 low, 7 moderate, 7 high, 2 critical)
- After: TBD (run `npm audit` after install completes)

---

*Generated on March 25, 2026*
*Node.js 24.14.1, npm 11.11.0*
