# AGENTS.md — 本仓库短地图

> 保持简短。细节在 Skill `references/` 与 `skill-pack/`，不要把百科写进这里。

## 路由

| 用户意图 | 动作 |
|----------|------|
| 开发功能 / 从 0 搭 / 模糊需求 / 「按 SOP」 | **必须** `/ai-dev-sop`（`skills/ai-dev-sop/`） |
| 纯问答、解释代码、与实现无关 | 普通对话即可 |
| 明确单行热修且用户拒绝完整 SOP | 可直改；**仍须** diff 自检，禁止碰 G3 |

开发类任务：**禁止跳过 L1 需求澄清**直接写业务代码（除非用户书面要求热修且范围单文件）。

## Never

- 无用户确认的 Spec 就开始写业务功能
- 输出门禁哨兵句之前继续写码 / push
- 自主生产部署、删数、提交密钥
- 自主改资金结算、外部系统凭据、法定/合规字段、生产 PII 用途
- 把「可能、大概、优化一下」写进验收标准
- 全自动合 main

## Always

- 节点交付物进仓（见 `docs/节点交付物.md`）；对话批准不算完成
- 制品：SPEC / MVP / ARCH / PLAN / ACCEPTANCE
- G2 操作先预览再等人批；G3 升级授权审批人
- 范围变更 → 打回 L1；切片/架构变更 → 打回 PHASE 2/3
- 进入阶段时加载对应 `skill-pack/0x-*/SKILL.md`
- Spec → MVP → **架构** → Plan → …；热修可跳前几道，不可跳 Diff

## 关键路径

- Skill：`skills/ai-dev-sop/SKILL.md`
- 子技能：`skill-pack/01`…`06`（含 mvp-cut、arch-design）
- 节点交付物总表：`docs/节点交付物.md`
- 甲方收集：`templates/INTENT-raw.md`
- 产品整理 Intent：`templates/INTENT.md`（再 `/ai-dev-sop`）
- 模板：`SPEC` / `ACCEPTANCE` / `ARCHITECTURE` / 合规表
- DoR 脚本：`skills/ai-dev-sop/scripts/check-dor.sh`
- 人读总览：`docs/00-总览与流程图.md`

## 安装与试跑

```bash
./install.sh                 # 默认：用户级多客户端 + 本仓项目链
./install.sh --no-project    # 仅用户级（个人跨仓推荐）
./install.sh --tool grok     # 只装某一客户端目录
./install.sh --check
./install.sh --into /path/to/product-repo
```

读包内文件用 **SOP_ROOT**（`skills/ai-dev-sop` 目录再上两级）；写 Spec 到工作区 `docs/specs/`。

试跑：`docs/试跑剧本.md` → 记录 `docs/试跑记录.md` → 勾选 `docs/试点投产检查单.md`

## DoR 机械检查

```bash
./skills/ai-dev-sop/scripts/check-dor.sh <SPEC.md> [ACCEPTANCE.md]
```
