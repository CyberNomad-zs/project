# AI 开发 SOP

通用、**可启动**的 AI 辅助软件开发标准作业程序。

- **形态**：唯一 Skill 入口 + 阶段状态机 + Spec 模板 + 分阶段子技能包  
- **原则**：清单与门禁替代自由裁量；制品进仓；生成与校验分离  
- **状态**：P0 + P1 + P2 已落盘；**试点投产工具**已齐（install / 试跑 / 检查单）  


---

## 使用说明（推荐先读）

完整安装、员工协作、节点交付物与管理者检查：见 **[`使用说明.md`](./使用说明.md)**。  
节点总表：[`docs/节点交付物.md`](./docs/节点交付物.md)。

## 唯一记法

```text
1. 甲方/业务：填 templates/INTENT-raw.md（白话收集卡）
2. AI 产品经理：整理成 templates/INTENT.md（至少 §0）
3. /ai-dev-sop + 粘贴整理后的 INTENT
4. 回答澄清问题，直到 Spec 被确认
5. 依次批准：MVP → 架构 → Plan →（Findings）→ Diff（看进仓文件，不只看对话）
6. 不要跳过门禁；不确定就写进 ASSUMPTIONS 或升级审批
```

| 模板 | 谁填 | 用途 |
|------|------|------|
| [`INTENT-raw.md`](templates/INTENT-raw.md) | 甲方 / 业务 | 收原始需求（白话） |
| [`INTENT.md`](templates/INTENT.md) | AI 产品经理 | 整理后喂给 `/ai-dev-sop` |

示例：[`INTENT-raw-example`](docs/specs/INTENT-raw-example.md) · [`INTENT-example`](docs/specs/INTENT-example.md)

---

## 安装 / 让 Agent 找得到 Skill

```bash
# 推荐：校验 + 用户级多客户端链 + 本仓项目链
./install.sh

# 仅用户级（任意业务仓可用 /ai-dev-sop）
./install.sh --no-project

# 仅检查不写链接
./install.sh --check

# 同步到业务仓（团队共享）
./install.sh --into /path/to/your-product-repo

# 只写某一客户端目录；或用复制代替 symlink
./install.sh --tool cursor|claude|grok|agents
./install.sh --copy --no-global
```

`install.sh` 会：校验布局、跑 `check-dor` smoke、按约定写入用户级/项目级 Skill 目录（默认 `--tool all`）。

| 适配 | 用户级 | 项目级 |
|------|--------|--------|
| A | `~/.cursor/skills/` | `.cursor/skills/` |
| B | `~/.claude/skills/` | `.claude/skills/` |
| C | `~/.grok/skills/` | `.grok/skills/` |
| 通用 | `~/.agents/skills/` | `.agents/skills/` |

通过 **`/ai-dev-sop`** 显式调用。读包用 **SOP_ROOT**；写制品到当前工作区 `docs/specs/`。流程与交付物**不绑定**某一产品 UI。

### 试点投产

| 文档 | 用途 |
|------|------|
| [试点投产检查单](docs/试点投产检查单.md) | 宣布启用前勾选 |
| [试跑剧本](docs/试跑剧本.md) | 30–45 min 端到端 |
| [试跑记录](docs/试跑记录.md) | 留下证据 |
| [hooks 草案](docs/hooks-草案.md) | 可选机械防呆（非必须） |

---

## 仓库结构

```text
ai开发sop/
├── install.sh                    # 安装 / 校验 / 同步到业务仓
├── README.md
├── AGENTS.md
├── docs/                         # 人读 + 试跑 + 投产检查
├── skills/ai-dev-sop/            # ★ 唯一可启动入口
├── skill-pack/                   # 分阶段子技能
└── templates/                    # INTENT-raw / INTENT / SPEC / …
```

---

## 流程速览

```text
/ai-dev-sop
  → PHASE 0  mode
  → PHASE 1  Spec 批准                         [硬]  + 01
  → PHASE 2  MVP / Ship-now                    [硬]  + 02
  → PHASE 3  Architecture                      [硬]  + 03
  → PHASE 4  Plan                              [硬]  + 04
  → PHASE 5  Findings                          [硬/可 N/A]
  → PHASE 6  Implement                               + 05
  → PHASE 7  Diff → PR                         [硬]  + 06
```

每个硬节点 = 哨兵句 + 人批 + **进仓制品**（见 [`docs/节点交付物.md`](docs/节点交付物.md)）。

哨兵句：

- `SPEC READY — waiting for approval`
- `MVP READY — waiting for approval`
- `ARCH READY — waiting for approval`
- `PLAN READY — waiting for approval`
- `FINDINGS READY — waiting for approval`
- `DIFF READY — waiting for approval`

DoR 阈值：Out of Scope ≥3 · Open Questions ≤2 · Edge ≥3 · 用户批准。

```bash
./skills/ai-dev-sop/scripts/check-dor.sh path/to/SPEC.md [path/to/ACCEPTANCE.md]
```

---

## 文档索引

| 文档 | 用途 |
|------|------|
| [00 总览与流程图](docs/00-总览与流程图.md) | 人读入口 |
| [L0](docs/L0-心智与禁区.md) · [L1](docs/L1-需求澄清.md) · [L2](docs/L2-开发执行.md) · [L3](docs/L3-评审发布.md) | 分阶段说明 |
| [合规扩展 checklist](templates/spec-compliance-checklist.md) | L1/L3 合规展开 |
| [SKILL.md](skills/ai-dev-sop/SKILL.md) | Agent 总控 |
| [skill-pack/](skill-pack/) | 分阶段子技能 |

---

## 明确不做

- 全自动合并生产  
- 重型 MCP 需求平台（先用文件态 Spec）  
- 把培训课程伪装成 Skill  
