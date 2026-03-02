# npm Publishing Setup for @openintentai/mcp-server

This document describes the one-time setup steps needed to publish `@openintentai/mcp-server` to npm.

## 1. Create the npm Organization

The package uses the `@openintentai` scope, which requires an npm organization.

1. Go to [npmjs.com/signup](https://www.npmjs.com/signup) (or log in)
2. Go to [npmjs.com/org/create](https://www.npmjs.com/org/create)
3. Create an organization named `openintent`
4. Choose the **free** plan (public packages only)

If someone else owns the `openintent` scope, you'll need to either:
- Contact them to be added as a member
- Use a different scope (e.g., `@openintent-ai/mcp-server`) and update `package.json` accordingly

## 2. Generate an npm Access Token

1. Go to [npmjs.com/settings/tokens](https://www.npmjs.com/settings/~/tokens)
2. Click **Generate New Token**
3. Select **Automation** type (for CI use)
4. Copy the token (starts with `npm_`)

## 3. Add the Token to GitHub

1. Go to your GitHub repo: `github.com/openintent-ai/openintent`
2. Navigate to **Settings > Secrets and variables > Actions**
3. Click **New repository secret**
4. Name: `NPM_TOKEN`
5. Value: paste the npm token from step 2

## 4. Create the GitHub Environment

The publish workflow uses a `npm` environment for protection.

1. Go to **Settings > Environments** in your GitHub repo
2. Click **New environment**
3. Name: `npm`
4. Optionally add protection rules:
   - **Required reviewers**: Add yourself so publishes require manual approval
   - **Deployment branches**: Restrict to `main` only

## 5. Publish

Publishing happens automatically when you create a GitHub Release:

1. Go to **Releases > Draft a new release**
2. Create a tag (e.g., `v0.13.1`)
3. Publish the release

The `publish.yml` workflow triggers on release and:
- Publishes the Python SDK to PyPI (existing behavior)
- Builds and publishes the MCP server to npm (new)

Both happen in parallel. If one fails, the other still proceeds.

## Manual First Publish

For the very first publish, you may want to do it manually to verify everything works:

```bash
cd reference-implementation/mcp-server
npm install
npm run build
npm login  # log in with your npm account
npm publish --access public
```

## Version Sync

The MCP server version should be kept in sync with the Python SDK version. When bumping versions, update:

1. `reference-implementation/pyproject.toml` (Python SDK)
2. `reference-implementation/openintent/__init__.py` (Python SDK)
3. `reference-implementation/mcp-server/package.json` (MCP server)
4. `reference-implementation/mcp-server/src/index.ts` (hardcoded in Server constructor)

## Verifying Publication

After publishing, verify:

```bash
# Check npm
npm info @openintentai/mcp-server

# Test npx
npx -y @openintentai/mcp-server --help
```
