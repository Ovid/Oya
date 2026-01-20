# Case-Preserving Slugs Design

## Problem

The left-hand sidebar displays filenames in lowercase because the `path_to_slug()` function lowercases all characters. This loses case information, making paths like `lib/MooseX/Extended.pm` display as `lib/moosex/extended.pm`.

## Solution

Preserve case in slug generation so the frontend can accurately reconstruct display paths.

## Changes

### Backend: `backend/src/oya/generation/summaries.py`

Change line 45 from:
```python
slug = re.sub(r"[^a-z0-9-]", "", slug.lower())
```

To:
```python
slug = re.sub(r"[^a-zA-Z0-9-]", "", slug)
```

### Frontend: `frontend/src/components/Sidebar.tsx`

Update the `FILE_EXTENSIONS.has()` check to lowercase just the extension for lookup:
```typescript
if (FILE_EXTENSIONS.has(lastPart.toLowerCase()) && parts.length >= 2) {
```

Remove the comment explaining that case information is lost (lines 79-84).

## Migration

Existing wikis generated with lowercase slugs will have different filenames than newly generated ones. Users must regenerate their wiki to see correct casing. No automated migration path is provided.

## Testing

- Generate wiki for a codebase with mixed-case paths
- Verify sidebar displays correct casing
- Verify navigation still works (slugs in URLs are case-sensitive)
