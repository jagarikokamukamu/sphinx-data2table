# Sphinx Data2Table 拡張機能 デモ

<!-- datatable / data-table ディレクティブの動作デモ -->
`sphinx_data2table` 拡張機能を使用して、YAML、TOML、および JSON 形式の構造化データを表としてレンダリングするデモドキュメントです。

## 1. YAML インライン記述の例 (`data-table`)

```{data-table}
:format: yaml

- 機能名: "**YAML / TOML / JSON サポート**"
  詳細説明: |
    第1段落のテキストです。

    第2段落のテキスト（リスト含む）：
    - リスト項目 A
    - リスト項目 B
    - リスト項目 C
  備考: "`yaml` / `toml` / `json` 形式にフル対応"

- 機能名: "**Markdown セルパース**"
  詳細説明: |
    セルの記述は **Markdown** としてパースされます。  
    （行末スペース2個による改行のテスト）
  備考: "[MyST Parser](https://myst-parser.readthedocs.io/) 連携"
```

## 2. TOML インライン記述の例

```{data-table}
:format: toml

[[items]]
"項目" = "**TOML 箇条書き機能**"
"内容" = """
セル内に箇条書きリストを含める例：

* 項目 1
* 項目 2
"""

[[items]]
"項目" = "**改段落機能**"
"内容" = """
前段落の文章です。

後段落の文章です。
"""
```

## 3. JSON インライン記述の例

```{data-table}
:format: json

[
  {
    "機能名": "**JSON サポート**",
    "詳細説明": "標準の `json` モジュールを用いてパースされます。",
    "備考": "`:format: json` オプション指定"
  },
  {
    "機能名": "**エイリアス機能**",
    "詳細説明": "`data-table` ディレクティブおよび `datatable` の両名に対応。",
    "備考": "互換性確保"
  }
]
```

## 4. 外部ファイルからの読み込み例

```{data-table}
:file: sample_data.yaml
```
