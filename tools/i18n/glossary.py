"""
Per-language data for the rules in rules.py. Edit this file to change terminology.

An Entry applies when its `when` regex matches the English msgid (code spans, URLs and
placeholders removed; case-insensitive). It is violated when one of the `avoid` regexes
matches the translation (same clean-up). `prefer` is named in the retry message and
in the prompt. Lines marked LOW are style calls on which the two reviews were unsure.
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Entry:
    term: str  # English term, as shown to the model
    when: str
    prefer: str
    avoid: Tuple[str, ...]


# 'header' as a common noun: not part of a hyphenated name like Cross-Origin-Opener-Policy-header
_HEADER = r"(?<![\w-])headers?(?![\w-])"
# 'origin' as a common noun: not Cross-Origin, and not the Origin field
_ORIGIN = r"(?<![\w-])origins?(?![\w-])(?!\s+(?:header|field))"

GLOSSARY: Dict[str, Tuple[Entry, ...]] = {
    "ja": (
        Entry("directive", r"\bdirectives?\b", "ディレクティブ", ("指示",)),
        Entry("origin", _ORIGIN, "オリジン", ("起源", "原産地")),
        Entry("parameter", r"\bparameters?\b", "パラメータ", ("パラメーター",)),
        Entry("header", _HEADER, "ヘッダー", ("ヘッダ(?!ー)",)),
        Entry("value", r"^(?!.*\bvariables?\b).*\bvalues?\b", "値", ("変数",)),
        Entry("response", r"\bresponses?\b", "レスポンス", ("応答",)),  # LOW
        Entry("field", r"\bfields?\b", "フィールド", ("分野",)),
        Entry("status code", r"\bstatus codes?\b", "ステータスコード", ("状態コード",)),
        Entry("stale", r"\bstale\b", "古い", ("スタレ", "スタール")),  # LOW
        Entry("decompress", r"\bdecompress", "展開", ("デ圧縮", "デコンパイル")),  # LOW
        Entry("coding", r"\bcodings?\b", "コーディング", ("(?<!ステータス)コード(?!ン)",)),  # LOW
        Entry("freshness", r"\bfresh(?:ness)?\b", "鮮度", ("更新性", "新鮮")),  # LOW
        Entry("reverse proxy", r"\breverse prox", "リバースプロキシ", ("逆プロキシ",)),
        Entry("store", r"(?<![\w-])stor(?:e|es|ed|ing|age)\b", "保存", ("格納", "ストア")),  # LOW
        Entry("deprecated", r"\bdeprecat", "非推奨", ("廃止",)),
        Entry("media range", r"\bmedia ranges?\b", "メディア範囲", ("メディアレンジ",)),
        Entry("inner list", r"\binner lists?\b", "内部リスト", ("インナーリスト",)),
    ),
    "zh": (
        Entry(
            "header",
            _HEADER,
            "标头",
            ("头部", "报头", "接受头", "报告头", "头信息", "请求头", "响应头", "首部"),
        ),
        Entry("origin", _ORIGIN, "源", ("来源", "起源")),
        Entry("speculation rule", r"\bspeculation rules?\b", "推测规则", ("猜测规则",)),  # LOW
        Entry("preflight", r"\bpreflight", "预检", ("预飞行",)),
        Entry("cookie", r"\bcookies?\b", "Cookie", ("饼干",)),
        Entry("intermediary", r"\bintermediar", "中间节点", ("中间人",)),
        Entry("freshness", r"\bfreshness\b", "新鲜度", ("最新",)),  # LOW
        Entry("stale", r"\bstale\b", "过期", ("过时",)),  # LOW
        Entry("inner list", r"\binner lists?\b", "内部列表", ("内列表",)),
        Entry("advertise", r"\badvertis(?:e|es|ed|ing)\b", "通告", ("宣传", "广告")),  # LOW
        Entry("on the wire", r"\bon the wire\b", "传输中", ("电缆",)),
        Entry("you", r"\byou\b", "您", ("你",)),  # LOW
    ),
    "es": (
        Entry("header", _HEADER, "cabecera", ("encabezado",)),
        Entry("supported", r"\bsupported\b", "compatible", (r"soportad[oa]s?",)),  # LOW
    ),
    "fr": (
        # the English word left in the translation
        Entry("header", _HEADER, "en-tête", (_HEADER,)),
    ),
}

# RFC 2119 words: (MUST-like, SHOULD-like) regexes per language.
STRENGTH: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {
    "fr": (
        (r"(?<!\w)(?:doit|doivent|devez)(?!\w)",),
        (r"(?<!\w)(?:devrait|devraient|devriez)(?!\w)",),
    ),
    "es": (
        (r"(?<!\w)(?:debe|debes|deben)(?!\w)",),
        (r"(?<!\w)(?:debería|deberías|deberían)(?!\w)",),
    ),
    "ja": (
        (
            "なければなりません",
            "なければならない",
            "ねばなりません",
            "必要があります",
            "てはなりません",
        ),
        ("べき", "ほうがよい", "ほうが良い", "方がよい", "方が良い", "推奨"),
    ),
    "zh": (("必须",), ("应该", "应当", "不应", "建议", "推荐")),
}
