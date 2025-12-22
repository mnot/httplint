# Translation

This document outlines the process for adding and updating translations in `httplint`.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Guidelines for Translators](#guidelines-for-translators)
- [Guidelines for Code](#guidelines-for-code)
- [Workflow](#workflow)
  - [1. Extract Messages](#1-extract-messages)
  - [2. Update PO Files](#2-update-po-files)
  - [3. Translate](#3-translate)
  - [4. Compile](#4-compile)
  - [5. Verify](#5-verify)
- [Adding a New Language](#adding-a-new-language)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Guidelines for Translators

Suggestions and corrections for the translations in `redbot/translations` are welcome as GitHub Pull Requests. A few guidelines for doing so:

* Assume a technical audience, but prioritise clarity, accuracy, and brevity. Do not assume deep domain-specific knowledge about HTTP.
* Keep "%(foo)s" style variable in your content.
* Line endings are not important.

In your PR, please do not modify any file except for the .po. Making multiple suggestions in the same PR is fine.


## Guidelines for Code

Code that contains user-facing strings should follow these guidelines:

*   **Note Classes**: Strings assigned to `_summary` and `_text` in `Note` subclasses are automatically extracted.
*   **Other Strings**: For other strings (e.g., class attributes, global constants), use the `L_` lazy translation marker from `httplint.i18n`.
    ```python
    from httplint.i18n import L_

    MY_STRING = L_("This is a translatable string")
    ```
    Ensure these strings are passed to `translate()` (from `httplint.i18n`) before being displayed or used in a context requiring translation.
*   **Plurals**: Use `ngettext` from `httplint.i18n` for strings that have singular and plural forms.
    ```python
    from httplint.i18n import ngettext

    msg = ngettext("%(num)s item", "%(num)s items", count) % {"num": count}
    ```
*   **Direct Translation**: You can also use `translate()` directly for strings that don't need to be defined at module level (but `L_` is preferred for clarity).


## Workflow

### 1. Extract Messages

When code changes, new translatable strings might be added. This will update the `.po` files in `httplint/translations` with any new strings from `httplint/translations/messages.pot`.

```bash
make i18n-extract
```

### 2. Update PO Files

Update the `.po` files for all locales to include the new strings from the template:

```bash
make i18n-update
```

### 3. Translate

You have two options for translation:

**Option A: Manual Translation**
Edit the `.po` files (e.g., `httplint/translations/fr/LC_MESSAGES/messages.po`) to add missing translations or correct existing ones.

**Option B: Auto-Translation**
Use an LLM (via the `llm` package) to automatically translate missing strings. You can specify the model using the `MODEL` variable (default: `mlx-community/aya-23-8B-4bit`) and the rate limit using `RPM` (default: unlimited; this is for remote models).

```bash
make i18n-autotranslate MODEL=gemini-1.5-flash-latest RPM=60
```
*Note: To use remote models you must have the `llm` package configured with valid API keys (e.g., `./.venv/bin/llm keys set gemini`).*

### 4. Compile

Compile the `.po` files into binary `.mo` files for use at runtime:

```bash
make i18n-compile
```

### 5. Verify

Run `httplint` with the target locale to verify the translations:

```bash
./.venv/bin/httplint --locale fr <url>
```

## Adding a New Language

To add a new language (e.g., Spanish `es`):

```bash
make init_locale LOCALE=es
```
Then follow steps 2-5 above.
