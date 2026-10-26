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
- [Reviewing translations](#reviewing-translations)
  - [Offline checks](#offline-checks)
  - [Model review](#model-review)
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

This does not do fuzzy matching: a string whose text changed shows up as a new, empty entry rather than as a guessed translation flagged `fuzzy`, and the old translation moves to an obsolete `#~` entry. The trade-off is that even a trivial rewording of a string now needs a full retranslation.

If a catalog already has `fuzzy` entries (from an earlier update), `make i18n-clear-fuzzy` blanks them and removes the flag, so they are translated like any other missing string (by hand, in Option A below). This **discards the text** of those fuzzy translations; `make i18n-autotranslate` already retranslates fuzzy entries, so Option B does not need it:

```bash
make i18n-clear-fuzzy
```

### 3. Translate

You have two options for translation:

**Option A: Manual Translation**
Edit the `.po` files (e.g., `httplint/translations/fr/LC_MESSAGES/messages.po`) to add missing translations or correct existing ones.

**Option B: Auto-Translation**
Use an LLM (via the `llm` package) to automatically translate missing strings. You can specify the model using the `MODEL` variable (default: `mlx-community/aya-expanse-8b-4bit`) and the rate limit using `RPM` (default: unlimited; this is for remote models).

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

## Reviewing translations

Machine translations need checking, and most maintainers cannot read every language. There are two layers: free offline checks, and an optional model review. Both are advisory.

### Offline checks

`make i18n-check` (part of `make test`) fails only on `BAD_VARIABLE` and `SYNTAX_ERROR`. It also reports, without failing:

* `MISSING`, `FUZZY`: no translation, or marked fuzzy.
* `LINK_MISMATCH`: the URLs and Markdown link targets in the translation differ from the English, or the number of well-formed `[text](target)` links does (a space before the `(`, an unclosed link, or lost brackets around a URL that is still there).
* `TOKEN_CHANGED`: a backtick-quoted header name, token or value in the English (a single token such as `Cache-Control` or `bytes`, a `Name: value` line, or the code of a status like `404 (Not Found)`) does not appear verbatim in the translation. Spans containing placeholders, bare punctuation and prose are ignored, so some changes will be missed.
* `DUPLICATED_TEXT`: more sentences repeat within the translation than within the English, or a placeholder occurs more often than in the English. Only exact repeats are found; a paraphrased restatement is not (the model review can catch those).
* `SUSPICIOUS_LENGTH`: the translation is much shorter or longer than the English (ratio outside 0.5-2.2, or 0.2-1.4 for `ja` and 0.12-1.2 for `zh`; strings under 30 characters are skipped).
* `PREAMBLE`: the translation starts with model chatter ("Here is the translation", "Certainly", "As an AI", a refusal, in the supported languages) or a code fence, ends with commentary ("(Note: ...)", "Let me know if..."), or contains `<think>` tags.

There is no check for a translation that is identical to the English (an untranslated string).

A flag means "look at this", not "this is wrong".

To have flagged entries retranslated, `make i18n-clear-flagged` blanks them (and any fuzzy entries), discarding their text. `make i18n-check MARK_FUZZY=1` only marks them fuzzy. A release pass:

```bash
make i18n-update
make i18n-clear-flagged
make i18n-autotranslate
make i18n-check
```

### Model review

`make i18n-review` asks a language model to judge each translation (meaning, technical register, header names and acronyms left in English, Markdown and placeholders preserved). It is not part of `make test`, and it needs a model you choose; there is no default.

```bash
# Claude (needs an API key; this costs money)
./.venv/bin/llm install llm-anthropic
./.venv/bin/llm keys set anthropic
./.venv/bin/llm models                      # find the model id
make i18n-review MODEL=<model id> LOCALE=fr SINCE=origin/main
```

A local MLX model should also work through `llm-mlx` (installed by `make venv-i18n`) once its model has been downloaded, with no key and no cost per call. That path has not been tested with this tool.

Options (as `make` variables):

* `LOCALE`: a locale such as `fr`, or `all` (the default).
* `SINCE=REF`: only review entries whose translation is new or changed compared with the catalog at git ref `REF`, which is what you want after retranslating.
* `LIMIT=N`: review at most N entries per locale.
* `YES=1`: required if more than 50 model calls could be made. The count is the worst case, entries x (1 + `BACKTRANSLATE`) x 2, because a reply that is not valid JSON is retried once. `DRY_RUN=1` shows it.
* `BACKTRANSLATE=1`: first translate each translation back to English in a separate call, without showing the original, then compare meanings. It doubles the number of calls.
* `MARK_FUZZY=1`: set the `fuzzy` flag on entries judged "major". It means "queued for retranslation or manual fix": `make i18n-compile` skips them (English is shown instead) and `make i18n-check` lists them. Off by default. Be aware that `make i18n-autotranslate` and `make i18n-clear-fuzzy` DISCARD the msgstr of fuzzy entries, and the reviewer's suggestion with it, because suggestions live only in the report file. Copy any suggestion you want before running either.
* `DRY_RUN=1`: list what would be reviewed and how many model calls it would take; calls nothing, and needs no `MODEL`.

The report is written to `i18n-review-<locale>.md` in the current directory (git-ignored), with major problems first: each entry shows the English, the current translation, the problems found and a suggested replacement. It is rewritten after every entry, so Ctrl-C (or a run aborted by repeated model errors) keeps a partial report. The review never changes a translation; apply any suggestion by hand in the `.po` file.

The strings are sent to the model inside delimited blocks marked as data, with a random delimiter, so that text that looks like instructions is judged rather than obeyed. That reduces the risk but a model can still be fooled, which is another reason to keep `MARK_FUZZY` off unless you will read the report.

Cost and privacy: every reviewed string, and its translation, is sent to the model's provider. Check that this is acceptable, and use `DRY_RUN=1`, `SINCE` and `LIMIT` to keep the number of calls down. Models make mistakes in both directions, so treat the verdicts as a second opinion, not a gate; a native speaker is still the best reviewer.

## Adding a New Language

To add a new language (e.g., Spanish `es`):

```bash
make init_locale LOCALE=es
```
Then follow steps 2-5 above.
