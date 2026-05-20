# agent-careflow 実装計画書

作成日: 2026-05-19 JST  
対象 repository: `agent-careflow`  
目的: AI coding agent の業務プロセスを、医療現場風の「計画・オーダー・申し送り・インシデント・レビュー・退院処理」によって統制する中央運用基盤として実装する。

---

## 0. 要約

`agent-careflow` は、Codex / Claude Code / Cursor Composer を直接置き換える agent ではない。各 AI coding agent の外側にある、**記録・制約・オーケストレーション・監査の control repository** として実装する。

設計原則は次の通り。

1. **すべての静的ルール・設定・テンプレート・hooks・schemas・skills・subagent 定義は `agent-careflow` に置く。**
2. **個別タスクの runtime artifacts は対象 repository / worktree の `.careflow/` に置く。**
3. **PLAN と ORDER を分離する。** PLAN は症例単位の方針、ORDER は subagent への具体的・限定的な依頼である。
4. **LLM の自己申告ではなく、CLI / schema / hook / policy によって phase gate を判定する。**
5. **Codex / Claude / Cursor の差異は adapter に閉じ込め、policy logic を各ツール設定に重複実装しない。**
6. **実装より先に調査レポートを repo 内に出力し、公式情報・OSS 先行事例・コミュニティ情報を source registry として固定する。**

---

## 1. 背景思想

### 1.1 医療ワークフローから借りるもの

この project は医療システムを作るものではない。借りるのは clinical reasoning ではなく、以下の運用構造である。

| 医療現場の概念 | agent-careflow での対応 |
|---|---|
| 症例 / 患者 | Case / task / feature / bugfix |
| カルテ | `.careflow/cases/<case_id>/` |
| 治療計画 | `PLAN.md` |
| 医師オーダー | `orders/*.order.md` |
| 専門職 | researcher / implementer / verifier / reviewer / incident-commander |
| カンファレンス | phase transition conference / multi-agent review |
| 申し送り | result file / handoff summary |
| インシデントレポート | policy deviation / unsafe command / scope violation / failed verification |
| 退院処理 | final summary / PR body / cleanup / archive |
| 退院基準 | no open incidents, tests passed, review accepted, evidence attached |

中核は「人間や agent が判断した内容を、次の actor が参照できる形式で残す」ことである。chat transcript は補助資料にすぎず、正式な state ではない。

### 1.2 PLAN / ORDER 分離

`PLAN.md` は case 全体の方針であり、以下を含む。

- objective
- non-goals
- acceptance criteria
- risk class
- allowed scope
- phase plan
- subagent utilization plan
- evidence requirements
- rollback plan
- unresolved questions

`ORDER.md` は個別 subagent への限定指示であり、以下を含む。

- order id
- assigned role
- plan path
- plan hash
- allowed actions
- forbidden actions
- deliverables
- expected output format
- completion criteria

ORDER は原則 immutable とする。修正は既存 ORDER の編集ではなく、追補 ORDER を発行する。

### 1.3 中央 repo と対象 repo の分離

`agent-careflow` は control repository である。

```text
agent-careflow/
  rules/
  policies/
  schemas/
  templates/
  hooks/
  adapters/
  skills/
  agents/
  profiles/
  install/
  research/
```

対象 repo には runtime artifacts のみを置く。

```text
target-repo/
  .careflow/
    careflow.yaml
    state.json
    cases/
      ACF-20260519-001/
        CASE.yaml
        PLAN.md
        PLAN.lock.json
        orders/
        results/
        evidence/
        incidents/
        reviews/
        conferences/
        DISCHARGE.md
```

`.careflow/careflow.yaml` は中央 repo を指す。

```yaml
careflow_repo: "/Users/<user>/dev/agent-careflow"
profile: "business"
tools:
  codex: true
  claude: true
  cursor: true
```

private profile では `claude: false` とする。

---

## 2. 初期調査が必要な領域

実装前に `agent-careflow/research/` にレポートとして出力する。調査結果は `PLAN.md` と `design/*.md` の前提として参照する。

### 2.1 R-001: 医療現場ワークフロー調査

出力先:

```text
research/R-001-medical-workflow-patterns.md
```

調査対象:

- SBAR / ISBAR / I-PASS などの structured handoff
- clinical order / closed-loop communication
- discharge planning / transition of care
- incident reporting / sentinel event / RCA / corrective action plan
- multidisciplinary conference / signoff / escalation

観点:

- agent workflow に移植すべき構造
- 移植すべきでない医療固有概念
- 用語の誤解リスク
- PLAN / ORDER / RESULT / INCIDENT / DISCHARGE template への落とし込み

初期確認済みの重要ソース:

- AHRQ TeamSTEPPS SBAR: https://www.ahrq.gov/teamstepps-program/curriculum/communication/tools/sbar.html
- IHI SBAR Tool: https://www.ihi.org/library/tools/sbar-tool-situation-background-assessment-recommendation
- AHRQ PSNet Handoffs: https://psnet.ahrq.gov/primer/handoffs
- AHRQ IDEAL Discharge Planning: https://www.ahrq.gov/patient-safety/patients-families/engagingfamilies/strategy4/index.html
- AHRQ PSNet Discharge Planning and Transitions of Care: https://psnet.ahrq.gov/primer/discharge-planning-and-transitions-care
- WHO Patient Safety Incident Reporting and Learning Systems: https://www.who.int/publications/i/item/9789240010338
- WHO Incident Reporting and Learning Systems: https://www.who.int/teams/integrated-health-services/patient-safety/research/incident-reporting-and-learning-systems
- Joint Commission Sentinel Event Policy and Procedures, effective January 1, 2026: https://www.jointcommission.org/en-us/knowledge-library/support-center/standards-interpretation/sentinel-event-policy-and-procedures

未解決事項:

- 「退院」「インシデント」「オーダー」などの医療用語を UI / CLI にそのまま使うか、technical alias を用意するか。
- SBAR を ORDER template に組み込むか、handoff result template に組み込むか。
- RCA を重大 incident のみ必須にするか、すべての policy deviation に簡易 RCA を要求するか。

推奨判断:

- CLI 上は `case`, `order`, `incident`, `discharge` を使う。
- template 内で医療由来の構造を説明するが、医療システムではないことを README に明記する。

---

### 2.2 R-002: TAKT / 既存 OSS 比較調査

出力先:

```text
research/R-002-takt-and-oss-agent-orchestration.md
```

調査対象:

- `nrslib/takt`
- `takt-sdd`
- Claude Code plugins / skills / hooks repositories
- Codex skills / hooks examples
- Cursor rules / plugins / skills examples
- Git worktree / clone-based isolation tools

観点:

- YAML workflow 定義
- persona / policy / knowledge / instruction / output contract 分離
- review / fix / re-review loop
- provider routing
- worktree or clone isolation
- PR automation
- logs / reports / audit trail
- `agent-careflow` との差分

初期確認済みの重要ソース:

- TAKT GitHub README: https://github.com/nrslib/takt
- TAKT Japanese docs: https://github.com/nrslib/takt/blob/main/docs/README.ja.md
- TAKT task-management docs: https://github.com/nrslib/takt/blob/main/docs/task-management.md
- TAKT configuration docs: https://github.com/nrslib/takt/blob/main/docs/configuration.md
- TAKT export-codex issue: https://github.com/nrslib/takt/issues/475
- Zenn: takt 入門: https://zenn.dev/rasshii/articles/dc19793edab99a
- Zenn: Codex / Cursor / Claude Code 協調体験記: https://zenn.dev/coji/articles/takt-multi-agent-coding-experience

未解決事項:

- TAKT を dependency とするか、参考実装として分析するだけにするか。
- TAKT の piece / movement / facet 概念を `agent-careflow` に取り込むか。
- TAKT の `git clone --shared` 分離を採用するか、通常の `git worktree` を採用するか。
- TAKT workflow との import/export を v1.0 前に実装するか。

推奨判断:

- v0.x では TAKT に依存しない。
- TAKT は比較対象・interop 対象として扱う。
- `agent-careflow` は workflow engine よりも **case artifact protocol + hook enforcement** を優先する。

---

### 2.3 R-003: Codex 公式機能調査

出力先:

```text
research/R-003-codex-official-surface-2026.md
```

調査対象:

- Codex CLI / Codex app / IDE extension
- hooks
- subagents
- skills
- AGENTS.md
- config.toml / requirements.toml
- sandbox / approvals
- MCP / plugins / custom commands

初期確認済みの重要ソース:

- Codex hooks: https://developers.openai.com/codex/hooks
- Codex subagents: https://developers.openai.com/codex/subagents
- Codex skills: https://developers.openai.com/codex/skills
- Codex advanced config: https://developers.openai.com/codex/config-advanced
- Codex config reference: https://developers.openai.com/codex/config-reference
- Codex sandboxing: https://developers.openai.com/codex/concepts/sandboxing
- Codex best practices / AGENTS.md: https://developers.openai.com/codex/learn/best-practices

未解決事項:

- 2026-05 時点の local Codex CLI version で hooks / subagents / skills が実際に同一仕様で動くか。
- hook input / output schema の実 fixture を収集する必要がある。
- `PreToolUse` / `PermissionRequest` で file scope と command policy をどこまで確実に block できるか。
- Codex app / CLI / IDE extension で設定読み込み差があるか。
- profiles, plugins, managed hooks の扱いを MVP に含めるか。

必須作業:

```bash
codex --version
codex --help
codex /status  # interactive only, if available
```

さらに、dummy repo で以下を検証する。

- `.codex/hooks.json` が読み込まれるか
- `.codex/config.toml` inline hooks が読み込まれるか
- `PreToolUse` で forbidden command を deny できるか
- `PermissionRequest` で network / workspace 外アクセスを deny できるか
- subagent に plan_path / order_path を渡す運用が実用的か

---

### 2.4 R-004: Claude Code 公式機能調査

出力先:

```text
research/R-004-claude-code-official-surface-2026.md
```

調査対象:

- Claude Code settings scopes
- hooks
- subagents
- skills
- CLAUDE.md / project settings
- plugins
- MCP
- Agent SDK / `claude -p`

初期確認済みの重要ソース:

- Claude Code overview: https://code.claude.com/docs
- Claude Code hooks guide: https://code.claude.com/docs/en/hooks-guide
- Claude Code hooks reference: https://code.claude.com/docs/en/hooks
- Claude Code subagents: https://code.claude.com/docs/en/sub-agents
- Claude Code skills: https://code.claude.com/docs/en/skills
- Claude Code settings: https://code.claude.com/docs/en/settings

未解決事項:

- project-level `.claude/settings.json` と central `agent-careflow` との symlink/copy 方針。
- `PreToolUse` / `PostToolUse` / `Stop` / `SubagentStart` / `SubagentStop` の exact schema。
- subagent の tools restriction / memory / skill preload を business profile にどこまで使うか。
- private profile では Claude を完全に無効化し、生成物に `.claude/` を出さないか。

必須作業:

```bash
claude --version
claude --help
```

MVP では Claude は optional adapter とする。Claude 不在でも `agent-careflow` が動くことを必須条件にする。

---

### 2.5 R-005: Cursor / Composer / Cursor Agent 調査

出力先:

```text
research/R-005-cursor-composer-agent-surface-2026.md
```

調査対象:

- Composer 2.5
- Plan Mode
- Worktrees
- Subagents
- Agent Skills
- Rules / AGENTS.md
- Hooks
- Cursor CLI
- Cloud Agents / Agents Window
- forum / Reddit reports around subagents, Composer behavior, hooks, model routing

初期確認済みの重要ソース:

- Cursor Plan Mode docs: https://cursor.com/docs/agent/plan-mode
- Cursor Worktrees docs: https://cursor.com/docs/configuration/worktrees
- Cursor Subagents docs: https://cursor.com/docs/subagents
- Cursor Agent Skills docs: https://cursor.com/docs/skills
- Cursor Rules docs: https://cursor.com/docs/rules
- Cursor Hooks docs: https://cursor.com/docs/hooks
- Cursor Composer 2.5 blog, 2026-05-18: https://cursor.com/blog/composer-2-5
- Cursor blog index: https://cursor.com/blog
- Cursor forum: Composer 2.5 / subagents / hooks topics
- Reddit r/cursor posts on Cursor 2.5 plugins / sandbox / async subagents

未解決事項:

- Cursor hooks の block 能力が Codex / Claude と同等か、補助的な built-in hook に留まるか。
- Cursor subagent の model routing / inherited model behavior / Composer 2.5 固定化の実態。
- Cursor rules / AGENTS.md / skills / plugins の読み込み優先順位。
- Cursor CLI と IDE Agent の設定差。
- Plan Mode の plan を repo file としてどのように保存・検証するか。

推奨判断:

- Cursor は primary orchestrator として使えるが、policy enforcement は `agent-careflow` CLI + Git/file checks に寄せる。
- Composer 2.5 は長時間 agent work に有用だが、community reports は必ず「signal」として扱い、公式 docs と実測で確認する。

---

### 2.6 R-006: ブログ / Reddit / Forum 実践知調査

出力先:

```text
research/R-006-community-practice-signals-2026.md
```

目的:

公式 docs だけでは分からない運用上の失敗・費用・context 汚染・subagent 失敗・model routing バグを拾う。

対象:

- Reddit r/codex
- Reddit r/ClaudeCode
- Reddit r/cursor
- Cursor forum
- Zenn / Qiita / note / blog
- Hacker News

扱い:

- community post は authoritative source ではない。
- 実装方針の根拠ではなく、risk register / test scenario / UX caution として使う。
- 重要な claim は必ず公式 docs または local reproduction で確認する。

初期的に拾うべき論点:

- Codex hooks / subagents の version 差
- Claude Code hooks の blocking semantics
- Claude Code subagent + skills の運用パターン
- Cursor Composer 2.5 の長時間作業・指示追従・subagent routing
- Plan-first workflows and plan-review subagents
- session compaction / context hygiene
- cost and token consumption behavior

---

### 2.7 R-007: セキュリティ / ガバナンス調査

出力先:

```text
research/R-007-security-governance-policy.md
```

調査対象:

- sandbox / approvals
- secret detection
- network access
- package install restrictions
- destructive commands
- `git push`, `git reset --hard`, `rm -rf`, `curl | sh`
- path traversal / symlink risk
- MCP server allowlist
- central policy tampering
- target repo bootstrap safety

未解決事項:

- hook 自体が OS user 権限で実行される場合の安全性。
- central repo path が攻撃者に差し替えられた場合の防御。
- `.careflow/PLAN.lock.json` の hash / signature をどこまで強化するか。
- symlink 先の policy 改変をどう検出するか。

---

## 3. 実装対象の repository layout

```text
agent-careflow/
  README.md
  AGENTS.md
  pyproject.toml
  uv.lock                       # 採用する場合

  src/agent_careflow/
    __init__.py
    cli.py
    constants.py

    domain/
      case.py
      plan.py
      order.py
      result.py
      incident.py
      review.py
      conference.py
      discharge.py
      phase.py
      risk.py
      evidence.py

    policy/
      engine.py
      file_scope.py
      command_policy.py
      phase_policy.py
      risk_policy.py
      discharge_policy.py
      incident_policy.py
      hashes.py
      decisions.py

    hooks/
      codex.py
      claude.py
      cursor.py
      common.py

    adapters/
      codex.py
      claude.py
      cursor.py
      takt.py

    bootstrap/
      target_repo.py
      profiles.py
      links.py

    reports/
      research_report.py
      source_registry.py

    schemas/
      CASE.schema.json
      PLAN.schema.json
      ORDER.schema.json
      RESULT.schema.json
      INCIDENT.schema.json
      REVIEW.schema.json
      CONFERENCE.schema.json
      DISCHARGE.schema.json
      POLICY.schema.json
      STATE.schema.json
      SOURCE_REGISTRY.schema.json

    templates/
      CASE.yaml.j2
      PLAN.md.j2
      ORDER.md.j2
      RESULT.md.j2
      INCIDENT.md.j2
      REVIEW.md.j2
      CONFERENCE.md.j2
      DISCHARGE.md.j2
      SOURCE_REGISTRY.md.j2

  rules/
    global/
      phase-policy.yaml
      command-policy.yaml
      file-scope-policy.yaml
      risk-class-policy.yaml
      incident-policy.yaml
      discharge-policy.yaml
      research-policy.yaml

    codex/
      AGENTS.md
      config.toml
      hooks.json
      skills/
      rules/

    claude/
      CLAUDE.md
      settings.json
      agents/
      skills/

    cursor/
      AGENTS.md
      rules/
      hooks.json
      agents/
      skills/

  profiles/
    business.yaml
    private.yaml
    codex-only.yaml
    cursor-codex.yaml

  research/
    README.md
    R-001-medical-workflow-patterns.md
    R-002-takt-and-oss-agent-orchestration.md
    R-003-codex-official-surface-2026.md
    R-004-claude-code-official-surface-2026.md
    R-005-cursor-composer-agent-surface-2026.md
    R-006-community-practice-signals-2026.md
    R-007-security-governance-policy.md

  install/
    install.sh
    install.ps1
    bootstrap-target-repo.sh
    link-codex.sh
    link-claude.sh
    link-cursor.sh

  examples/
    target-repo-small-bugfix/
    target-repo-feature-c2/
    target-repo-incident/

  tests/
    unit/
    integration/
    fixtures/
      codex-hooks/
      claude-hooks/
      cursor-hooks/
      target-repos/
```

---

## 4. Runtime artifact layout in target repositories

```text
target-repo/
  .careflow/
    careflow.yaml
    state.json
    source-registry.lock.json

    cases/
      ACF-20260519-001-auth-flow/
        CASE.yaml
        PLAN.md
        PLAN.lock.json
        orders/
          ORD-001-research.order.md
          ORD-002-implementation.order.md
          ORD-003-verification.order.md
          ORD-004-review.order.md
        results/
          ORD-001-research.result.md
          ORD-002-implementation.result.md
          ORD-003-verification.result.md
          ORD-004-review.result.md
        evidence/
          git-status.txt
          git-diff-summary.txt
          unit-test.txt
          lint.txt
          typecheck.txt
        incidents/
          INC-001-scope-violation.md
        reviews/
          REVIEW-001-code-quality.md
          REVIEW-002-security.md
        conferences/
          CONF-001-plan-approval.md
          CONF-002-post-verification.md
        DISCHARGE.md
```

注意:

- 旧案の `.agentflow/` は廃止し、MVP では `.careflow/` に統一する。
- 互換 alias が必要になれば v0.3 以降で検討する。

---

## 5. CLI 仕様

CLI 名は `agent-careflow` とする。Python module は `agent_careflow`。

### 5.1 v0.1 commands

```bash
agent-careflow init
agent-careflow research scaffold
agent-careflow research validate
agent-careflow bootstrap --target . --profile business
agent-careflow case new --title "..." --risk C2
agent-careflow plan validate --case ACF-...
agent-careflow order validate --case ACF-... --order ORD-...
agent-careflow phase status --case ACF-...
agent-careflow phase advance --case ACF-... --to research
agent-careflow discharge validate --case ACF-...
```

### 5.2 v0.2 commands

```bash
agent-careflow policy check-file --case ACF-... --path src/foo.ts --operation write
agent-careflow policy check-command --case ACF-... --command "pnpm test"
agent-careflow incident new --case ACF-... --trigger scope_violation
agent-careflow evidence collect --case ACF-... --kind git-status
agent-careflow hash plan --case ACF-...
```

### 5.3 v0.3 hook commands

```bash
agent-careflow hook codex pre-tool-use
agent-careflow hook codex permission-request
agent-careflow hook codex post-tool-use
agent-careflow hook codex user-prompt-submit
agent-careflow hook codex stop

agent-careflow hook claude pre-tool-use
agent-careflow hook claude post-tool-use
agent-careflow hook claude stop
agent-careflow hook claude subagent-start
agent-careflow hook claude subagent-stop

agent-careflow hook cursor pre-tool-use
agent-careflow hook cursor post-tool-use
agent-careflow hook cursor stop
```

### 5.4 v0.4 profile commands

```bash
agent-careflow install --profile business --enable codex --enable claude --enable cursor
agent-careflow install --profile private --enable codex --enable cursor --disable claude
agent-careflow profile validate business
agent-careflow profile render business --target ~/.agent-careflow/rendered/business
```

---

## 6. Phase model

```text
intake
planning
research
implementation_planning
implementation
verification
review
conference
remediation
discharge
archive
```

Phase は task の risk class によって省略可能。ただし省略は PLAN に明記する。

| Phase | 目的 | 主な成果物 | 実装 gate |
|---|---|---|---|
| intake | case 作成、risk 判定 | CASE.yaml | schema valid |
| planning | PLAN 作成 | PLAN.md, PLAN.lock.json | PLAN approved |
| research | 調査 | research result / research reports | source registry present |
| implementation_planning | ORDER 発行 | orders/*.order.md | plan hash valid |
| implementation | 実装 | diff, result | scope policy pass |
| verification | テスト・検証 | evidence/*.txt | required evidence present |
| review | 独立レビュー | reviews/*.md | required reviews pass |
| conference | phase transition 判断 | conferences/*.md | signoff pass |
| remediation | incident 対応 | incident updates, follow-up orders | no blocker incident |
| discharge | 最終処理 | DISCHARGE.md | discharge policy pass |
| archive | case 終了 | archived state | immutable archive |

---

## 7. Risk class policy

| Class | 意味 | 必須要件 |
|---|---|---|
| C0 | 変更なしの質問・軽調査 | CASE-lite |
| C1 | 小規模・低リスク変更 | PLAN-lite, ORDER, verification |
| C2 | 通常 feature / bugfix | full PLAN, research optional, review 1 件 |
| C3 | auth / payment / data / security / migration | research required, conference, review 2 件, rollback plan |
| C4 | release / production / destructive / irreversible | C3 + incident drill + human signoff |

MVP では C0〜C2 を実装し、C3〜C4 は schema と policy placeholder を作る。

---

## 8. Hook / policy 方針

### 8.1 原則

- 危険操作は `PostToolUse` ではなく `PreToolUse` / `PermissionRequest` で止める。
- hook は OS user 権限で実行されるため、hook input は必ず validate / sanitize する。
- LLM に「守ってください」と頼むのではなく、CLI で deny を返す。
- phase / order / plan hash / allowed paths / command rules をすべて合わせて判定する。

### 8.2 policy examples

```yaml
phase_policies:
  planning:
    allow_write:
      - ".careflow/cases/*/CASE.yaml"
      - ".careflow/cases/*/PLAN.md"
      - ".careflow/cases/*/PLAN.lock.json"
    deny_write:
      - "src/**"
      - "tests/**"

  research:
    allow_write:
      - ".careflow/cases/*/results/*.result.md"
      - ".careflow/cases/*/evidence/**"
    deny_write:
      - "src/**"
      - "tests/**"

  implementation:
    require_active_order: true
    require_plan_hash_match: true
    allow_write_from_order: true
    deny_commands:
      - "git push"
      - "git reset --hard"
      - "rm -rf"
      - "curl | sh"
      - "npm install"
      - "pnpm add"
      - "pip install"
      - "chmod -R 777"

  verification:
    allow_write:
      - ".careflow/cases/*/evidence/**"
      - ".careflow/cases/*/results/*verification*.md"
    deny_write:
      - "src/**"
      - "tests/**"

  review:
    read_only: true
    allow_write:
      - ".careflow/cases/*/reviews/**"
      - ".careflow/cases/*/results/*review*.md"
```

---

## 9. Tool adapter 方針

### 9.1 Codex adapter

配置:

```text
rules/codex/
  AGENTS.md
  config.toml
  hooks.json
  skills/
```

実装方針:

- Codex は最終的な repo builder / autonomous implementer / verification executor として重視する。
- Codex hooks から `agent-careflow hook codex ...` を呼び出す。
- Codex skills は `plan-review`, `order-create`, `verification`, `incident-report`, `discharge` に分ける。
- Codex subagents は明示依頼時のみ起動し、必ず `plan_path` と `order_path` を渡す。

### 9.2 Claude adapter

配置:

```text
rules/claude/
  CLAUDE.md
  settings.json
  agents/
  skills/
```

実装方針:

- business profile のみ有効。
- Claude primary / orchestrator としての利用に強い。
- hooks / subagents / skills を活用するが、policy logic は `agent-careflow` CLI に集約する。
- private profile では生成しない。

### 9.3 Cursor adapter

配置:

```text
rules/cursor/
  AGENTS.md
  rules/
  hooks.json
  agents/
  skills/
```

実装方針:

- private profile では primary orchestrator 候補。
- Plan Mode で作成した plan を `.careflow/cases/<case>/PLAN.md` に保存・検証させる。
- Worktrees / Agents Window / Composer 2.5 を使う場合も、phase gate は `agent-careflow` CLI に寄せる。

---

## 10. Research report workflow

実装開始前に必ず以下を実行する。

```bash
agent-careflow research scaffold
agent-careflow research validate
```

各 report は以下の形式とする。

```markdown
# R-XXX: <title>

checked_at: 2026-05-19T00:00:00+09:00
owner: researcher
status: draft | reviewed | accepted

## Scope

## Sources
| source | type | date checked | authority | notes |
|---|---|---:|---|---|

## Verified facts

## Implementation implications

## Risks / caveats

## Open questions

## Decisions proposed

## References to add to PLAN
```

Source authority levels:

| Level | Source type |
|---|---|
| A | Official vendor docs / official standards bodies |
| B | Official GitHub repo / changelog / issue by maintainer |
| C | Technical blog by identifiable practitioner |
| D | Forum / Reddit / HN community signal |

D-level sources cannot directly justify implementation policy. They can generate test cases or risks.

---

## 11. MVP implementation milestones

### Milestone 0: Research scaffold and source registry

Goal:

- `research/` directory and report templatesを作成する。
- 初期 source registry を固定する。
- research validation を実装する。

Deliverables:

- `research/README.md`
- `research/R-001...R-007.md`
- `schemas/SOURCE_REGISTRY.schema.json`
- `agent-careflow research scaffold`
- `agent-careflow research validate`

Acceptance criteria:

- すべての required report file が存在する。
- 各 report に scope / sources / verified facts / open questions がある。
- source authority level が明示される。

---

### Milestone 1: Core artifact protocol

Goal:

- CASE / PLAN / ORDER / RESULT / INCIDENT / REVIEW / CONFERENCE / DISCHARGE の schema と template を作る。

Deliverables:

- schemas
- templates
- validators
- `case new`
- `plan validate`
- `order validate`
- `discharge validate`

Acceptance criteria:

- invalid case is rejected
- invalid order without plan_path is rejected
- order referencing mismatched plan hash is rejected
- discharge without evidence is rejected

---

### Milestone 2: Policy engine

Goal:

- phase, file scope, command policy, risk policy を実装する。

Deliverables:

- `policy/engine.py`
- `policy/file_scope.py`
- `policy/command_policy.py`
- `policy/phase_policy.py`
- `agent-careflow policy check-*`

Acceptance criteria:

- planning phase で `src/**` write が deny される。
- implementation phase で active ORDER なしの write が deny される。
- verification phase で code write が deny される。
- destructive command が deny される。

---

### Milestone 3: Hook adapters

Goal:

- Codex / Claude / Cursor hooks から共通 policy engine を呼び出す。

Deliverables:

- `hooks/codex.py`
- `hooks/claude.py`
- `hooks/cursor.py`
- fixture-based tests
- `rules/*/hooks.json` or settings templates

Acceptance criteria:

- fixture input から allow / deny / warn が安定して返る。
- unsupported hook schema は fail-open ではなく safe warning / fail-closed を選べる。
- hook が incident を生成できる。

---

### Milestone 4: Target repo bootstrap

Goal:

- 対象 repo に最小 runtime config を生成する。

Deliverables:

- `agent-careflow bootstrap --target . --profile business`
- `agent-careflow bootstrap --target . --profile private`
- `.careflow/careflow.yaml`
- `.careflow/state.json`

Acceptance criteria:

- business profile は Codex / Claude / Cursor を有効化できる。
- private profile は Claude を出力しない。
- central repo path が存在しない場合は fail する。

---

### Milestone 5: Case lifecycle

Goal:

- case 作成から discharge までの CLI flow を通す。

Deliverables:

- `case new`
- `phase status`
- `phase advance`
- `order issue`
- `result validate`
- `incident new`
- `review validate`
- `discharge validate`

Acceptance criteria:

- open incident がある case は discharge できない。
- required evidence が不足する case は review に進めない。
- phase advance は policy によって block される。

---

### Milestone 6: Subagent order workflow

Goal:

- subagent に渡す order package を生成する。

Deliverables:

- `agent-careflow order issue`
- `agent-careflow order prompt --tool codex|claude|cursor`
- role templates: researcher / implementer / verifier / reviewer / incident-commander

Acceptance criteria:

- prompt には plan_path と order_path が必ず含まれる。
- subagent output path が order に明記される。
- result file がない場合、order は complete 扱いにならない。

---

### Milestone 7: Isolation strategy

Goal:

- worktree / clone isolation を正式化する。

Options:

1. `git worktree`
2. `git clone --shared`
3. temporary clone + patch export

調査論点:

- agent が `.git` 経由で main repo に戻れるか。
- symlink / path traversal risk。
- cleanup strategy。
- PR generation。

推奨:

- v0.x は `git worktree` を default にし、R-002 調査後に `git clone --shared` を optional にする。

---

### Milestone 8: TAKT interop / comparative mode

Goal:

- TAKT を置き換えるのではなく、比較・import/export 対象として扱う。

Deliverables:

- `agent-careflow takt analyze`
- `agent-careflow takt import-workflow`
- `agent-careflow takt export-policy` などは backlog。

Acceptance criteria:

- TAKT workflow の persona / policy / output contract を agent-careflow の order/policy 構造に対応付ける report が出る。

---

## 12. Testing strategy

### 12.1 Unit tests

- schema validation
- plan hash
- order immutability
- allowed path matching
- forbidden command matching
- risk class escalation
- incident severity calculation

### 12.2 Fixture tests

- Codex hook input fixtures
- Claude hook input fixtures
- Cursor hook input fixtures
- target repo fixture with invalid states

### 12.3 Integration tests

- create target repo
- bootstrap
- create case
- create plan
- issue order
- simulate file write
- collect evidence
- create review
- discharge

### 12.4 Golden file tests

- template rendering
- subagent prompt rendering
- discharge summary rendering
- PR body rendering

---

## 13. Initial Codex bootstrap prompt

Codex に `agent-careflow` を実装させる最初の prompt は以下を使う。

```text
Repository name: agent-careflow

You are implementing agent-careflow, a central control repository for AI coding-agent workflows.

Core idea:
- agent-careflow contains all static rules, settings, schemas, templates, hooks, skills, subagent definitions, profiles, and deployment scripts.
- target repositories contain runtime case artifacts only under .careflow/.
- PLAN.md is the case-level plan.
- ORDER files are separate immutable instructions to subagents.
- Every subagent must receive both plan_path and order_path.
- Hooks and CLI validators enforce phase constraints deterministically.
- Tool-specific configs for Codex, Claude Code, and Cursor are thin adapters.
- Core policy logic must live in the agent-careflow CLI, not in model prompts.

Before implementation:
1. Create .careflow/cases/ACF-BOOTSTRAP/CASE.yaml.
2. Create .careflow/cases/ACF-BOOTSTRAP/PLAN.md.
3. Create .careflow/cases/ACF-BOOTSTRAP/orders/ORD-001-research.order.md.
4. Create research report stubs under research/.
5. Fill an initial source registry from official docs and existing OSS references.
6. Do not implement code before the research scaffold and PLAN are written.

First milestone:
Build Milestone 0 and Milestone 1 only.

Deliver:
- repository layout
- Python package named agent_careflow
- CLI command named agent-careflow
- schemas and templates
- research scaffold and validation
- case creation
- plan validation
- order validation
- discharge validation
- tests
- README explaining the workflow

Use subagents only for bounded review tasks:
- one research reviewer for healthcare workflow mapping
- one research reviewer for TAKT / OSS workflow comparison
- one technical reviewer for Codex / Claude / Cursor adapter assumptions

Each subagent must receive:
- plan_path
- order_path
- expected result_path

Wait for all subagent results, summarize disagreements, and create a conference note before finalizing.
```

---

## 14. Important design decisions to lock early

1. Runtime directory name: `.careflow/`.
2. Central repository name: `agent-careflow`.
3. Static rules live only in `agent-careflow`.
4. Target repo artifacts are runtime state, not central policy.
5. PLAN / ORDER split is non-negotiable.
6. ORDER immutability is non-negotiable.
7. Hook enforcement must be CLI-driven.
8. Research reports must precede implementation.
9. Community sources are signals, not authority.
10. Claude is optional; private profile must work without Claude.
11. Cursor is usable as primary orchestrator but not trusted as sole policy enforcer.
12. Codex is the preferred autonomous implementer for the repository itself.

---

## 15. Open risks

| Risk | Impact | Mitigation |
|---|---|---|
| Vendor hook schemas change | hooks break | fixture tests + version report |
| Cursor docs are dynamic / sparse | adapter assumptions wrong | local reproduction + forum review |
| TAKT already solves enough | duplicate work | R-002 comparison before workflow engine implementation |
| Too many artifacts slow agents | friction | risk-class-based ceremony reduction |
| Medical terms confuse users | wrong expectations | README disclaimer + technical aliases |
| Central repo symlink tampering | policy bypass | path validation + hash locks |
| Community advice is noisy | bad design | authority levels + reproduction requirement |
| LLM ignores PLAN/ORDER | scope drift | hooks + file scope checks + active ORDER requirement |

---

## 16. Definition of Done for v0.1

v0.1 is done when:

- `agent-careflow` repository has research scaffold, schemas, templates, CLI, and tests.
- `agent-careflow bootstrap` can initialize a target repo.
- `case new` creates a valid case directory.
- `PLAN.md` and `ORDER.md` are validated by schema and hash.
- `DISCHARGE.md` cannot validate without required evidence.
- `research validate` ensures required research reports exist.
- README explains central repo vs target repo separation.
- No Codex / Claude / Cursor adapter contains duplicated policy logic.

